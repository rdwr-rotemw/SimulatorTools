import logging

from backend.app.modules.sapro.oid_compiler.constants import SYNTAX_MAP
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
            if entry.is_table_entry:
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
        """Generate %en lines for table entries and structural nodes."""
        lines: list[str] = []
        for entry in sorted_entries:
            if entry.is_table_entry:
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

            # Index columns are those with access=NA in this table
            index_labels = [
                col.label for col in table_cols
                if col.access == AccessLevel.NA
            ]

            if not index_labels:
                continue

            # Format index names with * prefix for string types
            formatted_indices = []
            for idx_label in index_labels:
                idx_entry = label_map.get(idx_label)
                if idx_entry and idx_entry.syntax in STRING_INDEX_SYNTAXES:
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
        if entry.min_range is not None and entry.max_range is not None:
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

    def _format_enum_lines(self, entry: OidEntry) -> list[str]:
        lines = []
        for name, value in sorted(entry.enum_values.items(), key=lambda x: x[1]):
            lines.append(f"%ev {entry.label:<40} {name:<20} {value}")
        return lines

    def _normalize_syntax(self, syntax: str) -> str:
        if syntax in SYNTAX_MAP.values():
            return syntax
        return SYNTAX_MAP.get(syntax, syntax)
