import logging
import re
from typing import Optional

import pdfplumber

from backend.app.modules.sapro.oid_compiler.models import PdfColumnInfo, PdfTableInfo

logger = logging.getLogger(__name__)

# Header pattern to detect table header rows in the PDF
HEADER_PATTERN = re.compile(r"OID\s+Label\s+Syntax\s+Table\s*Name\s+Index\s+Access\s+Description", re.IGNORECASE)

# Version pattern from PDF title
VERSION_PATTERN = re.compile(r"DefensePro.*?version\s+([\d.]+)", re.IGNORECASE)


class PdfParser:
    """Parse DefensePro OIDs PDF to extract table structure information."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._version: Optional[str] = None

    def parse(self) -> list[PdfTableInfo]:
        all_columns: list[PdfColumnInfo] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            if self._version is None:
                self._extract_version_from_pages(pdf)

            for page_num, page in enumerate(pdf.pages):
                try:
                    columns = self._parse_page(page)
                    all_columns.extend(columns)
                except Exception as e:
                    logger.warning(f"Failed to parse page {page_num + 1}: {e}")

        logger.info(f"Extracted {len(all_columns)} column entries from PDF")

        tables = self._group_by_table(all_columns)
        logger.info(f"Grouped into {len(tables)} tables")
        return tables

    def get_version(self) -> str:
        return self._version or ""

    def _extract_version_from_pages(self, pdf) -> None:
        for page in pdf.pages[:3]:
            text = page.extract_text() or ""
            match = VERSION_PATTERN.search(text)
            if match:
                self._version = match.group(1)
                logger.info(f"Detected DefensePro version: {self._version}")
                return

    def _parse_page(self, page) -> list[PdfColumnInfo]:
        columns: list[PdfColumnInfo] = []

        # Try table extraction first
        tables = page.extract_tables()
        if tables:
            for table in tables:
                for row in table:
                    if row is None:
                        continue
                    col_info = self._parse_table_row(row)
                    if col_info:
                        columns.append(col_info)
            return columns

        # Fallback: text-mode parsing with layout
        text = page.extract_text(layout=True) or ""
        columns.extend(self._parse_text_layout(text))
        return columns

    def _parse_table_row(self, row: list) -> Optional[PdfColumnInfo]:
        if len(row) < 7:
            return None

        cleaned = [str(cell).strip() if cell else "" for cell in row]
        oid, label, syntax, table_name, index_name, access, description = (
            cleaned[0], cleaned[1], cleaned[2], cleaned[3], cleaned[4], cleaned[5],
            " ".join(cleaned[6:]),
        )

        # Skip header rows
        if oid.upper() == "OID" or label.upper() == "LABEL":
            return None

        # Skip scalar OIDs
        if not table_name or table_name.upper() in ("NO TABLE", "NOT TABLE", ""):
            return None

        # Must have a valid OID pattern
        if not re.match(r"^[\d.]+$", oid):
            return None

        return PdfColumnInfo(
            oid=oid,
            label=label,
            syntax=syntax,
            table_name=table_name,
            index_name=index_name,
            access=access,
            description=description,
        )

    def _parse_text_layout(self, text: str) -> list[PdfColumnInfo]:
        columns: list[PdfColumnInfo] = []
        lines = text.split("\n")

        col_positions: Optional[list[int]] = None

        for line in lines:
            header_match = HEADER_PATTERN.search(line)
            if header_match:
                col_positions = self._detect_column_positions(line)
                continue

            if col_positions is None:
                continue

            if not line.strip():
                continue

            col_info = self._parse_fixed_width_line(line, col_positions)
            if col_info:
                columns.append(col_info)

        return columns

    def _detect_column_positions(self, header_line: str) -> list[int]:
        positions = []
        for keyword in ["OID", "Label", "Syntax", "Table", "Index", "Access", "Description"]:
            idx = header_line.lower().find(keyword.lower())
            if idx >= 0:
                positions.append(idx)
        return sorted(positions)

    def _parse_fixed_width_line(self, line: str, positions: list[int]) -> Optional[PdfColumnInfo]:
        if len(positions) < 7:
            return None

        fields = []
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(line)
            fields.append(line[pos:end].strip())

        if len(fields) < 7:
            return None

        oid, label, syntax, table_name, index_name, access, description = (
            fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6],
        )

        if not re.match(r"^[\d.]+$", oid):
            return None

        if not table_name or table_name.upper() in ("NO TABLE", "NOT TABLE", ""):
            return None

        return PdfColumnInfo(
            oid=oid,
            label=label,
            syntax=syntax,
            table_name=table_name,
            index_name=index_name,
            access=access,
            description=description,
        )

    def _group_by_table(self, columns: list[PdfColumnInfo]) -> list[PdfTableInfo]:
        table_map: dict[str, list[PdfColumnInfo]] = {}
        for col in columns:
            table_map.setdefault(col.table_name, []).append(col)

        tables: list[PdfTableInfo] = []
        for table_name, cols in table_map.items():
            # Derive entry name
            entry_name = table_name.replace("Table", "Entry")

            # Determine index columns from the first column's index_name field
            index_columns: list[str] = []
            for col in cols:
                if col.index_name:
                    for idx_name in re.split(r"[,\s]+", col.index_name):
                        idx_name = idx_name.strip()
                        if idx_name and idx_name not in index_columns:
                            index_columns.append(idx_name)
                    break

            tables.append(PdfTableInfo(
                table_name=table_name,
                entry_name=entry_name,
                columns=cols,
                index_columns=index_columns,
            ))

        return tables
