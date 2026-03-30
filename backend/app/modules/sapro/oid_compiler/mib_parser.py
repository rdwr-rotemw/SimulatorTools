import logging
import os
import re
import rarfile
import zipfile
from pathlib import Path
from typing import Optional

from pysmi.reader import FileReader
from pysmi.parser import SmiV1CompatParser
from pysmi.codegen import PySnmpCodeGen
from pysmi.compiler import MibCompiler as PysmiMibCompiler
from pysmi.writer import PyFileWriter
from pysnmp.smi import builder, view

from backend.app.modules.sapro.oid_compiler.constants import SYNTAX_MAP, ROWSTATUS_TCS, ENTRYSTATUS_TCS
from backend.app.modules.sapro.oid_compiler.models import AccessLevel, OidEntry

logger = logging.getLogger(__name__)

# Module name regex — handles leading whitespace
MODULE_NAME_RE = re.compile(r"^\s*(\S+)\s+DEFINITIONS\s*::=\s*BEGIN", re.MULTILINE)

# RFC-1215 defines the TRAP-TYPE macro (SMIv1). It fails to compile with pysmi
# and is not needed for OID extraction. Strip imports and definitions referencing it.
TRAP_IMPORT_RE = re.compile(r",?\s*TRAP-TYPE\s+FROM\s+RFC-1215\s*\n?")
TRAP_DEF_RE = re.compile(r"\w+\s+TRAP-TYPE\s+.*?::=\s*\d+", re.DOTALL)

# Minimal stub for IP-MIB — not included in Radware archives but implicitly
# required by pysmi's SMIv1→v2 conversion of RFC1213-MIB.
IP_MIB_STUB = """IP-MIB DEFINITIONS ::= BEGIN
IMPORTS
    MODULE-IDENTITY, OBJECT-TYPE, Integer32, Counter32, IpAddress
        FROM SNMPv2-SMI;

ipAddrTable OBJECT-TYPE
    SYNTAX      SEQUENCE OF IpAddrEntry
    MAX-ACCESS  not-accessible
    STATUS      current
    DESCRIPTION "The table of addressing information."
    ::= { ip 20 }

ipAddrEntry OBJECT-TYPE
    SYNTAX      IpAddrEntry
    MAX-ACCESS  not-accessible
    STATUS      current
    DESCRIPTION "An address entry."
    INDEX       { ipAdEntAddr }
    ::= { ipAddrTable 1 }

IpAddrEntry ::= SEQUENCE {
    ipAdEntAddr     IpAddress,
    ipAdEntIfIndex  Integer32,
    ipAdEntNetMask  IpAddress
}

ipAdEntAddr OBJECT-TYPE
    SYNTAX      IpAddress
    MAX-ACCESS  read-only
    STATUS      current
    DESCRIPTION "IP address."
    ::= { ipAddrEntry 1 }

ipAdEntIfIndex OBJECT-TYPE
    SYNTAX      Integer32
    MAX-ACCESS  read-only
    STATUS      current
    DESCRIPTION "Interface index."
    ::= { ipAddrEntry 2 }

ipAdEntNetMask OBJECT-TYPE
    SYNTAX      IpAddress
    MAX-ACCESS  read-only
    STATUS      current
    DESCRIPTION "Subnet mask."
    ::= { ipAddrEntry 3 }

ip OBJECT IDENTIFIER ::= { mib-2 4 }
mib-2 OBJECT IDENTIFIER ::= { mgmt 1 }
mgmt OBJECT IDENTIFIER ::= { internet 2 }
internet OBJECT IDENTIFIER ::= { iso org(3) dod(6) 1 }

END
"""


