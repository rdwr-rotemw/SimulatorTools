import logging
import re

from backend.app.modules.sapro.oid_compiler.models import SoapColumnInfo, SoapTableInfo

logger = logging.getLogger(__name__)

# Regex patterns for parsing the C file
# Matches: UINT_8 *soap_<entryName>_attrList[] =
ATTR_LIST_PATTERN = re.compile(
    r'UINT_8\s+\*soap_(\w+)_attrList\[\]\s*=\s*\{([^}]+)\}',
    re.DOTALL,
)

# Matches: UINT_8 *soap_<entryName>_keyAttrList[] =
KEY_ATTR_LIST_PATTERN = re.compile(
    r'UINT_8\s+\*soap_(\w+)_keyAttrList\[\]\s*=\s*\{([^}]+)\}',
    re.DOTALL,
)

# Matches: operation = soapAddOperationMapping("namespace", MIB_<entry>_CNS,
#     "operation_name", "operation_response",
#     <callback>);
OPERATION_PATTERN = re.compile(
    r'soapAddOperationMapping\(\s*"([^"]+)"\s*,\s*MIB_(\w+)_CNS\s*,\s*'
    r'"(\w+)"\s*,\s*"[^"]+"\s*,\s*(\w+)\s*\)',
    re.DOTALL,
)

# Matches quoted string entries: "Name", "hidden", etc.
QUOTED_STRING_PATTERN = re.compile(r'"(\w+)"')


def _parse_array_entries(body: str) -> list[str]:
    """Extract quoted string values from a C array body, excluding NULL."""
    return [m.group(1) for m in QUOTED_STRING_PATTERN.finditer(body) if m.group(1) != "NULL"]


def parse_soap_metadata(file_path: str) -> list[SoapTableInfo]:
    """Parse soap_metadata.c and return structured table metadata.

    Extracts:
    - attrList arrays: column positions with visible/hidden flags
    - keyAttrList arrays: which columns are table keys
    - Operation mappings: SOAP namespace and whether create operations exist
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Step 1: Parse all attrList arrays
    tables: dict[str, SoapTableInfo] = {}

    for match in ATTR_LIST_PATTERN.finditer(content):
        entry_name = match.group(1)
        entries = _parse_array_entries(match.group(2))

        columns = []
        hidden_count = 0
        visible_count = 0

        for i, attr in enumerate(entries, start=1):
            is_hidden = attr == "hidden"
            if is_hidden:
                hidden_count += 1
            else:
                visible_count += 1

            columns.append(SoapColumnInfo(
                position=i,
                soap_name=None if is_hidden else attr,
                is_hidden=is_hidden,
            ))

        tables[entry_name] = SoapTableInfo(
            entry_name=entry_name,
            columns=columns,
            hidden_count=hidden_count,
            visible_count=visible_count,
        )

    # Step 2: Parse keyAttrList arrays and mark key columns
    for match in KEY_ATTR_LIST_PATTERN.finditer(content):
        entry_name = match.group(1)
        key_entries = _parse_array_entries(match.group(2))

        if entry_name not in tables:
            logger.warning(f"keyAttrList for {entry_name} has no matching attrList")
            continue

        table = tables[entry_name]
        key_names = {name for name in key_entries if name != "hidden"}

        # Mark columns that match key names
        for col in table.columns:
            if col.soap_name and col.soap_name in key_names:
                col.is_key = True

    # Step 3: Parse operation mappings for namespace and create capability
    for match in OPERATION_PATTERN.finditer(content):
        namespace = match.group(1)
        mib_entry = match.group(2)
        operation_name = match.group(3)
        callback = match.group(4)

        # MIB entry constant is like "rsBWMNetworkEntry" — match to our tables
        if mib_entry in tables:
            table = tables[mib_entry]
            if not table.soap_namespace:
                table.soap_namespace = namespace
            if callback == "wsCreateCallback":
                table.has_create = True

    result = list(tables.values())
    tables_with_hidden = [t for t in result if t.hidden_count > 0]

    logger.info(
        f"Parsed soap_metadata.c: {len(result)} tables, "
        f"{len(tables_with_hidden)} with hidden columns"
    )

    return result
