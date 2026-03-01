"""Utilities to convert device template JSON to XML for Sapro and to modify template fields.

This module provides:
- json_to_xml(template_dict: Dict[str, Any]) -> str
- modify_template_field(template_dict: Dict, path: str, value: Any) -> Dict

Behavior highlights:
- Uses a custom renderer to produce Sapro-style XML (attributes with spaces, 8-space indentation).
- Converts keys to Sapro-preferred CamelCase with special handling for acronyms like SSH/SSHSCP/DHCP and short prefixes like Snmp/Soap.
- Primitive dict values become attributes; nested dicts become child elements; lists become repeated child elements.
"""
from typing import Any, Dict
import xml.etree.ElementTree as ET
import re
from xml.sax.saxutils import escape as xml_escape


def to_camel_case(key: str) -> str:
    """Convert snake_case / camelCase keys to Sapro-style CamelCase with acronym handling.

    Rules implemented:
    - Known acronym prefixes are mapped specially:
      - 'ssh' -> 'SSH' (uppercase)
      - 'sshscp' -> 'SSHSCP' (uppercase)
      - 'snmp' -> 'Snmp' (first-letter uppercase only)
      - 'soap' -> 'Soap'
      - 'dhcp' -> 'DHCP' (uppercase)
    - If key starts with a known prefix, the prefix mapping is used and the rest of the
      key is PascalCased and appended.
    - Otherwise, the key is converted from snake_case/camelCase to PascalCase.

    Examples:
      snmp_str -> SnmpStr
      snmp_port -> SnmpPort
      soap_http_port -> SoapHttpPort
      ssh_user_name -> SSHUserName
      sshscp_base_dir -> SSHSCPBaseDir
      dhcp -> DHCP
      multi_home -> MultiHome
      subnet_mask -> SubnetMask
    """
    if not key:
        return key

    # Normalize separators and split camel boundaries
    s = key.replace('-', '_')
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    parts = [p for p in s.split('_') if p]
    if not parts:
        return key

    acronyms = {
        'sshscp': 'SSHSCP',
        'sshs': 'SSHS',
        'ssh': 'SSH',
        'snmp': 'Snmp',
        'soap': 'Soap',
        'dhcp': 'DHCP',
    }

    # Try longest matching acronym prefix (e.g., sshscp before ssh)
    lower = s.lower()
    for acr in sorted(acronyms.keys(), key=lambda x: -len(x)):
        if lower.startswith(acr):
            prefix = acronyms[acr]
            rest = s[len(acr):]
            if not rest:
                return prefix
            # rest may start with '_' or camelCase; normalize and PascalCase it
            rest = rest.lstrip('_')
            # split remaining on underscores and camel boundaries
            rest_parts = [p for p in re.split(r'[_]', rest) if p]
            rest_camel = ''.join(p[:1].upper() + p[1:] for p in rest_parts)
            return prefix + rest_camel

    # Default: PascalCase (capitalize all parts)
    return ''.join(p[:1].upper() + p[1:] for p in parts)


def _build_element(tag: str, obj: Any) -> ET.Element:
    """Recursively build an ElementTree Element using to_camel_case for names.

    - Primitives (str/int/float/bool/None) at this level become element text.
    - Dict entries that are primitives become attributes on this element.
    - Dict entries that are dict/list become child elements.
    - Lists become repeated child elements named by the tag.
    """
    element = ET.Element(to_camel_case(tag))

    # Primitive types become text content
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        element.text = "" if obj is None else str(obj)
        return element

    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, dict):
                child = _build_element(key, val)
                element.append(child)
            elif isinstance(val, list):
                for item in val:
                    child = _build_element(key, item)
                    element.append(child)
            else:
                # Primitive -> attribute (convert None to empty string)
                element.set(to_camel_case(key), "" if val is None else str(val))
        return element

    if isinstance(obj, list):
        # Create repeated child elements for each item
        for item in obj:
            child = _build_element(tag, item)
            element.append(child)
        return element

    # Fallback: convert to string
    element.text = str(obj)
    return element


