import logging
import os
import zipfile
from pathlib import Path
from typing import Optional

from pysmi.reader import FileReader
from pysmi.parser import SmiV2Parser
from pysmi.codegen import PySnmpCodeGen
from pysmi.compiler import MibCompiler as PysmiMibCompiler
from pysmi.writer import PyFileWriter
from pysnmp.smi import builder, view

from backend.app.modules.sapro.oid_compiler.constants import SYNTAX_MAP, ROWSTATUS_TCS, ENTRYSTATUS_TCS
from backend.app.modules.sapro.oid_compiler.models import AccessLevel, OidEntry

logger = logging.getLogger(__name__)


class MibParser:
    """Parse MIB files from a ZIP archive using pysmi/pysnmp."""

    def __init__(self, zip_path: str, work_dir: str):
        self.zip_path = zip_path
        self.work_dir = Path(work_dir)
        self.mib_dir = self.work_dir / "mibs"
        self.compiled_dir = self.work_dir / "compiled"
        self._mib_modules: list[tuple[str, str]] = []

    def parse(self) -> list[OidEntry]:
        mib_files = self._extract_zip()
        logger.info(f"Extracted {len(mib_files)} MIB files from ZIP")

        self._compile_mibs(mib_files)
        entries = self._load_compiled_mibs()
        entries = self._determine_table_relationships(entries)
        entries.sort(key=lambda e: [int(x) for x in e.oid.split(".")])

        logger.info(f"Parsed {len(entries)} OID entries")
        return entries

    def _extract_zip(self) -> list[str]:
        self.mib_dir.mkdir(parents=True, exist_ok=True)
        mib_files = []

        with zipfile.ZipFile(self.zip_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                filename = os.path.basename(member)
                if filename.lower().endswith(".mib") or filename.lower().endswith(".my"):
                    target = self.mib_dir / filename
                    with zf.open(member) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    mib_files.append(str(target))

        return mib_files

    def _compile_mibs(self, mib_files: list[str]) -> None:
        self.compiled_dir.mkdir(parents=True, exist_ok=True)

        mib_compiler = PysmiMibCompiler(
            SmiV2Parser(),
            PySnmpCodeGen(),
            PyFileWriter(str(self.compiled_dir)),
        )
        mib_compiler.addSources(FileReader(str(self.mib_dir)))

        module_names = []
        for mib_file in mib_files:
            module_name = Path(mib_file).stem
            module_names.append(module_name)
            self._mib_modules.append((Path(mib_file).name, module_name))

        status = mib_compiler.compile(*module_names)
        for name, result in status.items():
            logger.debug(f"MIB compile {name}: {result}")

    def _load_compiled_mibs(self) -> list[OidEntry]:
        mib_builder = builder.MibBuilder()
        mib_builder.addMibSources(builder.DirMibSource(str(self.compiled_dir)))

        module_names = [mod[1] for mod in self._mib_modules]
        for module_name in module_names:
            try:
                mib_builder.loadModules(module_name)
            except Exception as e:
                logger.warning(f"Could not load MIB module {module_name}: {e}")

        mib_view = view.MibViewController(mib_builder)
        entries = []

        for modname in module_names:
            try:
                oid, label, suffix = mib_view.getFirstNodeName(modname)
            except Exception:
                continue

            while True:
                try:
                    node_name = oid
                    oid_str = ".".join(str(x) for x in node_name)
                    mib_node = mib_builder.importSymbols(modname, label)

                    entry = self._node_to_oid_entry(mib_node, oid_str, label, modname)
                    if entry:
                        entries.append(entry)

                    oid, label, suffix = mib_view.getNextNodeName(node_name)
                except Exception:
                    break

        return entries

    def _node_to_oid_entry(
        self, mib_node, oid_str: str, label: str, module_name: str
    ) -> Optional[OidEntry]:
        try:
            node_obj = mib_node[0] if isinstance(mib_node, tuple) else mib_node

            syntax = self._get_syntax(node_obj)
            access = self._get_access(node_obj)
            enum_values = self._extract_enum_values(node_obj)
            min_range, max_range = self._extract_range(node_obj)
            index_columns = self._get_index_columns(node_obj)
            description = self._get_description(node_obj)
            display_hint = self._get_display_hint(node_obj)

            original_syntax = syntax
            normalized_syntax = SYNTAX_MAP.get(syntax, syntax)

            is_table_entry = hasattr(node_obj, "getIndexNames") and bool(index_columns)

            return OidEntry(
                oid=oid_str,
                label=label,
                syntax=normalized_syntax,
                access=access,
                is_table_entry=is_table_entry,
                index_columns=index_columns,
                min_range=min_range,
                max_range=max_range,
                has_enum=bool(enum_values),
                enum_values=enum_values,
                description=description,
                mib_module=module_name,
                display_hint=display_hint,
                enum_flag="e" if enum_values else "d",
            )
        except Exception as e:
            logger.debug(f"Could not process node {label} ({oid_str}): {e}")
            return None

    def _get_syntax(self, node_obj) -> str:
        try:
            syntax_obj = node_obj.getSyntax()
            if syntax_obj is None:
                return "OctetString"
            type_name = type(syntax_obj).__name__
            if hasattr(syntax_obj, "prettyPrint"):
                named_values = getattr(syntax_obj, "namedValues", None)
                if named_values and "RowStatus" in type(syntax_obj).__mro__.__class__.__name__:
                    return "RowStatus"
            return type_name
        except Exception:
            return "OctetString"

    def _get_access(self, node_obj) -> AccessLevel:
        try:
            access = node_obj.getMaxAccess()
            access_map = {
                "readonly": AccessLevel.RO,
                "read-only": AccessLevel.RO,
                "readwrite": AccessLevel.RW,
                "read-write": AccessLevel.RW,
                "read-create": AccessLevel.CREATE,
                "readcreate": AccessLevel.CREATE,
                "writeonly": AccessLevel.WO,
                "write-only": AccessLevel.WO,
                "notaccessible": AccessLevel.NA,
                "not-accessible": AccessLevel.NA,
                "accessiblefornotify": AccessLevel.RO,
                "accessible-for-notify": AccessLevel.RO,
            }
            return access_map.get(access.lower(), AccessLevel.RO) if access else AccessLevel.RO
        except Exception:
            return AccessLevel.RO

    def _extract_enum_values(self, node_obj) -> dict[str, int]:
        try:
            syntax_obj = node_obj.getSyntax()
            if syntax_obj is None:
                return {}
            named_values = getattr(syntax_obj, "namedValues", None)
            if named_values:
                return {str(name): int(value) for name, value in named_values.items()}
        except Exception:
            pass
        return {}

    def _extract_range(self, node_obj) -> tuple[Optional[int], Optional[int]]:
        try:
            syntax_obj = node_obj.getSyntax()
            if syntax_obj is None:
                return None, None
            subtypes = getattr(syntax_obj, "subtypeSpec", None)
            if subtypes:
                constraints = getattr(subtypes, "getValueRange", None)
                if constraints:
                    min_val, max_val = constraints()
                    return int(min_val), int(max_val)
        except Exception:
            pass
        return None, None

    def _get_index_columns(self, node_obj) -> list[str]:
        try:
            if hasattr(node_obj, "getIndexNames"):
                index_names = node_obj.getIndexNames()
                if index_names:
                    return [str(idx[0]) if isinstance(idx, tuple) else str(idx) for idx in index_names]
        except Exception:
            pass
        return []

    def _get_description(self, node_obj) -> str:
        try:
            return str(node_obj.getDescription()) if hasattr(node_obj, "getDescription") else ""
        except Exception:
            return ""

    def _get_display_hint(self, node_obj) -> Optional[str]:
        try:
            syntax_obj = node_obj.getSyntax()
            if syntax_obj and hasattr(syntax_obj, "displayHint"):
                return str(syntax_obj.displayHint)
        except Exception:
            pass
        return None

    def _determine_table_relationships(self, entries: list[OidEntry]) -> list[OidEntry]:
        entry_objects: dict[str, OidEntry] = {}
        for e in entries:
            if e.is_table_entry:
                entry_objects[e.label] = e

        table_entries_by_oid: dict[str, OidEntry] = {}
        for e in entry_objects.values():
            table_entries_by_oid[e.oid] = e

        for entry in entries:
            if entry.is_table_entry:
                continue

            entry_oid = entry.oid
            parts = entry_oid.rsplit(".", 1)
            if len(parts) < 2:
                continue
            parent_oid = parts[0]

            if parent_oid in table_entries_by_oid:
                parent = table_entries_by_oid[parent_oid]
                entry.is_table_column = True
                entry.entry_name = parent.label
                table_name = parent.label.replace("Entry", "Table")
                entry.table_name = table_name
                entry.index_columns = parent.index_columns

        # Assign column index types (C1, C2, ...)
        table_columns: dict[str, list[OidEntry]] = {}
        for e in entries:
            if e.is_table_column and e.table_name:
                table_columns.setdefault(e.table_name, []).append(e)

        for table_name, columns in table_columns.items():
            columns.sort(key=lambda c: [int(x) for x in c.oid.split(".")])
            for idx, col in enumerate(columns, 1):
                col.index_type = f"C{idx}"

        return entries

    def get_mib_modules(self) -> list[tuple[str, str]]:
        return self._mib_modules
