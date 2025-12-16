"""Utilities to convert device template JSON to XML for Sapro and to modify template fields.

Functions:
- json_to_xml(template_dict: Dict[str, Any]) -> str
- modify_template_field(template_dict: Dict, path: str, value: Any) -> Dict

Behavior:
- Uses xml.etree.ElementTree to construct XML.
- Primitive values (str/int/bool/None) inside a dict become attributes on the parent's element.
- Nested dicts become child elements.
- Lists create repeated child elements for each item (child tag uses the same key name converted to PascalCase).
- Keys are converted to PascalCase for element and attribute names (snake_case and kebab-case supported).
- Produces pretty-printed XML with 2-space indentation.

"""
from typing import Any, Dict, List
import xml.etree.ElementTree as ET


def to_pascal_case(key: str) -> str:
    """Convert a key like 'device_map' or 'soapModFile' to PascalCase: 'DeviceMap', 'SoapModFile'.

    - Splits on '_' and '-' first. If no separators found, just uppercase first character and leave rest as-is.
    """
    if not key:
        return key
    if "_" in key or "-" in key:
        parts = [p for p in key.replace("-", "_").split("_") if p]
        return "".join(part[:1].upper() + part[1:] for part in parts)
    # No separators: just capitalize first char to preserve camelCase internals
    return key[:1].upper() + key[1:]


def _build_element(tag: str, obj: Any) -> ET.Element:
    """Recursively build an ElementTree Element for the given tag and object.

    Rules:
    - If obj is a dict: primitive values -> attributes; dict/list values -> child elements.
    - If obj is a list: create repeated child elements named after tag (PascalCase).
    - If obj is primitive: create element with text set to the string value.
    """
    element = ET.Element(to_pascal_case(tag))

    # Primitive types become text content
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        if obj is None:
            element.text = ""
        else:
            element.text = str(obj)
        return element

    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, dict):
                child = _build_element(key, val)
                element.append(child)
            elif isinstance(val, list):
                # For list, create repeated child elements for each entry
                for item in val:
                    child = _build_element(key, item)
                    element.append(child)
            else:
                # Primitive -> attribute
                # Convert None to empty string
                element.set(to_pascal_case(key), "" if val is None else str(val))
        return element

    if isinstance(obj, list):
        # If the value itself is a list at this level, create a parent element and
        # append child elements for each item using the same PascalCase tag.
        for item in obj:
            child = _build_element(tag, item)
            element.append(child)
        return element

    # Fallback: convert to string
    element.text = str(obj)
    return element


def _indent(elem: ET.Element, level: int = 0) -> None:
    """In-place pretty print formatter (2-space indentation)."""
    indent_str = "\n" + ("  " * level)
    child_indent = "\n" + ("  " * (level + 1))

    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = child_indent
        for child in elem:
            _indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent_str
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent_str


def json_to_xml(template_dict: Dict[str, Any]) -> str:
    """Convert a nested template JSON (dict) into a pretty-printed XML string.

    - Preserves attributes for primitive key/values on the same object level.
    - Nested dicts become child elements.
    - Uses 2-space indentation.

    Example input:
    {
      "deviceMap": {
        "release": "11.0",
        "description": "",
        "device": {
          "general": {"name": "<ip>", "multiHome": "1"},
          "snmp": {"readCommunity": "public"}
        }
      }
    }

    Produces:
    <DeviceMap Release="11.0" Description="">
      <Device>
        <General Name="<ip>" MultiHome="1" />
        <Snmp ReadCommunity="public" />
      </Device>
    </DeviceMap>

    Returns the XML as a string (no XML declaration).
    """
    if not isinstance(template_dict, dict):
        raise TypeError("template_dict must be a dict")

    # If template_dict contains a single top-level key, use it as the root element.
    keys = list(template_dict.keys())
    if len(keys) == 1:
        root_key = keys[0]
        root_val = template_dict[root_key]
        root = _build_element(root_key, root_val)
    else:
        # Multiple top-level items: wrap under a <Root> element
        root = ET.Element("Root")
        for k, v in template_dict.items():
            child = _build_element(k, v)
            root.append(child)

    # Pretty-print indentation
    _indent(root, 0)

    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str


def modify_template_field(template_dict: Dict, path: str, value: Any) -> Dict:
    """Modify a nested field inside `template_dict` following a dot-separated `path`.

    - Creates intermediate dictionaries when necessary.
    - Supports integer path segments to index lists (e.g., 'array.0.key').

    Example:
      modify_template_field(template, "deviceMap.device.soap.soapModFile", "/new/path.xmf")

    Returns the modified template_dict.
    """
    if not isinstance(template_dict, dict):
        raise TypeError("template_dict must be a dict")
    if not path:
        raise ValueError("path must be a non-empty string")

    parts = path.split(".")
    cur = template_dict
    for idx, part in enumerate(parts):
        is_last = idx == len(parts) - 1

        # If part looks like an integer index for a list, handle accordingly
        try:
            list_index = int(part)
            is_index = True
        except (ValueError, TypeError):
            list_index = None
            is_index = False

        if is_index:
            # Current must be a list
            if not isinstance(cur, list):
                # If we need to set into a list but current isn't a list, create it
                cur_parent = cur
                # Replace the current key in the parent with a list -- but we don't have parent reference here
                raise TypeError("Encountered numeric path segment but current object is not a list")

            # Ensure list is long enough
            while len(cur) <= list_index:
                cur.append({})

            if is_last:
                cur[list_index] = value
                return template_dict
            cur = cur[list_index]
            continue

        # Normal dict key
        if is_last:
            # Set the value
            if isinstance(cur, dict):
                cur[part] = value
            else:
                raise TypeError(f"Cannot set key '{part}' on non-dict object")
            return template_dict

        # Not last: ensure intermediate dict exists
        nxt = cur.get(part)
        if nxt is None:
            # Create intermediate dict
            cur[part] = {}
            nxt = cur[part]
        elif not isinstance(nxt, (dict, list)):
            # Overwrite non-dict with a dict to continue path
            cur[part] = {}
            nxt = cur[part]

        cur = nxt

    return template_dict

