import logging

from backend.app.modules.sapro.oid_compiler.constants import FIXED_SIZE_TYPES, SYNTAX_MAP
from backend.app.modules.sapro.oid_compiler.models import AccessLevel, OidEntry

logger = logging.getLogger(__name__)

# RowStatus enum value names — used to detect RowStatus columns
ROWSTATUS_ENUM_VALUES = {"active", "notInService", "notReady", "createAndGo", "createAndWait", "destroy"}

# String-based syntaxes — index columns with these types get * prefix in %ei
STRING_INDEX_SYNTAXES = {"OctetString"}


class CmfGenerator:
    """Generate SAPRO .cmf file content from parsed MIB data."""

    def __init__(self, oid_entries: list[OidEntry]):
        self.entries = oid_entries

    def generate(self) -> str:
        """Generate CMF content and return as string."""
        sorted_entries = sorted(
            self.entries,
            key=lambda e: [int(x) for x in e.oid.split(".")],
        )

        lines: list[str] = []

        # Column lines (C1, C2, ... and S for scalars)
        for entry in sorted_entries:
            if entry.is_table_entry or entry.is_table_node or entry.is_structural_node:
                continue
            line = self._format_entry_line(entry)
            if line:
                lines.append(line)

        # %en lines — entry/node name mappings for structural nodes
        en_lines = self._generate_en_lines(sorted_entries)
        if en_lines:
            lines.append("")
            lines.extend(en_lines)

        # %ei lines — table entry index declarations
        ei_lines = self._generate_ei_lines(sorted_entries)
        if ei_lines:
            lines.extend(ei_lines)

        # %ed lines — default values for columns with DEFVAL
        ed_lines = self._generate_ed_lines(sorted_entries)
        if ed_lines:
            lines.extend(ed_lines)

        # %ev lines — enum value definitions
        ev_lines: list[str] = []
        for entry in sorted_entries:
            if entry.has_enum and entry.enum_values:
                ev_lines.extend(self._format_enum_lines(entry))
        if ev_lines:
            lines.append("")
            lines.extend(ev_lines)

        content = "\n".join(lines) + "\n"
        logger.info(f"Generated CMF content ({len(sorted_entries)} entries)")
        return content

    def _format_entry_line(self, entry: OidEntry) -> str:
        syntax = self._normalize_syntax(entry.syntax)
        access = self._format_access(entry)
        index_type = entry.index_type
        range_str = self._compute_range(entry, syntax)
        enum_flag = self._compute_enum_flag(entry, range_str)

        oid_label = f"{entry.oid:<40} {entry.label:<30}"

        if range_str and enum_flag:
            return f"{oid_label} {syntax:<12} {access:<3} {index_type:<3} {range_str} {enum_flag}"
        elif range_str:
            return f"{oid_label} {syntax:<12} {access:<3} {index_type:<3} {range_str}"
        else:
            return f"{oid_label} {syntax:<12} {access:<3} {index_type:<3}"

    def _generate_en_lines(self, sorted_entries: list[OidEntry]) -> list[str]:
        """Generate %en lines for table entries, table nodes, and structural nodes."""
        seen: set[str] = set()
        lines: list[str] = []
        for entry in sorted_entries:
            if entry.is_table_entry or entry.is_table_node or entry.is_structural_node:
                key = entry.oid
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"%en          {entry.oid:<40} {entry.label}")
        return lines

    def _generate_ei_lines(self, sorted_entries: list[OidEntry]) -> list[str]:
        """Generate %ei lines declaring index columns for each table entry.

        Format: %ei <entry_oid> "<index1> <index2> ..."
        String-based indices (OctetString) get a * prefix.
        """
        lines: list[str] = []

        # Build lookup: label -> OidEntry for finding index column types
        label_map: dict[str, OidEntry] = {}
        for e in sorted_entries:
            if e.is_table_column:
                label_map[e.label] = e

        # Find all table entries and their index columns
        for entry in sorted_entries:
            if not entry.is_table_entry:
                continue

            # Get the table's columns to find index labels
            entry_oid = entry.oid
            table_name = entry.label.replace("Entry", "Table")

            # Find columns belonging to this table
            table_cols = [
                e for e in sorted_entries
                if e.is_table_column and e.table_name == table_name
            ]
            if not table_cols:
                continue

            # Get index columns and implied flags from the entry
            index_labels = []
            implied_indexes = set()
            for col in table_cols:
                if col.index_columns:
                    index_labels = list(col.index_columns)
                    implied_indexes = col.implied_indexes
                    break
            # Also check the entry itself
            if not index_labels:
                if entry.index_columns:
                    index_labels = list(entry.index_columns)
                    implied_indexes = entry.implied_indexes

            if not index_labels:
                continue

            # Format index names with * prefix ONLY for IMPLIED string indexes.
            # IMPLIED means the string length is NOT encoded in the OID instance.
            # Non-IMPLIED string indexes have a length prefix — no * needed.
            formatted_indices = []
            for idx_label in index_labels:
                if idx_label in implied_indexes:
                    formatted_indices.append(f"*{idx_label}")
                else:
                    formatted_indices.append(idx_label)

            index_str = " ".join(formatted_indices)
            lines.append(f'%ei   {entry_oid} "{index_str}"')

        return lines

    def _format_access(self, entry: OidEntry) -> str:
        access = entry.access.value
        if access == "Create":
            return "RC"
        return access

    def _compute_range(self, entry: OidEntry, normalized_syntax: str) -> str:
        if normalized_syntax == "ObjectID":
            return ""
        if normalized_syntax == "IpAddress":
            return "(4,4)"
        # Use fixed size from textual convention if the MIB range looks wrong
        if entry.original_syntax in FIXED_SIZE_TYPES:
            fixed_min, fixed_max = FIXED_SIZE_TYPES[entry.original_syntax]
            # Only override if MIB range is suspiciously broad
            if entry.min_range is not None and entry.max_range is not None:
                if entry.max_range > fixed_max * 2:
                    return f"({fixed_min},{fixed_max})"
            else:
                return f"({fixed_min},{fixed_max})"
        if entry.min_range is not None and entry.max_range is not None:
            # Skip meaningless full Integer range
            if normalized_syntax == "Integer" and entry.min_range == -2147483648 and entry.max_range == 2147483647:
                return ""
            return f"({entry.min_range},{entry.max_range})"
        return ""

    def _compute_enum_flag(self, entry: OidEntry, range_str: str) -> str:
        if not range_str:
            return ""
        if entry.has_enum and entry.enum_values:
            if ROWSTATUS_ENUM_VALUES.issubset(set(entry.enum_values.keys())):
                return "r"
            return "e"
        if entry.display_hint and "1x:" in str(entry.display_hint):
            return "p"
        return "d"

    def _generate_ed_lines(self, sorted_entries: list[OidEntry]) -> list[str]:
        """Generate %ed lines for columns with DEFVAL in the MIB.

        Format: %ed                  <column_label> <default_value>
        For enum columns, the enum name is used (e.g., 'ipMask' not '1').
        For string defaults, quotes are added.
        """
        lines: list[str] = []
        for entry in sorted_entries:
            if not entry.default_value or entry.is_table_entry:
                continue
            if not entry.is_table_column:
                continue

            val = entry.default_value
            # For enum columns, try to resolve numeric default to enum name
            if entry.has_enum and entry.enum_values:
                try:
                    num_val = int(val)
                    for name, enum_val in entry.enum_values.items():
                        if enum_val == num_val:
                            val = name
                            break
                except (ValueError, TypeError):
                    pass

            # Quote string values that contain spaces or look like names
            if entry.syntax == "OctetString" and not val.startswith("'") and not val.isdigit():
                val = f'"{val}"'

            lines.append(f"%ed                  {entry.label} {val}")
        return lines

    def _format_enum_lines(self, entry: OidEntry) -> list[str]:
        lines = []
        for name, value in sorted(entry.enum_values.items(), key=lambda x: x[1]):
            lines.append(f"%ev {entry.label:<40} {name:<20} {value}")
        return lines

    def _normalize_syntax(self, syntax: str) -> str:
        if syntax in SYNTAX_MAP.values():
            return syntax
        return SYNTAX_MAP.get(syntax, syntax)
