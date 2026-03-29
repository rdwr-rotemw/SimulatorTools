import logging
import re
from typing import Optional

from backend.app.modules.sapro.oid_compiler.constants import (
    DEFAULT_RANGES,
    ENTRYSTATUS_TCS,
    ROWSTATUS_TCS,
    SYNTAX_MAP,
)
from backend.app.modules.sapro.oid_compiler.models import (
    AccessLevel,
    DynamicColumnConfig,
    DynamicRowConfig,
    DynamicRowType,
    OidEntry,
    PdfColumnInfo,
    PdfTableInfo,
)

logger = logging.getLogger(__name__)


class DynamicRowDetector:
    """Detect dynamic row creation type and parameters for SNMP tables."""

    # Newinstance detection patterns
    PATTERN_A = re.compile(
        r"[Ss]etting\s+this\s+object\s+to\s+(?:the\s+)?value\s+"
        r"(\w+)\((\d+)\)\s+has\s+the\s+effect\s+of\s+invalidat"
    )
    PATTERN_B = re.compile(
        r"[Ss]tatus\s+is\s+invalid.*(?:entry|community)\s+.*(?:will\s+be\s+)?deleted",
        re.DOTALL,
    )
    PATTERN_C = re.compile(r"[Vv]alidity.*[Ii]nvalid\s+indicates")

    def __init__(
        self,
        mib_entries: list[OidEntry],
        pdf_tables: list[PdfTableInfo],
    ):
        self.mib_entries = mib_entries
        self.pdf_tables = pdf_tables
        self._mib_by_label: dict[str, OidEntry] = {e.label: e for e in mib_entries}
        self._mib_by_table: dict[str, list[OidEntry]] = {}
        for e in mib_entries:
            if e.is_table_column and e.table_name:
                self._mib_by_table.setdefault(e.table_name, []).append(e)

    def detect_all(self) -> list[DynamicRowConfig]:
        configs: list[DynamicRowConfig] = []

        for pdf_table in self.pdf_tables:
            mib_columns = self._mib_by_table.get(pdf_table.table_name, [])
            config = self._detect_table(pdf_table, mib_columns)
            if config:
                configs.append(config)

        logger.info(
            f"Detected {len(configs)} dynamic row tables "
            f"({sum(1 for c in configs if c.is_fully_detected)} fully detected, "
            f"{sum(1 for c in configs if not c.is_fully_detected)} commented out)"
        )
        return configs

    def _detect_table(
        self, pdf_table: PdfTableInfo, mib_columns: list[OidEntry]
    ) -> Optional[DynamicRowConfig]:
        row_type = self._detect_table_type(pdf_table, mib_columns)
        if row_type is None:
            return None

        if row_type == DynamicRowType.NEWINSTANCE:
            return self._build_newinstance_config(pdf_table, mib_columns)

        # rowstatus or rmonstatus
        dcol_configs = self._build_dcol_configs(pdf_table, mib_columns, row_type)
        return DynamicRowConfig(
            entry_name=pdf_table.entry_name,
            row_type=row_type,
            columns=dcol_configs,
        )

    def _detect_table_type(
        self, table: PdfTableInfo, mib_columns: list[OidEntry]
    ) -> Optional[DynamicRowType]:
        # Check MIB columns for RowStatus/EntryStatus syntax
        for col in mib_columns:
            original_syntax = self._get_original_syntax(col)
            if original_syntax in ROWSTATUS_TCS:
                return DynamicRowType.ROWSTATUS
            if original_syntax in ENTRYSTATUS_TCS:
                return DynamicRowType.RMONSTATUS

        # Check PDF columns for RowStatus/EntryStatus syntax
        for pdf_col in table.columns:
            if pdf_col.syntax in ROWSTATUS_TCS:
                return DynamicRowType.ROWSTATUS
            if pdf_col.syntax in ENTRYSTATUS_TCS:
                return DynamicRowType.RMONSTATUS

        # Check if table has any RW columns (potential newinstance)
        has_rw = any(
            pdf_col.access.upper() in ("RW", "CREATE")
            for pdf_col in table.columns
        )
        if not has_rw:
            has_rw = any(
                col.access in (AccessLevel.RW, AccessLevel.CREATE)
                for col in mib_columns
            )

        if has_rw:
            return DynamicRowType.NEWINSTANCE

        return None

    def _get_original_syntax(self, col: OidEntry) -> str:
        """Get the original (pre-normalization) syntax by reverse-looking up SYNTAX_MAP."""
        for original, normalized in SYNTAX_MAP.items():
            if normalized == col.syntax and original in ROWSTATUS_TCS | ENTRYSTATUS_TCS:
                return original
        return col.syntax

    def _build_newinstance_config(
        self, pdf_table: PdfTableInfo, mib_columns: list[OidEntry]
    ) -> DynamicRowConfig:
        setaction_col, setaction_type, setaction_value, is_detected, warning = (
            self._detect_newinstance_delete_action(pdf_table, mib_columns)
        )

        dcol_configs = self._build_dcol_configs(
            pdf_table, mib_columns, DynamicRowType.NEWINSTANCE
        )

        return DynamicRowConfig(
            entry_name=pdf_table.entry_name,
            row_type=DynamicRowType.NEWINSTANCE,
            columns=dcol_configs,
            setaction_column=setaction_col,
            setaction_type=setaction_type,
            setaction_value=setaction_value,
            is_fully_detected=is_detected,
            detection_warning=warning,
        )

    def _detect_newinstance_delete_action(
        self,
        table: PdfTableInfo,
        mib_columns: list[OidEntry],
    ) -> tuple[Optional[str], Optional[str], Optional[str], bool, Optional[str]]:
        # Scan PDF column descriptions for patterns
        for pdf_col in table.columns:
            desc = pdf_col.description

            # Pattern A: explicit "Setting to value invalid(N)"
            match = self.PATTERN_A.search(desc)
            if match:
                value = match.group(2)
                syntax = self._resolve_column_syntax(pdf_col.label, pdf_col.syntax, mib_columns)
                return pdf_col.label, syntax, value, True, None

            # Pattern B: "status is invalid ... entry will be deleted"
            if self.PATTERN_B.search(desc):
                value = self._infer_invalid_value(pdf_col.label, mib_columns)
                syntax = self._resolve_column_syntax(pdf_col.label, pdf_col.syntax, mib_columns)
                return pdf_col.label, syntax, value, True, None

            # Pattern C: "Validity ... Invalid indicates"
            if self.PATTERN_C.search(desc):
                value = self._infer_invalid_value(pdf_col.label, mib_columns)
                syntax = self._resolve_column_syntax(pdf_col.label, pdf_col.syntax, mib_columns)
                return pdf_col.label, syntax, value, True, None

        # Also check MIB descriptions
        for mib_col in mib_columns:
            desc = mib_col.description

            match = self.PATTERN_A.search(desc)
            if match:
                value = match.group(2)
                return mib_col.label, mib_col.syntax, value, True, None

            if self.PATTERN_B.search(desc):
                value = self._infer_invalid_value(mib_col.label, mib_columns)
                return mib_col.label, mib_col.syntax, value, True, None

            if self.PATTERN_C.search(desc):
                value = self._infer_invalid_value(mib_col.label, mib_columns)
                return mib_col.label, mib_col.syntax, value, True, None

        warning = (
            f"Table {table.table_name} has RW columns but the delete-action "
            f"column and value could not be auto-detected."
        )
        return None, None, None, False, warning

    def _infer_invalid_value(self, column_label: str, mib_columns: list[OidEntry]) -> str:
        """Try to find 'invalid' enum value from MIB data, default to '2'."""
        for col in mib_columns:
            if col.label == column_label and col.enum_values:
                for name, value in col.enum_values.items():
                    if "invalid" in name.lower():
                        return str(value)
        return "2"

    def _resolve_column_syntax(
        self, label: str, pdf_syntax: str, mib_columns: list[OidEntry]
    ) -> str:
        """Get normalized syntax, preferring MIB data over PDF."""
        for col in mib_columns:
            if col.label == label:
                return col.syntax
        return SYNTAX_MAP.get(pdf_syntax, pdf_syntax)

    def _build_dcol_configs(
        self,
        table: PdfTableInfo,
        mib_columns: list[OidEntry],
        row_type: DynamicRowType,
    ) -> list[DynamicColumnConfig]:
        configs: list[DynamicColumnConfig] = []
        index_labels = set(table.index_columns)

        # Merge PDF and MIB column info, preferring MIB
        mib_by_label = {c.label: c for c in mib_columns}

        for pdf_col in table.columns:
            label = pdf_col.label
            mib_col = mib_by_label.get(label)

            is_index = label in index_labels
            syntax = mib_col.syntax if mib_col else SYNTAX_MAP.get(pdf_col.syntax, pdf_col.syntax)
            access = mib_col.access.value if mib_col else pdf_col.access.upper()
            if access == "Create":
                access = "RW"

            # Check if this is the RowStatus/EntryStatus column
            is_rowstatus = pdf_col.syntax in ROWSTATUS_TCS or (
                mib_col and self._get_original_syntax(mib_col) in ROWSTATUS_TCS
            )
            is_entrystatus = pdf_col.syntax in ENTRYSTATUS_TCS or (
                mib_col and self._get_original_syntax(mib_col) in ENTRYSTATUS_TCS
            )

            if is_index:
                required = "NotReq"
                value_info = self._get_index_value_info(syntax)
            elif is_rowstatus:
                required = "Req"
                value_info = "rowstatus(1)"
                syntax = "RowStatus"
                access = "RW"
            elif is_entrystatus:
                required = "Req"
                value_info = "rmonstatus(1)"
                syntax = "EntryStatus"
                access = "RW"
            elif access in ("RW", "CREATE"):
                required = "Req"
                value_info = self._get_default_value_info(syntax, "RW", False, row_type)
            else:
                required = "NotReq"
                value_info = self._get_default_value_info(syntax, "RO", False, row_type)

            configs.append(DynamicColumnConfig(
                label=label,
                required=required,
                syntax=syntax,
                access=access if access in ("RO", "RW") else "RO",
                value_info=value_info,
            ))

        return configs

    def _get_index_value_info(self, syntax: str) -> str:
        defaults = {
            "IpAddress": "dfixed(0.0.0.0)",
            "OctetString": "dfixed(0x00)",
            "ObjectID": "dfixed(0.0)",
        }
        return defaults.get(syntax, "dfixed(0)")

    def _get_default_value_info(
        self, syntax: str, access: str, is_index: bool, row_type: DynamicRowType
    ) -> str:
        if access == "RO":
            ro_map = {
                "Counter": "randomup(0, 100)",
                "Counter64": "randomup(0, 100)",
                "Gauge": "random(1000, 100)",
                "Integer": "fixed(1)",
                "OctetString": "fixed(0x00)",
                "TimeTicks": "clock(0)",
                "IpAddress": "fixed(0.0.0.0)",
                "ObjectID": "fixed(0.0)",
            }
            return ro_map.get(syntax, "fixed(0)")

        # RW
        rw_map = {
            "Counter": "lastset(0)",
            "Counter64": "lastset(0)",
            "Gauge": "lastset(0)",
            "Integer": "lastset(1)",
            "OctetString": "lastset(0x00)",
            "TimeTicks": "lastset(0)",
            "IpAddress": "lastset(0.0.0.0)",
            "ObjectID": "lastset(0.0)",
        }
        return rw_map.get(syntax, "lastset(0)")
