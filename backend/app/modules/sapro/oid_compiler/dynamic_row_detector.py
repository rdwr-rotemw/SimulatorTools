import logging
import re
from typing import Optional

from backend.app.modules.sapro.oid_compiler.constants import (
    ENTRYSTATUS_TCS,
    ROWSTATUS_TCS,
)
from backend.app.modules.sapro.oid_compiler.models import (
    DynamicColumnConfig,
    DynamicRowConfig,
    DynamicRowType,
    OidEntry,
)

logger = logging.getLogger(__name__)


class DynamicRowDetector:
    """Detect dynamic row creation type and parameters for SNMP tables.

    Uses MIB data exclusively — no PDF dependency.
    """

    # Newinstance detection patterns (matched against MIB DESCRIPTION fields)
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
        cc_columns: dict[str, set[str]] = None,
    ):
        self.mib_entries = mib_entries
        self._cc_columns = cc_columns or {}
        self._mib_by_label: dict[str, OidEntry] = {e.label: e for e in mib_entries}
        self._mib_by_table: dict[str, list[OidEntry]] = {}
        for e in mib_entries:
            if e.is_table_column and e.table_name:
                self._mib_by_table.setdefault(e.table_name, []).append(e)

    def detect_all(self) -> list[DynamicRowConfig]:
        configs: list[DynamicRowConfig] = []

        for table_name, mib_columns in self._mib_by_table.items():
            config = self._detect_table(table_name, mib_columns)
            if config:
                configs.append(config)

        logger.info(
            f"Detected {len(configs)} dynamic row tables "
            f"({sum(1 for c in configs if c.is_fully_detected)} fully detected, "
            f"{sum(1 for c in configs if not c.is_fully_detected)} commented out)"
        )
        return configs

    def _detect_table(
        self, table_name: str, mib_columns: list[OidEntry]
    ) -> Optional[DynamicRowConfig]:
        """Detect dynamic row type from MIB data."""
        rowstatus_label = None
        row_type = None

        for col in mib_columns:
            if col.original_syntax in ROWSTATUS_TCS:
                row_type = DynamicRowType.ROWSTATUS
                rowstatus_label = col.label
                break
            if col.original_syntax in ENTRYSTATUS_TCS:
                row_type = DynamicRowType.RMONSTATUS
                rowstatus_label = col.label
                break

        # No RowStatus/EntryStatus — check for newinstance patterns in descriptions
        if row_type is None:
            if self._has_newinstance_evidence(mib_columns):
                row_type = DynamicRowType.NEWINSTANCE

        if row_type is None:
            return None

        # Find entry name and index columns
        entry_name = table_name.replace("Table", "Entry")
        index_columns: list[str] = []
        for col in mib_columns:
            if col.index_columns:
                index_columns = col.index_columns
                break

        # Build %dcol configs
        index_labels = set(index_columns)
        index_positions = {label: pos for pos, label in enumerate(index_columns, 1)}
        cc_cols = self._cc_columns.get(table_name, set())

        dcol_configs: list[DynamicColumnConfig] = []

        # Add not-accessible index columns (from other tables, referenced by INDEX)
        for idx_label in index_columns:
            idx_mib = self._mib_by_label.get(idx_label)
            if idx_mib and idx_mib.label not in {c.label for c in mib_columns}:
                idx_pos = index_positions.get(idx_label, 1)
                dcol_configs.append(DynamicColumnConfig(
                    label=idx_label,
                    required="NotReq",
                    syntax=idx_mib.syntax,
                    access="RO",
                    value_info=self._get_index_dfixed(idx_mib.syntax, idx_pos, idx_mib),
                ))

        # Newinstance-specific: detect delete action column
        setaction_col = None
        setaction_type = None
        setaction_value = None
        is_fully_detected = True
        detection_warning = None

        if row_type == DynamicRowType.NEWINSTANCE:
            setaction_col, setaction_type, setaction_value, is_fully_detected, detection_warning = (
                self._detect_newinstance_delete_action(table_name, mib_columns)
            )

        for col in mib_columns:
            is_index = col.label in index_labels
            access = col.access.value if col.access else "RO"
            if access == "Create":
                access = "RC"
            is_rowstatus = col.original_syntax in ROWSTATUS_TCS and col.label == rowstatus_label
            is_entrystatus = col.original_syntax in ENTRYSTATUS_TCS and col.label == rowstatus_label
            cc_sends = col.label in cc_cols

            if is_index:
                idx_pos = index_positions.get(col.label, 1)
                dcol_configs.append(DynamicColumnConfig(
                    label=col.label,
                    required="NotReq",
                    syntax=col.syntax,
                    access="RO",
                    value_info=self._get_index_dfixed(col.syntax, idx_pos, col),
                ))
            elif is_rowstatus:
                dcol_configs.append(DynamicColumnConfig(
                    label=col.label,
                    required="Req",
                    syntax="Integer",
                    access=access if access in ("RC", "RW") else "RW",
                    value_info="rowstatus(1)",
                ))
            elif is_entrystatus:
                dcol_configs.append(DynamicColumnConfig(
                    label=col.label,
                    required="Req",
                    syntax="Integer",
                    access=access if access in ("RC", "RW") else "RW",
                    value_info=self._get_rw_value_info(col.syntax, col),
                ))
            elif access in ("RW", "RC"):
                dcol_configs.append(DynamicColumnConfig(
                    label=col.label,
                    required="Req" if cc_sends else "NotReq",
                    syntax=col.syntax,
                    access=access,
                    value_info=self._get_rw_value_info(col.syntax, col),
                ))
            else:
                dcol_configs.append(DynamicColumnConfig(
                    label=col.label,
                    required="NotReq",
                    syntax=col.syntax,
                    access="RO",
                    value_info=self._get_ro_value_info(col.syntax),
                ))

        return DynamicRowConfig(
            entry_name=entry_name,
            row_type=row_type,
            columns=dcol_configs,
            setaction_column=setaction_col,
            setaction_type=setaction_type,
            setaction_value=setaction_value,
            is_fully_detected=is_fully_detected,
            detection_warning=detection_warning,
        )

    def _has_newinstance_evidence(self, mib_columns: list[OidEntry]) -> bool:
        """Check if any MIB column description matches newinstance deletion patterns."""
        for col in mib_columns:
            if (self.PATTERN_A.search(col.description)
                    or self.PATTERN_B.search(col.description)
                    or self.PATTERN_C.search(col.description)):
                return True
        return False

    def _detect_newinstance_delete_action(
        self,
        table_name: str,
        mib_columns: list[OidEntry],
    ) -> tuple[Optional[str], Optional[str], Optional[str], bool, Optional[str]]:
        """Detect the delete-action column and value for newinstance tables."""
        for col in mib_columns:
            desc = col.description

            match = self.PATTERN_A.search(desc)
            if match:
                value = match.group(2)
                return col.label, col.syntax, value, True, None

            if self.PATTERN_B.search(desc):
                value = self._infer_invalid_value(col.label, mib_columns)
                return col.label, col.syntax, value, True, None

            if self.PATTERN_C.search(desc):
                value = self._infer_invalid_value(col.label, mib_columns)
                return col.label, col.syntax, value, True, None

        warning = (
            f"Table {table_name} has RW columns but the delete-action "
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

    def _get_index_dfixed(self, syntax: str, position: int, mib_col: Optional[OidEntry]) -> str:
        """Generate dfixed value info for index columns."""
        if syntax == "OctetString":
            max_len = mib_col.max_range if mib_col and mib_col.max_range else 255
            return f"dfixed({position},{max_len})"
        return "dfixed(1)"

    def _get_rw_value_info(self, syntax: str, mib_col: Optional[OidEntry]) -> str:
        """Generate value info for RW/RC columns in %dcol blocks."""
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
