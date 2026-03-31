import logging
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)


def parse_cc_columns_from_jar(jar_path: str) -> dict[str, set[str]]:
    """Parse a device driver JAR to extract columns CC writes per table.

    CC screen XMLs in the JAR define which SNMP columns are sent during
    create/update operations. Columns CC sends should be Req in %dcol,
    columns CC doesn't send should be NotReq.

    Returns:
        Dict mapping table name (e.g., "rsBWMNetworkTable") to set of
        column labels (e.g., {"rsBWMNetworkAddress", "rsBWMNetworkMask"}).
    """
    cc_columns: dict[str, set[str]] = {}

    with zipfile.ZipFile(jar_path, "r") as jar:
        for fname in jar.namelist():
            if not fname.endswith(".xml") or "screen" not in fname:
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
                    for mp in elem.iter("managmentProperties"):
                        if mp.get("local") == "true":
                            eid = ""
                            break
                    if eid:
                        cols.add(eid)

                if cols:
                    cc_columns.setdefault(table_id, set()).update(cols)

    logger.info(f"Parsed {len(cc_columns)} CC table column mappings from JAR")
    return cc_columns
