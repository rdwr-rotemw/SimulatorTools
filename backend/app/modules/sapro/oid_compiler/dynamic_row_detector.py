import logging
import re
from typing import Optional

from backend.app.modules.sapro.oid_compiler.constants import (
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
        cc_columns: dict[str, set[str]] = None,
    ):
        self.mib_entries = mib_entries
        self.pdf_tables = pdf_tables
        # CC column mapping from device driver JAR: table_name -> set of column labels CC sends.
        # Columns CC sends are Req, columns it doesn't are NotReq.
        self._cc_columns = cc_columns or {}
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
        # Check PDF columns for RowStatus/EntryStatus syntax
        # PDF has the original syntax names (not normalized), so it's authoritative
        for pdf_col in table.columns:
            if pdf_col.syntax in ROWSTATUS_TCS:
                return DynamicRowType.ROWSTATUS
            if pdf_col.syntax in ENTRYSTATUS_TCS:
                return DynamicRowType.RMONSTATUS

        # No RowStatus/EntryStatus — check if descriptions match newinstance patterns
        # Only flag as newinstance if we find actual evidence of delete-action behavior
        if self._has_newinstance_evidence(table, mib_columns):
            return DynamicRowType.NEWINSTANCE

        return None

    def _has_newinstance_evidence(
        self, table: PdfTableInfo, mib_columns: list[OidEntry]
    ) -> bool:
        """Check if any column description matches newinstance deletion patterns."""
        for pdf_col in table.columns:
            if (self.PATTERN_A.search(pdf_col.description)
                    or self.PATTERN_B.search(pdf_col.description)
                    or self.PATTERN_C.search(pdf_col.description)):
                return True
        for mib_col in mib_columns:
            if (self.PATTERN_A.search(mib_col.description)
                    or self.PATTERN_B.search(mib_col.description)
                    or self.PATTERN_C.search(mib_col.description)):
                return True
        return False

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
        # Build ordered index position map: label -> 1-based position
        index_positions: dict[str, int] = {
            label: pos for pos, label in enumerate(table.index_columns, 1)
        }

        mib_by_label = {c.label: c for c in mib_columns}
        pdf_labels = {c.label for c in table.columns}

        # CC columns for this table — used to determine Req vs NotReq.
        cc_cols = self._cc_columns.get(table.table_name, set())

        # Add missing index columns from MIB data (not-accessible indices
        # don't appear in the PDF but are required in %drow blocks)
        for mib_col in mib_columns:
            if mib_col.label not in pdf_labels and mib_col.label in index_labels:
                idx_pos = index_positions.get(mib_col.label, 1)
                configs.append(DynamicColumnConfig(
                    label=mib_col.label,
                    required="NotReq",
                    syntax=mib_col.syntax,
                    access="RO",
                    value_info=self._get_index_dfixed(mib_col.syntax, idx_pos, mib_col),
                ))

        # Also check for index columns that are in MIB but not in PDF or index_labels
        if not index_labels and mib_columns:
            for mib_col in mib_columns:
                if mib_col.index_columns:
                    for idx_label in mib_col.index_columns:
                        if idx_label not in pdf_labels and idx_label not in index_labels:
                            idx_mib = self._mib_by_label.get(idx_label)
                            if idx_mib:
                                configs.append(DynamicColumnConfig(
                                    label=idx_label,
                                    required="NotReq",
                                    syntax=idx_mib.syntax,
                                    access="RO",
                                    value_info=self._get_index_dfixed(idx_mib.syntax, 1, idx_mib),
                                ))
                    break

        for pdf_col in table.columns:
            label = pdf_col.label
            mib_col = mib_by_label.get(label)

            is_index = label in index_labels
            syntax = mib_col.syntax if mib_col else SYNTAX_MAP.get(pdf_col.syntax, pdf_col.syntax)
            access = mib_col.access.value if mib_col else pdf_col.access.upper()
            if access == "Create":
                access = "RC"

            # Check if this is the RowStatus/EntryStatus column
            is_rowstatus = pdf_col.syntax in ROWSTATUS_TCS
            is_entrystatus = pdf_col.syntax in ENTRYSTATUS_TCS

            # Determine Req/NotReq: if CC sends this column, it's Req.
            # If CC doesn't send it (hidden/computed), it's NotReq.
            cc_sends = label in cc_cols

            if is_index:
                required = "NotReq"
                dcol_access = "RO"
                idx_pos = index_positions.get(label, 1)
                value_info = self._get_index_dfixed(syntax, idx_pos, mib_col)
            elif is_rowstatus:
                required = "Req"
                syntax = "Integer"
                dcol_access = access if access in ("RC", "RW") else "RW"
                value_info = self._get_rw_value_info(syntax, mib_col)
            elif is_entrystatus:
                required = "Req"
                syntax = "Integer"
                dcol_access = access if access in ("RC", "RW") else "RW"
                value_info = self._get_rw_value_info(syntax, mib_col)
            elif access in ("RW", "RC"):
                required = "Req" if cc_sends else "NotReq"
                dcol_access = access
                value_info = self._get_rw_value_info(syntax, mib_col)
            else:
                required = "NotReq"
                dcol_access = "RO"
                value_info = self._get_ro_value_info(syntax)

            configs.append(DynamicColumnConfig(
                label=label,
                required=required,
                syntax=syntax,
                access=dcol_access,
                value_info=value_info,
            ))

        return configs

    def _get_index_dfixed(self, syntax: str, position: int, mib_col: Optional[OidEntry]) -> str:
        """Generate dfixed value info for index columns.

        For string indexes (OctetString): dfixed(<position>, <max_length>)
            SAPRO extracts the string from the OID instance at the given
            position, with max_length bytes.
        For integer indexes: dfixed(<position>)
            SAPRO extracts the integer sub-identifier at the given position.
        For IpAddress indexes: dfixed(<position>)
        """
        if syntax == "OctetString":
            max_len = mib_col.max_range if mib_col and mib_col.max_range else 255
            return f"dfixed({position},{max_len})"
        # For non-string indexes, dfixed takes a default value (not position).
        # SAPRO extracts the actual value from the instance OID automatically.
        return "dfixed(1)"

    def _get_rw_value_info(self, syntax: str, mib_col: Optional[OidEntry]) -> str:
        """Generate value info for RW/RC columns in %dcol blocks.

        Uses r_lastset with range only (no default value) to match the
        format that works with SAPRO dynamic row creation.
        """
        has_range = mib_col and mib_col.min_range is not None and mib_col.max_range is not None

        if syntax == "Integer":
            if has_range:
                return f"r_lastset({mib_col.min_range}, {mib_col.max_range})"
            return "lastset(1)"
        if syntax == "OctetString":
            if has_range:
                return f"r_lastset({mib_col.min_range}, {mib_col.max_range})"
            return "lastset(abc)"
        if syntax == "ObjectID":
            return "lastset(1.2.3)"
        if syntax == "IpAddress":
            return "r_lastset(4, 4)"
        if syntax == "Gauge":
            if has_range:
                return f"r_lastset({mib_col.min_range}, {mib_col.max_range})"
            return "lastset(0)"
        if syntax == "Counter":
            return "randomup(1000, 100)"
        if syntax == "Counter64":
            return "randomup(1000, 100)"
        if syntax == "TimeTicks":
            return "clock(0)"
        if syntax == "Bits":
            return "lastset(0x00)"
        return "lastset(0)"

    def _get_ro_value_info(self, syntax: str) -> str:
        """Generate value info for RO columns."""
        defaults = {
            "Counter": "randomup(1000, 100)",
            "Counter64": "randomup(1000, 100)",
            "Gauge": "fixed(1000)",
            "OctetString": "fixed(abc)",
            "TimeTicks": "clock(0)",
            "Integer": "fixed(1)",
            "IpAddress": "fixed(1.2.3.4)",
            "ObjectID": "fixed(1.2.3)",
            "Bits": "fixed(0x00)",
        }
        return defaults.get(syntax, "fixed(0)")