def json_to_xml(template_dict: Dict[str, Any]) -> str:
    """Convert a nested template JSON (dict) into Sapro-styled XML string.

    Formatting specifics implemented:
    - 8-space indentation per level
    - Attributes formatted as: Name = "value" (spaces around =)
    - Inline attributes when <= 4 attributes; otherwise attributes are listed on separate
      indented lines, with the '>' closing the start tag appended at the end of the last attribute line.
    - Text content is indented one level in from the tag.
    """
    if not isinstance(template_dict, dict):
        raise TypeError("template_dict must be a dict")

    keys = list(template_dict.keys())
    if len(keys) == 1:
        root_key = keys[0]
        root_val = template_dict[root_key]
        root = _build_element(root_key, root_val)
    else:
        root = ET.Element("Root")
        for k, v in template_dict.items():
            child = _build_element(k, v)
            root.append(child)

    def render_element(elem: ET.Element, level: int = 0) -> str:
        indent = ' ' * (8 * level)
        tag = elem.tag

        # Prepare attributes
        attrs = []
        for k, v in elem.attrib.items():
            name = to_camel_case(k)
            val = '' if v is None else str(v)
            val_escaped = xml_escape(val, {'"': '&quot;'})
            attrs.append(f'{name} = "{val_escaped}"')

        children = list(elem)
        # Determine meaningful text: treat empty or whitespace-only text as absent
        text_raw = elem.text
        text = None
        if text_raw is not None:
            t = str(text_raw).strip()
            if t != '':
                text = t

        # Inline if small attribute count
        inline = len(attrs) <= 2

        # No children and no text -> self-closing
        if not children and not text:
            if attrs:
                if inline:
                    return f"{indent}<{tag} {' '.join(attrs)} />\n"
                else:
                    # Multiline attributes; close with '/>' on its own line
                    attr_lines = '\n'.join(f"{indent}        {a}" for a in attrs)
                    return f"{indent}<{tag}\n{attr_lines}\n{indent}/>\n"
            else:
                return f"{indent}<{tag} />\n"

        # Has children or text -> opening tag
        if attrs:
            if inline:
                open_tag = f"{indent}<{tag} {' '.join(attrs)}>\n"
            else:
                attr_lines = '\n'.join(f"{indent}        {a}" for a in attrs)
                open_tag = f"{indent}<{tag}\n{attr_lines}>\n"
        else:
            open_tag = f"{indent}<{tag}>\n"

        inner = ''
        if text:
            inner += f"{indent}        {xml_escape(text)}\n"

        for child in children:
            inner += render_element(child, level + 1)

        close_tag = f"{indent}</{tag}>\n"
        return open_tag + inner + close_tag

    xml_out = render_element(root, 0)
    return xml_out.rstrip('\n')


def modify_template_field(template_dict: Dict, path: str, value: Any) -> Dict:
    """Modify a nested field inside `template_dict` following a dot-separated `path`.

    - Creates intermediate dictionaries when necessary.
    - Supports integer path segments to index lists (e.g., 'array.0.key').
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
            if not isinstance(cur, list):
                raise TypeError("Encountered numeric path segment but current object is not a list")

            while len(cur) <= list_index:
                cur.append({})

            if is_last:
                cur[list_index] = value
                return template_dict
            cur = cur[list_index]
            continue

        # Normal dict key
        if is_last:
            if isinstance(cur, dict):
                cur[part] = value
            else:
                raise TypeError(f"Cannot set key '{part}' on non-dict object")
            return template_dict

        nxt = cur.get(part)
        if nxt is None:
            cur[part] = {}
            nxt = cur[part]
        elif not isinstance(nxt, (dict, list)):
            cur[part] = {}
            nxt = cur[part]

        cur = nxt

    return template_dict
