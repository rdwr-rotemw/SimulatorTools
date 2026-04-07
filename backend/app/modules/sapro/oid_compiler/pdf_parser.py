import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber
import pypdfium2 as pdfium

from backend.app.modules.sapro.oid_compiler.models import PdfColumnInfo, PdfTableInfo

logger = logging.getLogger(__name__)

# Match "Version X.X.X.X" on the cover page (has the full minor version)
COVER_VERSION_PATTERN = re.compile(r"^Version\s+([\d.]+)", re.MULTILINE)
# Fallback: match from footer/header text on other pages
FOOTER_VERSION_PATTERN = re.compile(r"DefensePro.*?version\s+([\d.]+)", re.IGNORECASE)
OID_PATTERN = re.compile(r"^\.?\d+(\.\d+)+$")

# PDF table columns are at fixed positions in a 21-column layout.
# Real fields: OID(0), Label(3), Syntax(6), TableName(9), Index(12), Access(15), Description(18)
FIELD_INDICES = [0, 3, 6, 9, 12, 15, 18]

# Cache directory for parsed PDF data
CACHE_DIR = Path(__file__).parent / ".pdf_cache"
# Bump this when parsing logic changes to invalidate old caches
CACHE_VERSION = 2


class PdfParser:
    """Parse DefensePro OIDs PDF to extract table structure information.

    Uses pypdfium2 for fast version extraction and file hashing.
    Uses pdfplumber for accurate table extraction (slow but correct).
    Caches results so repeated compilations with the same PDF are instant.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._version: Optional[str] = None

    def parse(self) -> list[PdfTableInfo]:
        # Extract version quickly with pypdfium2
        self._extract_version_fast()

        # Check cache
        file_hash = self._hash_file()
        cached = self._load_cache(file_hash)
        if cached is not None:
            logger.info(f"Loaded {len(cached)} tables from PDF cache")
            return cached

        # Full extraction with pdfplumber
        all_columns = self._extract_with_pdfplumber()
        logger.info(f"Extracted {len(all_columns)} column entries from PDF")

        tables = self._group_by_table(all_columns)
        logger.info(f"Grouped into {len(tables)} tables")

        # Save to cache
        self._save_cache(file_hash, tables)
        return tables

    def get_version(self) -> str:
        return self._version or ""

    def _extract_version_fast(self) -> None:
        """Extract version using pypdfium2 (sub-second)."""
        try:
            pdf = pdfium.PdfDocument(self.pdf_path)
            cover_text = pdf[0].get_textpage().get_text_range()
            match = COVER_VERSION_PATTERN.search(cover_text)
            if match:
                self._version = match.group(1)
                logger.info(f"Detected DefensePro version from cover: {self._version}")
                return

            for i in range(min(5, len(pdf))):
                text = pdf[i].get_textpage().get_text_range()
                match = FOOTER_VERSION_PATTERN.search(text)
                if match:
                    self._version = match.group(1)
                    logger.info(f"Detected DefensePro version from header: {self._version}")
                    return
        except Exception as e:
            logger.warning(f"pypdfium2 version extraction failed: {e}")

    def _hash_file(self) -> str:
        """Compute SHA256 hash of the PDF file for caching."""
        sha = hashlib.sha256()
        with open(self.pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()[:16]

    def _load_cache(self, file_hash: str) -> Optional[list[PdfTableInfo]]:
        """Load cached parsing results if available."""
        cache_file = CACHE_DIR / f"v{CACHE_VERSION}_{file_hash}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            tables = []
            for t in data:
                columns = [PdfColumnInfo(**c) for c in t["columns"]]
                tables.append(PdfTableInfo(
                    table_name=t["table_name"],
                    entry_name=t["entry_name"],
                    columns=columns,
                    index_columns=t["index_columns"],
                ))
            return tables
        except Exception as e:
            logger.warning(f"Failed to load PDF cache: {e}")
            return None

    def _save_cache(self, file_hash: str, tables: list[PdfTableInfo]) -> None:
        """Save parsing results to cache."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = [t.model_dump() for t in tables]
            cache_file = CACHE_DIR / f"v{CACHE_VERSION}_{file_hash}.json"
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            logger.info(f"Saved PDF cache: {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save PDF cache: {e}")

    def _extract_with_pdfplumber(self) -> list[PdfColumnInfo]:
        """Full table extraction with pdfplumber (slow but accurate)."""
        all_columns: list[PdfColumnInfo] = []

        with pdfplumber.open(self.pdf_path) as pdf:
            # Skip first 5 pages (cover, TOC, intro — no OID tables)
            for page_num, page in enumerate(pdf.pages[5:], start=5):
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row is None:
                                continue
                            col_info = self._parse_row(row)
                            if col_info:
                                all_columns.append(col_info)
                except Exception as e:
                    logger.warning(f"Failed to parse page {page_num + 1}: {e}")

        return all_columns

    def _parse_row(self, row: list) -> Optional[PdfColumnInfo]:
        """Parse a PDF table row using fixed column positions."""
        if len(row) < 19:
            return None

        fields = [row[i] if i < len(row) else None for i in FIELD_INDICES]
        oid = self._clean_identifier(fields[0])
        label = self._clean_identifier(fields[1])
        syntax = self._clean_identifier(fields[2])
        table_name = self._clean_identifier(fields[3])
        index_name = self._clean_index_field(fields[4])
        access = self._clean_identifier(fields[5])
        description = self._clean_text(fields[6])

        if oid.upper() == "OID" or label.upper() == "LABEL":
            return None

        oid = oid.lstrip(".")
        if not OID_PATTERN.match("." + oid):
            return None

        if table_name.upper() in ("NO TABLE", "NOTABLE", "NOT TABLE"):
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

    def _clean_identifier(self, value) -> str:
        """Clean an identifier field — remove all whitespace."""
        if value is None:
            return ""
        return re.sub(r"\s+", "", str(value))

    def _clean_index_field(self, value) -> str:
        """Clean the index field, preserving separation between multiple index names."""
        if value is None:
            return ""
        return re.sub(r"\s+", "", str(value))

    def _clean_text(self, value) -> str:
        """Clean a text field — collapse whitespace but keep words separated."""
        if value is None:
            return ""
        return " ".join(str(value).split())

    def _group_by_table(self, columns: list[PdfColumnInfo]) -> list[PdfTableInfo]:
        table_map: dict[str, list[PdfColumnInfo]] = {}
        for col in columns:
            table_map.setdefault(col.table_name, []).append(col)

        tables: list[PdfTableInfo] = []
        for table_name, cols in table_map.items():
            entry_name = table_name.replace("Table", "Entry")

            index_columns: list[str] = []
            for col in cols:
                if col.index_name:
                    index_columns = self._resolve_index_names(
                        col.index_name, [c.label for c in cols]
                    )
                    break

            tables.append(PdfTableInfo(
                table_name=table_name,
                entry_name=entry_name,
                columns=cols,
                index_columns=index_columns,
            ))

        return tables

    def _resolve_index_names(self, concatenated: str, column_labels: list[str]) -> list[str]:
        """Resolve index names from a concatenated string by matching against column labels."""
        if not concatenated:
            return []

        remaining = concatenated
        found: list[str] = []
        sorted_labels = sorted(column_labels, key=len, reverse=True)

        while remaining:
            matched = False
            for label in sorted_labels:
                if remaining.startswith(label):
                    found.append(label)
                    remaining = remaining[len(label):]
                    matched = True
                    break
            if not matched:
                if remaining:
                    found.append(remaining)
                break

        return found
