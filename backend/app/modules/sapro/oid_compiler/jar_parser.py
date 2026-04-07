import logging
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)


def parse_cc_columns_from_jar(jar_path: str) -> dict[str, set[str]]:
    """Parse a device driver JAR to extract columns CC always sends per table.

    Two-layer filtering:
    1. Screen intersection — find columns present in edit-dialog screens
       (>2 columns), excluding view/Active screens. This filters out
       computed columns that only appear in display screens.
    2. Within edit-dialog columns, keep only those with defaultValue
       or mandatory=true in managmentProperties. CC always sends these.
       Columns without defaultValue and not mandatory are only sent
       when the user explicitly fills them — treated as NotReq.

    Returns:
        Dict mapping table name to set of always-sent column labels.
    """
    # Layer 1: collect per-table, per-screen column sets
    # table_id -> list of column sets (one per screen)
    table_screen_cols: dict[str, list[set[str]]] = {}
    # Track which columns have defaultValue or mandatory=true across all screens
    # column_id -> True if any screen has defaultValue or mandatory=true
    always_sent: dict[str, bool] = {}
    # Track columns with licenseDependency — CC hides them if device lacks license
    license_gated: set[str] = set()

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
                        # Track defaultValue and mandatory for Layer 2
                        if "defaultValue" in mp.attrib or mp.get("mandatory") == "true":
                            always_sent[eid] = True
                    # License-gated columns are hidden when device lacks
                    # the license — CC won't send them, so they can't be Req
                    for dep in elem.iter("dependency"):
                        for _ in dep.iter("licenseDependency"):
                            license_gated.add(eid)
                            break

                    if not is_local and not is_readonly and eid:
                        cols.add(eid)

                if cols:
                    table_screen_cols.setdefault(table_id, []).append(cols)

    # Layer 1: intersect edit-dialog screen column sets
    cc_columns: dict[str, set[str]] = {}
    for table_id, screen_col_sets in table_screen_cols.items():
        # Filter to edit-dialog screens (more than 2 non-local columns)
        edit_screens = [s for s in screen_col_sets if len(s) > 2]
        if not edit_screens:
            edit_screens = screen_col_sets

        if len(edit_screens) == 1:
            edit_cols = edit_screens[0]
        else:
            edit_cols = edit_screens[0]
            for s in edit_screens[1:]:
                edit_cols = edit_cols & s
            if not edit_cols:
                edit_cols = edit_screens[0]

        # Layer 2: from edit-dialog columns, keep only those CC always sends
        # (has defaultValue or mandatory=true, and not license-gated)
        req_cols = {col for col in edit_cols
                    if always_sent.get(col, False) and col not in license_gated}
        if req_cols:
            cc_columns[table_id] = req_cols

    logger.info(f"Parsed {len(cc_columns)} CC table column mappings from JAR")
    return cc_columns
