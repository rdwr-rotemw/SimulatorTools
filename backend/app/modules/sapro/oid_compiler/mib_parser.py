import logging
import os
import re
import rarfile
import zipfile
from pathlib import Path
from typing import Optional

from pysmi.parser.smi import parserFactory

from backend.app.modules.sapro.oid_compiler.constants import SYNTAX_MAP, FIXED_SIZE_TYPES
from backend.app.modules.sapro.oid_compiler.models import AccessLevel, OidEntry

logger = logging.getLogger(__name__)

MODULE_NAME_RE = re.compile(r"^\s*(\S+)\s+DEFINITIONS\s*::=\s*BEGIN", re.MULTILINE)
TRAP_IMPORT_RE = re.compile(r",?\s*TRAP-TYPE\s+FROM\s+RFC-1215\s*\n?")
TRAP_DEF_RE = re.compile(r"\w+\s+TRAP-TYPE\s+.*?::=\s*\d+", re.DOTALL)

# Well-known base OIDs for resolving relative references
WELL_KNOWN_OIDS = {
    "iso": "1",
    "org": "1.3",
    "dod": "1.3.6",
    "internet": "1.3.6.1",
    "directory": "1.3.6.1.1",
    "mgmt": "1.3.6.1.2",
    "mib-2": "1.3.6.1.2.1",
    "system": "1.3.6.1.2.1.1",
    "interfaces": "1.3.6.1.2.1.2",
    "ip": "1.3.6.1.2.1.4",
    "transmission": "1.3.6.1.2.1.10",
    "snmp": "1.3.6.1.2.1.11",
    "experimental": "1.3.6.1.3",
    "private": "1.3.6.1.4",
    "enterprises": "1.3.6.1.4.1",
    "snmpV2": "1.3.6.1.6",
    "snmpModules": "1.3.6.1.6.3",
    "snmpMIB": "1.3.6.1.6.3.1",
    "zeroDotZero": "0.0",
}

# Well-known textual convention enum values that pysmi can't extract
# from inline syntax (they're defined in imported TC modules).
TC_ENUM_VALUES = {
    "RowStatus": {
        "active": 1, "notInService": 2, "notReady": 3,
        "createAndGo": 4, "createAndWait": 5, "destroy": 6,
    },
    "EntryStatus": {
        "valid": 1, "createRequest": 2, "underCreation": 3, "invalid": 4,
    },
    "TruthValue": {
        "true": 1, "false": 2,
    },
    "StorageType": {
        "other": 1, "volatile": 2, "nonVolatile": 3,
        "permanent": 4, "readOnly": 5,
    },
}