class MibParser:
    """Parse MIB files from a ZIP or RAR archive using pysmi/pysnmp."""

    # MIB files can have various extensions
    MIB_EXTENSIONS = (".mib", ".my", ".txt", ".asn", ".smi", ".mi1")

    def __init__(self, archive_path: str, work_dir: str):
        self.archive_path = archive_path
        self.work_dir = Path(work_dir)
        self.mib_dir = self.work_dir / "mibs"
        self.compiled_dir = self.work_dir / "compiled"
        self._mib_modules: list[tuple[str, str]] = []

    def parse(self) -> list[OidEntry]:
        self._extract_and_rename()
        logger.info(f"Extracted {len(self._mib_modules)} MIB modules from archive")

        self._compile_mibs()
        entries = self._load_compiled_mibs()

        logger.info(f"Parsed {len(entries)} OID entries")
        return entries

    def _extract_and_rename(self) -> None:
        """Extract archive and rename files to match their MIB module names."""
        self.mib_dir.mkdir(parents=True, exist_ok=True)

        # Detect format by magic bytes, not extension
        if zipfile.is_zipfile(self.archive_path):
            members = self._list_zip()
        else:
            members = self._list_rar()

        for original_name, content in members:
            match = MODULE_NAME_RE.search(content)
            if match:
                mod_name = match.group(1)
                # Skip RFC-1215 entirely — only contains TRAP-TYPE macro
                if mod_name == "RFC-1215":
                    continue
                # Strip TRAP-TYPE imports and definitions from all files
                content = TRAP_IMPORT_RE.sub("\n", content)
                content = TRAP_DEF_RE.sub("", content)
                target = self.mib_dir / f"{mod_name}.mib"
                target.write_text(content, encoding="utf-8")
                self._mib_modules.append((original_name, mod_name))
            else:
                # No module definition found — write with original name
                filename = os.path.basename(original_name)
                target = self.mib_dir / filename
                target.write_text(content, encoding="utf-8")
                self._mib_modules.append((original_name, Path(filename).stem))

        # Add IP-MIB stub if not present in the archive
        if not (self.mib_dir / "IP-MIB.mib").exists():
            (self.mib_dir / "IP-MIB.mib").write_text(IP_MIB_STUB, encoding="utf-8")

    def _list_zip(self) -> list[tuple[str, str]]:
        results = []
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                filename = os.path.basename(member)
                if filename.lower().endswith(self.MIB_EXTENSIONS):
                    content = zf.read(member).decode("utf-8", errors="ignore")
                    results.append((filename, content))
        return results

    def _list_rar(self) -> list[tuple[str, str]]:
        results = []
        with rarfile.RarFile(self.archive_path, "r") as rf:
            for member in rf.namelist():
                if member.endswith("/"):
                    continue
                filename = os.path.basename(member)
                if filename.lower().endswith(self.MIB_EXTENSIONS):
                    content = rf.read(member).decode("utf-8", errors="ignore")
                    results.append((filename, content))
        return results

    def _compile_mibs(self) -> None:
        """Compile MIB sources to Python using pysmi."""
        self.compiled_dir.mkdir(parents=True, exist_ok=True)

        module_names = [f.stem for f in self.mib_dir.glob("*.mib")]

        # Single-pass compilation: compile all modules at once with one compiler.
        # pysmi resolves dependencies internally. We delete any stale .py first
        # to prevent the "unprocessed" staleness check from skipping modules.
        for f in self.compiled_dir.glob("*.py"):
            f.unlink()

        compiler = PysmiMibCompiler(
            SmiV1CompatParser(),
            PySnmpCodeGen(),
            PyFileWriter(str(self.compiled_dir)),
        )
        compiler.add_sources(FileReader(str(self.mib_dir)))

        try:
            status = compiler.compile(*module_names)
        except Exception as e:
            logger.error(f"MIB compilation failed: {e}")
            status = {}

        compiled = {n for n, r in status.items() if "compiled" in str(r).lower()}
        logger.info(f"Compiled {len(compiled)} modules in single pass")

        # If single-pass missed some (due to dependency order), retry individually
        remaining = set(module_names) - compiled
        if remaining:
            for mod in list(remaining):
                existing = self.compiled_dir / f"{mod}.py"
                if existing.exists():
                    existing.unlink()
                retry_compiler = PysmiMibCompiler(
                    SmiV1CompatParser(),
                    PySnmpCodeGen(),
                    PyFileWriter(str(self.compiled_dir)),
                )
                retry_compiler.add_sources(FileReader(str(self.mib_dir)))
                try:
                    retry_status = retry_compiler.compile(mod)
                    for name, result in retry_status.items():
                        if "compiled" in str(result).lower():
                            compiled.add(name)
                            remaining.discard(name)
                except Exception:
                    pass

            logger.info(f"After retries: {len(compiled)} modules compiled")

        failed = set(module_names) - compiled
        if failed:
            logger.warning(f"Could not compile {len(failed)} modules: {sorted(failed)}")

    def _load_compiled_mibs(self) -> list[OidEntry]:
        """Load compiled .py MIB modules into pysnmp and walk the OID tree."""
        mib_builder = builder.MibBuilder()
        mib_builder.addMibSources(builder.DirMibSource(str(self.compiled_dir)))

        compiled_modules = [f.stem for f in self.compiled_dir.glob("*.py")]
        loaded_modules = []

        for mod in compiled_modules:
            try:
                mib_builder.loadModules(mod)
                loaded_modules.append(mod)
            except Exception as e:
                logger.debug(f"Could not load module {mod}: {e}")

        logger.info(f"Loaded {len(loaded_modules)} compiled modules into pysnmp")

        if not loaded_modules:
            return []

        mib_view = view.MibViewController(mib_builder)
        entries: list[OidEntry] = []

        try:
            oid, label, suffix = mib_view.getFirstNodeName()
        except Exception:
            return entries

        while True:
            try:
                oid_str = ".".join(str(x) for x in oid)
                label_str = label[-1] if isinstance(label, tuple) else str(label)

                node_obj = None
                try:
                    mod_name, sym_name, _ = mib_view.getNodeLocation(oid)
                    if sym_name:
                        syms = mib_builder.importSymbols(mod_name, sym_name)
                        node_obj = syms[0] if syms else None
                except Exception:
                    pass

                entry = self._build_entry(oid_str, label_str, node_obj)
                if entry:
                    entries.append(entry)

                oid, label, suffix = mib_view.getNextNodeName(oid)
            except Exception:
                break

        entries = self._determine_table_relationships(entries)
        entries.sort(key=lambda e: [int(x) for x in e.oid.split(".")])
        return entries

    # pysnmp node types that represent actual SNMP OBJECT-TYPE definitions
    _VALID_NODE_TYPES = {"MibScalar", "MibTableColumn", "MibTableRow"}

    def _build_entry(self, oid_str: str, label: str, node_obj) -> Optional[OidEntry]:
        if node_obj is None:
            return None

        # Skip structural/container nodes (MibTree, ObjectIdentity, ModuleIdentity, MibTable)
        node_type = type(node_obj).__name__
        if node_type not in self._VALID_NODE_TYPES:
            return None

        try:
            syntax = self._get_syntax(node_obj)
            access = self._get_access(node_obj)
            enum_values = self._extract_enum_values(node_obj)
            min_range, max_range = self._extract_range(node_obj)

            # For enum columns without specific constraints, derive range from enum values
            if enum_values and (min_range is None or (min_range == -2147483648 and max_range == 2147483647)):
                enum_vals = list(enum_values.values())
                min_range = min(enum_vals)
                max_range = max(enum_vals)
            default_value = self._get_default_value(node_obj)
            index_columns = self._get_index_columns(node_obj)
            description = self._get_description(node_obj)
            display_hint = self._get_display_hint(node_obj)

            normalized_syntax = SYNTAX_MAP.get(syntax, syntax)
            if normalized_syntax == syntax and syntax not in SYNTAX_MAP.values():
                logger.warning(f"Unknown syntax type '{syntax}' for {label} — passing through as-is")
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
                default_value=default_value,
                description=description,
                mib_module="",
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
            return type(syntax_obj).__name__
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
            subtype_spec = getattr(syntax_obj, "subtypeSpec", None)
            if subtype_spec is None:
                return None, None

            # pysnmp uses ConstraintsIntersection containing ValueSizeConstraint
            # or ValueRangeConstraint objects. Walk through all constraints
            # and find the tightest (most specific) range.
            min_val = None
            max_val = None

            # Try iterating constraints (ConstraintsIntersection is iterable)
            constraints = []
            try:
                for constraint in subtype_spec:
                    constraints.append(constraint)
            except TypeError:
                constraints = [subtype_spec]

            for constraint in constraints:
                # ValueSizeConstraint and ValueRangeConstraint have similar structure
                c_min = getattr(constraint, "start", None)
                c_max = getattr(constraint, "stop", None)
                if c_min is None or c_max is None:
                    continue
                c_min = int(c_min)
                c_max = int(c_max)
                # Take the tightest constraint
                if min_val is None or c_min > min_val:
                    min_val = c_min
                if max_val is None or c_max < max_val:
                    max_val = c_max

            if min_val is not None and max_val is not None:
                return min_val, max_val
        except Exception:
            pass
        return None, None

    def _get_default_value(self, node_obj) -> Optional[str]:
        """Extract DEFVAL from the MIB node if present."""
        try:
            syntax_obj = node_obj.getSyntax()
            if syntax_obj is None:
                return None
            val = syntax_obj.prettyPrint()
            if val and val != "None" and val != "":
                # For enum names like 'nonVolatile', resolve to numeric value
                named_values = getattr(syntax_obj, "namedValues", None)
                if named_values and val in dict(named_values.items()):
                    return str(dict(named_values.items())[val])
                return str(val)
        except Exception:
            pass
        return None

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

            parts = entry.oid.rsplit(".", 1)
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
            # Determine how many index columns this table has
            num_index_cols = 0
            if columns and columns[0].index_columns:
                # index_columns from pysnmp contains OID fragments like ['1'] or ['1', '2']
                num_index_cols = len(columns[0].index_columns)
            # Default to 1 index column if we couldn't determine
            if num_index_cols == 0:
                num_index_cols = 1

            for idx, col in enumerate(columns, 1):
                col.index_type = f"C{idx}"
                # Index columns should be NA (not-accessible).
                # pysnmp often returns 'readonly' for not-accessible index columns.
                if idx <= num_index_cols:
                    col.access = AccessLevel.NA

        return entries

    def get_mib_modules(self) -> list[tuple[str, str]]:
        return self._mib_modules
