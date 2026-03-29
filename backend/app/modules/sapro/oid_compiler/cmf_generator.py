import logging
from pathlib import Path

from backend.app.modules.sapro.oid_compiler.constants import DEFAULT_RANGES, SYNTAX_MAP
from backend.app.modules.sapro.oid_compiler.models import OidEntry

logger = logging.getLogger(__name__)


class CmfGenerator:
    """Generate SAPRO .cmf files from parsed MIB data."""

    def __init__(self, oid_entries: list[OidEntry]):
        self.entries = oid_entries

    def generate(self, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        sorted_entries = sorted(
            self.entries,
            key=lambda e: [int(x) for x in e.oid.split(".")],
        )

        lines: list[str] = []

        # OID entry lines
        for entry in sorted_entries:
            if entry.is_table_entry:
                continue
            line = self._format_entry_line(entry)
            if line:
                lines.append(line)

        # Enum value definitions
        enum_lines: list[str] = []
        for entry in sorted_entries:
            if entry.has_enum and entry.enum_values:
                enum_lines.extend(self._format_enum_lines(entry))

        if enum_lines:
            lines.append("")
            lines.extend(enum_lines)

        content = "\n".join(lines) + "\n"
        output.write_text(content, encoding="utf-8")
        logger.info(f"Generated CMF file: {output} ({len(sorted_entries)} entries)")
        return str(output)

    def _format_entry_line(self, entry: OidEntry) -> str:
        syntax = self._normalize_syntax(entry.syntax)
        access = entry.access.value if entry.access.value != "Create" else "RW"
        index_type = entry.index_type
        range_str = self._compute_range(entry, syntax)
        enum_flag = entry.enum_flag

        return f"{entry.oid} {entry.label} {syntax} {access} {index_type} {range_str} {enum_flag}"

    def _format_enum_lines(self, entry: OidEntry) -> list[str]:
        lines = []
        for name, value in sorted(entry.enum_values.items(), key=lambda x: x[1]):
            lines.append(f"%ev {entry.label} {name} {value}")
        return lines

    def _normalize_syntax(self, syntax: str) -> str:
        if syntax in SYNTAX_MAP.values():
            return syntax
        return SYNTAX_MAP.get(syntax, syntax)

    def _compute_range(self, entry: OidEntry, normalized_syntax: str) -> str:
        if entry.min_range is not None and entry.max_range is not None:
            return f"({entry.min_range},{entry.max_range})"

        if normalized_syntax in DEFAULT_RANGES:
            min_val, max_val = DEFAULT_RANGES[normalized_syntax]
            return f"({min_val},{max_val})"

        return "(0,0)"
