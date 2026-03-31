import logging
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)


def parse_cc_columns_from_jar(jar_path: str) -> dict[str, set[str]]:
    """Parse a device driver JAR to extract columns CC writes per table.

    CC screen XMLs define which SNMP columns CC sends during create/update.
    A column is considered "CC writes" if it's present in the screen XML
    AND is not marked readOnly in managmentProperties.

    Columns not present in the screen XML at all are hidden/computed —
    CC doesn't know about them.

    Returns:
        Dict mapping table name (e.g., "rsBWMNetworkTable") to set of
        writable column labels CC sends during row creation.
    """
    cc_columns: dict[str, set[str]] = {}

    with zipfile.ZipFile(jar_path, "r") as jar:
        for fname in jar.namelist():
            if not fname.endswith(".xml") or "screen" not in fname:
                continue
            # Skip Active (read-only view) and monitoring screens
            basename = fname.split("/")[-1] if "/" in fname else fname
            if ".Active." in basename or basename.startswith("MC."):
                continue
            try:
                content = jar.read(fname).decode("utf-8", errors="replace")
                root = ET.fromstring(content)
            except (ET.ParseError, KeyError):
                continue

            for table in root.iter("table"):
                table_id = table.get("id", "")
                if not table_id:
                    continue

                cols: set[str] = set()
                for elem in table.iter():
                    if elem.tag not in ("column", "subColumn"):
                        continue
                    eid = elem.get("id", "")
                    if not eid:
                        continue

                    # Skip UI-local fields that aren't SNMP columns
                    is_local = False
                    is_readonly = False
                    for mp in elem.iter("managmentProperties"):
                        if mp.get("local") == "true":
                            is_local = True
                        if mp.get("readOnly") == "true":
                            is_readonly = True

                    # Only include columns CC actually writes
                    if not is_local and not is_readonly and eid:
                        cols.add(eid)

                if cols:
                    cc_columns.setdefault(table_id, set()).update(cols)

    logger.info(f"Parsed {len(cc_columns)} CC table column mappings from JAR")
    return cc_columns
