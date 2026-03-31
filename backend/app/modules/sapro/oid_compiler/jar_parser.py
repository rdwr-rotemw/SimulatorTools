import logging
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)


def parse_cc_columns_from_jar(jar_path: str) -> dict[str, set[str]]:
    """Parse a device driver JAR to extract columns CC writes per table.

    Analyzes CC screen XMLs to determine which SNMP columns CC sends
    during row creation. Uses intersection across all Modify screens
    for a table — only columns present in every screen are considered
    writable. This filters out legacy screen columns that are superseded
    by newer inner-table screens.

    Returns:
        Dict mapping table name to set of writable column labels.
    """
    # Collect per-table, per-screen column sets
    # table_id -> list of column sets (one per screen)
    table_screen_cols: dict[str, list[set[str]]] = {}

    with zipfile.ZipFile(jar_path, "r") as jar:
        for fname in jar.namelist():
            if not fname.endswith(".xml") or "screen" not in fname:
                continue
            basename = fname.split("/")[-1] if "/" in fname else fname
            # Skip Active (read-only view) and monitoring screens
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

                    is_local = False
                    is_readonly = False
                    for mp in elem.iter("managmentProperties"):
                        if mp.get("local") == "true":
                            is_local = True
                        if mp.get("readOnly") == "true":
                            is_readonly = True

                    if not is_local and not is_readonly and eid:
                        cols.add(eid)

                if cols:
                    table_screen_cols.setdefault(table_id, []).append(cols)

    # For each table, intersect the edit-dialog screen column sets.
    # List-view screens (with very few columns) are excluded from
    # intersection — they only show Name/Index, not edit columns.
    # The edit dialogs (inner tables) have the actual writable columns.
    cc_columns: dict[str, set[str]] = {}
    for table_id, screen_col_sets in table_screen_cols.items():
        # Filter to edit-dialog screens (more than 2 non-local columns)
        edit_screens = [s for s in screen_col_sets if len(s) > 2]
        if not edit_screens:
            # All screens are list views — use the largest one
            edit_screens = screen_col_sets

        if len(edit_screens) == 1:
            cc_columns[table_id] = edit_screens[0]
        else:
            # Intersect edit screens — columns in ALL edit dialogs
            result = edit_screens[0]
            for s in edit_screens[1:]:
                result = result & s
            if result:
                cc_columns[table_id] = result

    logger.info(f"Parsed {len(cc_columns)} CC table column mappings from JAR")
    return cc_columns