ACCESS_MAP = {
    "read-only": AccessLevel.RO,
    "readonly": AccessLevel.RO,
    "read-write": AccessLevel.RW,
    "readwrite": AccessLevel.RW,
    "read-create": AccessLevel.CREATE,
    "readcreate": AccessLevel.CREATE,
    "write-only": AccessLevel.WO,
    "writeonly": AccessLevel.WO,
    "not-accessible": AccessLevel.NA,
    "notaccessible": AccessLevel.NA,
    "accessible-for-notify": AccessLevel.RO,
}

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
    """Parse MIB files using pysmi's parser for raw AST data.

    Uses pysmi's SmiParser directly instead of pysnmp to get MIB data
    exactly as written — access levels, SIZE constraints, DEFVAL, and
    IMPLIED flags are preserved without SNMP protocol interpretation.
    """

    MIB_EXTENSIONS = (".mib", ".my", ".txt", ".asn", ".smi", ".mi1")

    def __init__(self, archive_path: str, work_dir: str):
        self.archive_path = archive_path
        self.work_dir = Path(work_dir)
        self.mib_dir = self.work_dir / "mibs"
        self._mib_modules: list[tuple[str, str]] = []
        # OID resolution: name -> absolute OID string
        self._oid_map: dict[str, str] = dict(WELL_KNOWN_OIDS)
        # Enum definitions: type_name -> {name: value}
        self._enum_defs: dict[str, dict[str, int]] = {}
        # Textual convention base types: tc_name -> base_syntax
        self._tc_types: dict[str, str] = {}

    def parse(self) -> list[OidEntry]:
        self._extract_and_rename()
        logger.info(f"Extracted {len(self._mib_modules)} MIB modules from archive")

        entries = self._parse_all_mibs()
        # Deduplicate entries by OID (same OID can appear in multiple MIB files)
        seen_oids: dict[str, OidEntry] = {}
        for e in entries:
            if e.oid not in seen_oids:
                seen_oids[e.oid] = e
        entries = list(seen_oids.values())
        entries = self._determine_table_relationships(entries)
        entries.sort(key=lambda e: [int(x) for x in e.oid.split(".")])

        logger.info(f"Parsed {len(entries)} OID entries")
        return entries

    def get_mib_modules(self) -> list[tuple[str, str]]:
        return self._mib_modules

    # --- Archive extraction (kept from original) ---

    def _extract_and_rename(self) -> None:
        self.mib_dir.mkdir(parents=True, exist_ok=True)

        if zipfile.is_zipfile(self.archive_path):
            members = self._list_zip()
        else:
            members = self._list_rar()

        for original_name, content in members:
            match = MODULE_NAME_RE.search(content)
            if match:
                mod_name = match.group(1)
                if mod_name == "RFC-1215":
                    continue
                content = TRAP_IMPORT_RE.sub("\n", content)
                content = TRAP_DEF_RE.sub("", content)
                target = self.mib_dir / f"{mod_name}.mib"
                target.write_text(content, encoding="utf-8")
                self._mib_modules.append((original_name, mod_name))
            else:
                filename = os.path.basename(original_name)
                target = self.mib_dir / filename
                target.write_text(content, encoding="utf-8")
                self._mib_modules.append((original_name, Path(filename).stem))

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

    # --- pysmi-based parsing ---

    def _parse_all_mibs(self) -> list[OidEntry]:
        """Parse all MIB files with pysmi's parser and extract OID entries."""
        parser = parserFactory()()
        entries: list[OidEntry] = []

        # Two passes: first collect all OID assignments and type definitions,
        # then build OidEntry objects with resolved absolute OIDs.

        # Pass 1: parse all modules, collect OID map and type info
        all_declarations: list[tuple] = []
        for mib_file in sorted(self.mib_dir.glob("*.mib")):
            try:
                content = mib_file.read_text(encoding="utf-8", errors="ignore")
                ast = parser.parse(content)
                if not ast:
                    continue
                module = ast[0]
                declarations = module[3] if len(module) > 3 else []
                if not declarations:
                    continue

                for decl in declarations:
                    if not isinstance(decl, tuple) or len(decl) < 2:
                        continue
                    self._collect_oid_and_types(decl)
                    all_declarations.append(decl)

            except Exception as e:
                logger.debug(f"Failed to parse {mib_file.name}: {e}")

        # Resolve all OIDs to absolute form
        self._resolve_all_oids()

        # Pass 2: build OidEntry objects
        for decl in all_declarations:
            entry = self._build_entry_from_ast(decl)
            if entry:
                entries.append(entry)

        # Pass 3: build structural OidEntry objects for %en lines
        # These are non-leaf nodes: objectIdentity, moduleIdentity,
        # objectIdentifier declarations, and well-known OIDs
        for decl in all_declarations:
            entry = self._build_structural_entry(decl)
            if entry:
                entries.append(entry)

        # Pass 4: add well-known OID nodes that weren't in any declaration
        # but are needed as %en lines (org, dod, internet, mgmt, etc.)
        existing_labels = {e.label for e in entries}
        for name, oid_str in WELL_KNOWN_OIDS.items():
            if name not in existing_labels and "." in oid_str:
                entries.append(OidEntry(
                    oid=oid_str,
                    label=name,
                    syntax="ObjectID",
                    original_syntax="ObjectID",
                    access=AccessLevel.NA,
                    is_structural_node=True,
                ))

        return entries

    def _store_oid(self, name: str, oid_value) -> None:
        """Store an OID mapping, but don't overwrite already-resolved values."""
        existing = self._oid_map.get(name)
        if isinstance(existing, str) and "." in existing:
            return  # Already resolved (e.g., from WELL_KNOWN_OIDS)
        self._oid_map[name] = oid_value

    def _collect_oid_and_types(self, decl: tuple) -> None:
        """Collect OID assignments and type definitions from an AST declaration."""
        decl_type = decl[0]

        if decl_type == "objectTypeClause" and len(decl) >= 12:
            name = decl[1]
            oid_part = decl[11]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

            # Collect enum definitions from syntax
            syntax = decl[2]
            self._collect_enum_from_syntax(name, syntax)

        elif decl_type == "objectIdentityClause" and len(decl) >= 6:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "moduleIdentityClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type in ("objectIdentifierDeclaration", "valueDeclaration") and len(decl) >= 3:
            name = decl[1]
            oid_part = decl[2]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "typeDeclaration" and len(decl) >= 3:
            name = decl[1]
            type_info = decl[2]
            self._collect_textual_convention(name, type_info)

        elif decl_type == "notificationTypeClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "moduleComplianceClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "objectGroupClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "notificationGroupClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

        elif decl_type == "agentCapabilitiesClause" and len(decl) >= 2:
            name = decl[1]
            oid_part = decl[-1]
            if isinstance(oid_part, tuple) and oid_part[0] == "objectIdentifier":
                self._store_oid(name, oid_part[1])

    def _collect_enum_from_syntax(self, column_name: str, syntax) -> None:
        """Extract enum values from a syntax definition."""
        if not isinstance(syntax, tuple):
            return
        # Look for enumSpec in syntax tuple
        for part in syntax:
            if isinstance(part, tuple) and part[0] == "enumSpec":
                enum_items = part[1] if len(part) > 1 else []
                if isinstance(enum_items, list):
                    enums = {}
                    for item in enum_items:
                        if isinstance(item, tuple) and len(item) == 2:
                            enums[str(item[0])] = int(item[1])
                    if enums:
                        self._enum_defs[column_name] = enums

    def _collect_textual_convention(self, name: str, type_info) -> None:
        """Collect textual convention base type mapping."""
        if not isinstance(type_info, tuple):
            return
        # TC definitions have various structures; extract base syntax if possible
        for part in type_info:
            if isinstance(part, tuple) and part[0] == "SimpleSyntax":
                if len(part) >= 2:
                    self._tc_types[name] = str(part[1])
            elif isinstance(part, str) and part in SYNTAX_MAP:
                self._tc_types[name] = part

    def _resolve_all_oids(self) -> None:
        """Resolve all OIDs from relative to absolute form."""
        max_iterations = 50
        for _ in range(max_iterations):
            changed = False
            for name, oid_val in list(self._oid_map.items()):
                if isinstance(oid_val, str) and "." in oid_val:
                    continue  # Already resolved

                if isinstance(oid_val, list):
                    resolved = self._resolve_oid_list(oid_val)
                    if resolved:
                        self._oid_map[name] = resolved
                        changed = True
            if not changed:
                break

    def _resolve_oid_list(self, oid_parts: list) -> Optional[str]:
        """Resolve an OID list like ['testEntry', 1] to absolute OID string."""
        result_parts = []
        for part in oid_parts:
            if isinstance(part, int):
                result_parts.append(str(part))
            elif isinstance(part, str):
                # Check if it's a named reference
                resolved = self._oid_map.get(part)
                if resolved is None:
                    return None  # Can't resolve yet
                if isinstance(resolved, str) and "." in resolved:
                    result_parts.append(resolved)
                elif isinstance(resolved, list):
                    return None  # Dependency not resolved yet
                else:
                    return None
            elif isinstance(part, tuple):
                # Handle (name, number) pairs like org(3)
                if len(part) == 2:
                    result_parts.append(str(part[1]))
        if result_parts:
            return ".".join(result_parts)
        return None

    def _build_entry_from_ast(self, decl: tuple) -> Optional[OidEntry]:
        """Build an OidEntry from a pysmi AST objectTypeClause."""
        if decl[0] != "objectTypeClause" or len(decl) < 12:
            return None

        name = decl[1]
        syntax_raw = decl[2]
        access_raw = decl[4]
        description_raw = decl[6]
        index_raw = decl[9]
        defval_raw = decl[10]
        oid_raw = decl[11]

        # Resolve OID
        oid_str = self._oid_map.get(name)
        if not oid_str or not isinstance(oid_str, str) or "." not in oid_str:
            return None

        # Parse syntax
        syntax, original_syntax, min_range, max_range, enum_values, display_hint = (
            self._parse_syntax(syntax_raw, name)
        )
        if not syntax:
            return None

        # Parse access
        access = self._parse_access(access_raw)

        # Check if this is a table entry (has INDEX clause)
        is_table_entry = False
        index_columns: list[str] = []
        implied_indexes: set[str] = set()

        if index_raw and isinstance(index_raw, tuple) and index_raw[0] == "INDEX":
            is_table_entry = True
            for idx_item in index_raw[1]:
                if isinstance(idx_item, tuple) and len(idx_item) == 2:
                    implied_flag = idx_item[0]
                    idx_name = str(idx_item[1])
                    index_columns.append(idx_name)
                    if implied_flag:
                        implied_indexes.add(idx_name)

        # Check if this is a conceptual table or row (not a leaf column)
        is_table = False
        if isinstance(syntax_raw, tuple):
            if syntax_raw[0] == "conceptualTable":
                return OidEntry(
                    oid=oid_str,
                    label=name,
                    syntax="SEQUENCE",
                    original_syntax="SEQUENCE",
                    access=AccessLevel.NA,
                    is_table_node=True,
                )
            if syntax_raw[0] == "row" and not is_table_entry:
                # Row type reference without INDEX — might be AUGMENTS
                # Check for augmentation
                augments_raw = decl[8]
                if augments_raw and isinstance(augments_raw, tuple):
                    is_table_entry = True

        # Parse DEFVAL
        default_value = None
        if defval_raw and isinstance(defval_raw, tuple) and defval_raw[0] == "DEFVAL":
            default_value = str(defval_raw[1])

        # Parse description
        description = ""
        if description_raw and isinstance(description_raw, tuple) and len(description_raw) >= 2:
            description = str(description_raw[1])

        # For enum columns without specific constraints, derive range from enum values
        if enum_values and (min_range is None or (min_range == -2147483648 and max_range == 2147483647)):
            enum_vals = list(enum_values.values())
            min_range = min(enum_vals)
            max_range = max(enum_vals)

        # Determine enum flag
        has_enum = bool(enum_values)
        enum_flag = "d"
        if has_enum:
            from backend.app.modules.sapro.oid_compiler.constants import ROWSTATUS_TCS
            rowstatus_names = {"active", "notInService", "notReady", "createAndGo", "createAndWait", "destroy"}
            if rowstatus_names.issubset(set(enum_values.keys())):
                enum_flag = "r"
            else:
                enum_flag = "e"

        normalized_syntax = SYNTAX_MAP.get(syntax, syntax)
        if normalized_syntax == syntax and syntax not in SYNTAX_MAP.values():
            normalized_syntax = SYNTAX_MAP.get(original_syntax, syntax)

        return OidEntry(
            oid=oid_str,
            label=name,
            syntax=normalized_syntax,
            original_syntax=original_syntax,
            access=access,
            is_table_entry=is_table_entry,
            index_columns=index_columns,
            implied_indexes=implied_indexes,
            min_range=min_range,
            max_range=max_range,
            has_enum=has_enum,
            enum_values=enum_values,
            default_value=default_value,
            description=description,
            display_hint=display_hint,
            enum_flag=enum_flag,
        )

    def _build_structural_entry(self, decl: tuple) -> Optional[OidEntry]:
        """Build an OidEntry for structural (non-leaf) nodes that need %en lines.

        Handles: objectIdentityClause, moduleIdentityClause,
        objectIdentifierDeclaration, valueDeclaration.
        """
        decl_type = decl[0]

        # Skip objectTypeClause — handled by _build_entry_from_ast
        if decl_type == "objectTypeClause":
            return None

        structural_types = {
            "objectIdentityClause",
            "moduleIdentityClause",
            "objectIdentifierDeclaration",
            "valueDeclaration",
            "notificationTypeClause",
            "moduleComplianceClause",
            "objectGroupClause",
            "notificationGroupClause",
            "agentCapabilitiesClause",
        }

        if decl_type not in structural_types:
            return None

        if len(decl) < 2:
            return None

        name = decl[1]
        oid_str = self._oid_map.get(name)
        if not oid_str or not isinstance(oid_str, str) or "." not in oid_str:
            return None

        return OidEntry(
            oid=oid_str,
            label=name,
            syntax="ObjectID",
            original_syntax="ObjectID",
            access=AccessLevel.NA,
            is_structural_node=True,
        )

    def _parse_syntax(self, syntax_raw, column_name: str):
        """Parse syntax tuple from AST.

        Returns: (syntax, original_syntax, min_range, max_range, enum_values, display_hint)
        """
        if not isinstance(syntax_raw, tuple):
            return None, "", None, None, {}, None

        min_range = None
        max_range = None
        enum_values = {}
        display_hint = None

        # Extract type name and constraints
        if syntax_raw[0] == "SimpleSyntax":
            type_name = str(syntax_raw[1]) if len(syntax_raw) >= 2 else "OctetString"
            original_syntax = type_name

            # Check for subtype constraints
            for part in syntax_raw[2:]:
                if isinstance(part, tuple):
                    if part[0] == "octetStringSubType":
                        # SIZE constraint: [(min, max), ...]
                        if part[1] and isinstance(part[1], list):
                            for constraint in part[1]:
                                if isinstance(constraint, tuple) and len(constraint) == 2:
                                    min_range = int(constraint[0])
                                    max_range = int(constraint[1])
                    elif part[0] == "integerSubType":
                        if part[1] and isinstance(part[1], list):
                            for constraint in part[1]:
                                if isinstance(constraint, tuple) and len(constraint) == 2:
                                    min_range = int(constraint[0])
                                    max_range = int(constraint[1])
                    elif part[0] == "enumSpec":
                        items = part[1] if len(part) > 1 else []
                        if isinstance(items, list):
                            for item in items:
                                if isinstance(item, tuple) and len(item) == 2:
                                    enum_values[str(item[0])] = int(item[1])

            # Also check column-level enums collected earlier
            if not enum_values and column_name in self._enum_defs:
                enum_values = self._enum_defs[column_name]

            # Apply fixed size for known types if no range extracted
            if original_syntax in FIXED_SIZE_TYPES and min_range is None:
                min_range, max_range = FIXED_SIZE_TYPES[original_syntax]

            return type_name, original_syntax, min_range, max_range, enum_values, display_hint

        elif syntax_raw[0] == "row":
            # Row/entry reference — table entry or textual convention reference
            type_name = str(syntax_raw[1]) if len(syntax_raw) >= 2 else "OctetString"
            enum_values = TC_ENUM_VALUES.get(type_name, {})
            min_range = None
            max_range = None
            if enum_values:
                min_range = min(enum_values.values())
                max_range = max(enum_values.values())
            if type_name in FIXED_SIZE_TYPES:
                min_range, max_range = FIXED_SIZE_TYPES[type_name]
            return type_name, type_name, min_range, max_range, enum_values, None

        elif syntax_raw[0] == "conceptualTable":
            return "SEQUENCE", "SEQUENCE", None, None, {}, None

        return None, "", None, None, {}, None

    def _parse_access(self, access_raw) -> AccessLevel:
        """Parse access from AST tuple."""
        if isinstance(access_raw, tuple) and len(access_raw) >= 2:
            access_str = str(access_raw[1]).lower()
            return ACCESS_MAP.get(access_str, AccessLevel.RO)
        return AccessLevel.RO

    def _determine_table_relationships(self, entries: list[OidEntry]) -> list[OidEntry]:
        """Set table_name, entry_name, and is_table_column for columns."""
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
                parent_entry = table_entries_by_oid[parent_oid]
                entry.is_table_column = True
                entry.entry_name = parent_entry.label
                entry.table_name = parent_entry.label.replace("Entry", "Table")
                entry.index_columns = parent_entry.index_columns
                entry.implied_indexes = parent_entry.implied_indexes

        # Assign column numbers
        table_columns: dict[str, list[OidEntry]] = {}
        for e in entries:
            if e.is_table_column and e.table_name:
                table_columns.setdefault(e.table_name, []).append(e)

        for cols in table_columns.values():
            cols.sort(key=lambda c: [int(x) for x in c.oid.split(".")])
            for idx, col in enumerate(cols, 1):
                col.index_type = f"C{idx}"

        return entries
