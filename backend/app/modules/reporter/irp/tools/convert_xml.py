import logging
import collections
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import xmltodict

from backend.app.modules.reporter.irp.models.data_format_models import *

# Module logger
logger = logging.getLogger(__name__)


class ConvertXml:
    """
    Parses IDS XML schema files into Python objects.
    """

    def __init__(self, xml_file):
        self.xml_file_path = Path(xml_file)
        if not self.xml_file_path.exists():
            raise FileNotFoundError(f"Schema XML file not found: {self.xml_file_path}")
        self.xml_dict = self.load_xml()
        self.xml_ordered_messages = self._parse_messages_with_ordering()
        self.schema = None  # Initialize schema attribute

    def _parse_messages_with_ordering(self):
        """
        Parse messages using ElementTree to preserve original XML element ordering.
        This fixes the xmltodict reordering issue without breaking existing functionality.
        """

        def parse_element(element):
            """
            Recursively parse an XML element and its children.

            Args:
                element (ET.Element): The XML element to parse.

            Returns:
                dict: Parsed element structure.
            """
            element_info = {
                'tag': element.tag,
                'name': element.get('name'),
                'type': element.get('type'),
                'attributes': dict(element.attrib),
                'children': []
            }

            for child in element:
                element_info['children'].append(parse_element(child))

            return element_info

        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()

            ordered_messages = {}

            # Find messages section
            messages_elem = root.find('messages')
            if messages_elem is not None:
                for message_elem in messages_elem.findall('message'):
                    msg_id = message_elem.get('id')
                    if msg_id:
                        # Parse elements recursively to preserve their original XML order
                        ordered_elements = [parse_element(child) for child in message_elem]
                        ordered_messages[msg_id] = ordered_elements

            return ordered_messages

        except Exception as e:
            logger.warning("ElementTree parsing failed: %s", e)
            return {}

    def load_xml(self):
        try:
            with open(self.xml_file_path, "r", encoding="utf-8") as file:
                xml_content = file.read()
            # Parse XML with OrderedDict and ensure hierarchical structure is preserved
            parsed_xml = xmltodict.parse(xml_content, dict_constructor=collections.OrderedDict)

            # Remove the global XML adjustment that was breaking while-loop structure
            # The original XML structure should be preserved as-is

            return parsed_xml
        except Exception as e:
            logger.exception("Failed to load or parse XML file %s: %s", self.xml_file_path, e)
            raise RuntimeError(f"Failed to load or parse XML file {self.xml_file_path}: {e}")

    class WhileLoop:
        def __init__(self, name, sentinel=None, stop_at=None, data=None):
            self.name = name
            self.sentinel = sentinel
            self.stop_at = stop_at
            self.data = data or []

    class DataField:
        def __init__(self, name, field_type):
            self.name = name
            self.type = field_type

    class Clone:
        def __init__(self, enumeration, body):
            self.enumeration = enumeration
            self.body = body

    class Struct:
        def __init__(self, name, fields):
            self.name = name
            self.fields = fields

    class Template:
        def __init__(self, name, instanceof):
            self.name = name
            self.instanceof = instanceof

    class ForLoop:
        def __init__(self, name, iterations, transparent, body):
            self.name = name
            self.iterations = iterations
            self.transparent = transparent
            self.body = body

    class Switch:
        def __init__(self, selector, cases, name=None):
            self.selector = selector
            self.cases = cases
            self.name = name

    class Composite:
        def __init__(self, name, composite_type, body):
            self.name = name
            self.composite_type = composite_type
            self.body = body

    class FixedArray:
        def __init__(self, name, array_type, size):
            self.name = name
            self.array_type = array_type
            self.size = size

    class VarArray:
        def __init__(self, name, array_type, size):
            self.name = name
            self.array_type = array_type
            self.size = size

    class IfCondition:
        def __init__(self, name, condition, body):
            self.name = name
            self.condition = condition
            self.body = body

    class Overlap:
        def __init__(self, data, name=None):
            self.data = data
            self.name = name

    class Nil:
        def __init__(self, name):
            self.name = name

    class Error:
        def __init__(self, name):
            self.name = name

    def _process_enumeration(self, enumeration):
        """
        Process enumeration nodes and add values dynamically.
        """
        if isinstance(enumeration, dict):
            values = enumeration.get('value', [])
            if isinstance(values, list):
                for i, value in enumerate(values):
                    if '@name' in value and '@code' not in value:
                        value['@code'] = i  # Assign incremental codes starting from 0
        return enumeration

    def get_enum_binary(self, enum_name):
        """
        Generate binary representation for enumeration values in order.
        """
        if not self.schema or not hasattr(self.schema, "types") or not self.schema.types:
            raise RuntimeError("Schema types are not initialized. Call convert_xml() first.")

        if not hasattr(self.schema.types, "enums") or not self.schema.types.enums:
            raise ValueError("No enums found in schema types.")

        if enum_name not in self.schema.types.enums:
            raise ValueError(f"Enumeration {enum_name} not found in schema.")

        enum = self.schema.types.enums[enum_name]
        binary_values = []
        for i, value in enumerate(enum.values.values()):
            binary_values.append(struct.pack('<I', i))  # Pack as unsigned 32-bit integer
        return binary_values

    def _convert_dict_to_children(self, node_dict):
        """
        Convert a dictionary structure to children format for recursive parsing.

        Args:
            node_dict: Dictionary containing XML node data

        Returns:
            list: List of child element info structures
        """
        children = []
        if isinstance(node_dict, dict):
            for child_key, child_val in node_dict.items():
                if not child_key.startswith('@'):
                    if isinstance(child_val, dict):
                        element_info = {
                            'tag': child_key,
                            'name': child_val.get('@name'),
                            'attributes': {k[1:]: v for k, v in child_val.items() if k.startswith('@')},
                            'children': self._convert_dict_to_children(child_val)
                        }
                        children.append(element_info)
                    elif isinstance(child_val, list):
                        # Handle lists of elements (like multiple data fields)
                        for item in child_val:
                            if isinstance(item, dict):
                                element_info = {
                                    'tag': child_key,
                                    'name': item.get('@name'),
                                    'attributes': {k[1:]: v for k, v in item.items() if k.startswith('@')},
                                    'children': self._convert_dict_to_children(item)
                                }
                                children.append(element_info)
        return children

    def _create_elements_from_ordered_data(self, ordered_elements):
        """
        Convert ordered element data from ElementTree into ConvertXml objects.
        This method is now recursive to handle deeply nested structures, including composites.
        """

        def process_element(elem_info):
            tag = elem_info['tag']
            name = elem_info['name']
            attributes = elem_info['attributes']
            children = elem_info.get('children', [])

            if tag == 'data':
                return self.DataField(name, attributes.get('type'))

            elif tag == 'if':
                if_children = [process_element(child_info) for child_info in children]
                return self.IfCondition(name, attributes.get('condition'), if_children)

            elif tag == 'template':
                instanceof = attributes.get('instanceof')
                # Auto-assign name for unnamed templates so template references like
                # <template instanceof="report-id"></template> become named 'report-id'
                if not name:
                    if instanceof and "." in instanceof:
                        name = instanceof.split('.')[1]
                    else:
                        name = instanceof
                return self.Template(name, instanceof)

            elif tag == 'struct':
                struct_children = [process_element(child_info) for child_info in children]
                return self.Struct(name, struct_children)

            elif tag == 'composite':
                composite_type = attributes.get('type')
                composite_children = [process_element(child_info) for child_info in children]
                name = attributes['type'].split('.')[1] if not 'name' in attributes else attributes['name']
                return self.Composite(name, composite_type, composite_children)

            elif tag == 'while-loop':
                loop_children = [process_element(child_info) for child_info in children]
                return self.WhileLoop(
                    name,
                    attributes.get('sentinel'),
                    attributes.get('stop-at'),
                    loop_children
                )

            elif tag == 'for-loop':
                loop_children = [process_element(child_info) for child_info in children]
                return self.ForLoop(
                    name,
                    attributes.get('iterations'),
                    attributes.get('transparent', 'no'),
                    loop_children
                )
            elif tag == 'overlap':
                overlap_children = [process_element(child_info) for child_info in children]
                return self.Overlap(overlap_children, name='overlap')
            elif tag == 'fixed-array':
                return self.FixedArray(name, attributes.get('type'), attributes.get('size'))

            elif tag == "switch":
                switch_children = [process_element(child_info) for child_info in children]
                return self.Switch(attributes.get('selector'), switch_children, name=name)

            elif tag == 'nil':
                return self.Nil(name)

            elif tag == 'error':
                return self.Error(name)

            elif tag == 'var-array':
                return self.VarArray(name, attributes.get('type'), attributes.get('size'))

            elif tag == 'clone':
                # Clone body can contain template, data, or other elements
                clone_body = None
                if children:
                    # Process all children recursively to get the actual body
                    clone_body = self._create_elements_from_ordered_data(children)
                return self.Clone(attributes.get('enumeration'), clone_body)

            return None  # Fallback for unsupported tags

        elements = [process_element(elem_info) for elem_info in ordered_elements]
        return [elem for elem in elements if elem is not None]

    def convert_xml(self):
        """
        Convert the loaded XML schema into a Schema object.
        """
        self.schema = Schema()  # Assign schema attribute
        irp_messages = {}

        # Initialize templates and types
        templates = Templates()
        types = Types()

        # Set messages - USE ORDERED PARSING IF AVAILABLE
        for _message in self.xml_dict['schema']['messages']['message']:
            message_id = _message['@id']
            message_name = _message['@name']

            # Try to use ordered parsing first
            if message_id in self.xml_ordered_messages:
                # Use ElementTree parsed data with correct ordering
                ordered_elements = self.xml_ordered_messages[message_id]
                message_elements = self._create_elements_from_ordered_data(ordered_elements)
            else:
                # Fallback to xmltodict parsing (existing functionality)
                message_elements = []
                for k, v in _message.items():
                    if not k.startswith('@'):
                        # Process elements normally without special list handling
                        if isinstance(v, list):
                            for item in v:
                                message_elements.append(self._parse_message_element(k, item))
                        else:
                            message_elements.append(self._parse_message_element(k, v))

            irp_messages[message_id] = Message(message_name, message_elements)

        self.schema.set_messages(irp_messages)

        # Set templates (parse all templates and namespaces recursively)
        structs = {}
        namespaces = {}
        templates_dict = self.xml_dict['schema']['templates']
        for key, value in templates_dict.items():
            if key == 'namespace':
                # Namespaces - use proper recursive parsing
                ns_list = value if isinstance(value, list) else [value]
                for ns in ns_list:
                    ns_name = ns['@name']
                    ns_structs = {}
                    for struct_key, struct_val in ns.items():
                        if struct_key == '@name':
                            continue

                        full_name = f"{ns_name}.{struct_key}"

                        # Parse namespace templates using the same recursive logic as messages
                        template_elements = []

                        if isinstance(struct_val, dict):
                            # Single element as dict
                            for child_key, child_val in struct_val.items():
                                if not child_key.startswith('@'):
                                    # Create element info structure similar to ElementTree parsing
                                    if isinstance(child_val, dict):
                                        element_info = {
                                            'tag': child_key,
                                            'name': child_val.get('@name'),
                                            'attributes': {k[1:]: v for k, v in child_val.items() if k.startswith('@')},
                                            'children': self._convert_dict_to_children(child_val)
                                        }
                                        template_elements.append(element_info)
                                    elif isinstance(child_val, list):
                                        # Multiple elements as list (e.g., multiple templates in rate-vectors)
                                        for item in child_val:
                                            if isinstance(item, dict):
                                                element_info = {
                                                    'tag': child_key,
                                                    'name': item.get('@name'),
                                                    'attributes': {k[1:]: v for k, v in item.items() if k.startswith('@')},
                                                    'children': self._convert_dict_to_children(item)
                                                }
                                                template_elements.append(element_info)

                        # Use the proper recursive parsing method
                        if template_elements:
                            parsed_elements = self._create_elements_from_ordered_data(template_elements)

                            if len(parsed_elements) == 1:
                                single_element = parsed_elements[0]

                                # Check if the single element is a ConvertXml.Struct (has 'fields' attribute)
                                # vs model Struct (has 'data' attribute only)
                                if hasattr(single_element, 'fields') and not hasattr(single_element, 'data'):
                                    # ConvertXml.Struct - extract its fields and wrap in model Struct with fields as data
                                    # This avoids double-nesting while maintaining model Struct structure
                                    ns_structs[struct_key] = Struct(full_name, single_element.fields)
                                else:
                                    # ForLoop, WhileLoop, or other element - wrap in model Struct with element as data
                                    ns_structs[struct_key] = Struct(full_name, single_element)
                            else:
                                # Multiple elements, wrap list in model Struct.data
                                ns_structs[struct_key] = Struct(full_name, parsed_elements)
                        else:
                            ns_structs[struct_key] = Struct(full_name, [])

                    namespaces[ns_name] = Namespace(ns_name, ns_structs)
            else:
                # Top-level templates - use original parsing logic (don't break existing functionality)
                struct = value['struct'] if 'struct' in value else value
                name = struct['@name'] if '@name' in struct else key

                # Use the original parsing method for top-level templates to avoid breaking existing functionality
                if isinstance(struct, dict) and 'data' in struct:
                    # This is a struct with data elements, process them directly
                    data_elements = struct['data']
                    if isinstance(data_elements, list):
                        converted_fields = []
                        for data_elem in data_elements:
                            if isinstance(data_elem, dict) and '@name' in data_elem and '@type' in data_elem:
                                converted_fields.append(ConvertXml.DataField(data_elem['@name'], data_elem['@type']))
                        structs[name] = ConvertXml.Struct(name, converted_fields)
                    elif isinstance(data_elements, dict) and '@name' in data_elements and '@type' in data_elements:
                        # Single data element
                        field = ConvertXml.DataField(data_elements['@name'], data_elements['@type'])
                        structs[name] = ConvertXml.Struct(name, [field])
                    else:
                        structs[name] = ConvertXml.Struct(name, [])
                else:
                    structs[name] = ConvertXml.Struct(name, [])

        templates.set_structs(structs)
        templates.set_namespaces(namespaces)
        self.schema.set_templates(templates)

        # Set types (parse all types and namespaces recursively)
        types_dict = self.xml_dict['schema']['types']
        primitives = {}
        fixed_strings = {}
        ip_addresses = {}
        enums = {}
        namespaces_types = {}
        bitmap = None
        for key, value in types_dict.items():
            if key == 'integer':
                int_list = value if isinstance(value, list) else [value]
                for integer in int_list:
                    primitives[integer['@name']] = integer['@size']
            elif key == 'boolean':
                bool_list = value if isinstance(value, list) else [value]
                for boolean in bool_list:
                    primitives[boolean['@name']] = boolean.get('@size', '1')
            elif key == 'float':
                primitives['float'] = 'float'
            elif key == 'fixed-string':
                fs_list = value if isinstance(value, list) else [value]
                for fs in fs_list:
                    fixed_strings[fs['@name']] = fs['@size']
            elif key == 'ip-address':
                ip_list = value if isinstance(value, list) else [value]
                for ip in ip_list:
                    ip_addresses[ip['@name']] = ip['@version']
            elif key == 'enumeration':
                enum_list = value if isinstance(value, list) else [value]
                for enum in enum_list:
                    values = {}
                    name = enum['@name']
                    # --- FIX: assign codes by order if missing ---
                    code_counter = 0
                    val_list = enum['value'] if isinstance(enum['value'], list) else [enum['value']]
                    for val in val_list:
                        code = val.get('@code')
                        if code is None:
                            code = code_counter
                        else:
                            try:
                                code = int(code)
                            except Exception:
                                code = code_counter
                        values[val['@name']] = code
                        code_counter += 1
                    enums[name] = Enum(name, enum['@type'], values)
            elif key == 'bitmap':
                bm_list = value if isinstance(value, list) else [value]
                for bm in bm_list:
                    name = bm['@name']
                    size = bm['@size']
                    bitmap_values = {}
                    val_list = bm['value'] if isinstance(bm['value'], list) else [bm['value']]
                    for val in val_list:
                        bitmap_values[val['@name']] = val.get('@code', None)
                    bitmap = Enum(name, size, bitmap_values)
            elif key == 'namespace':
                ns_list = value if isinstance(value, list) else [value]
                for ns in ns_list:
                    ns_name = ns['@name']
                    ns_types = {}
                    for type_key, type_val in ns.items():
                        if type_key == '@name':
                            continue
                        if type_key == 'fixed-string':
                            fs_list = type_val if isinstance(type_val, list) else [type_val]
                            for fs in fs_list:
                                fixed_strings[f"{ns_name}.{fs['@name']}"] = fs['@size']
                                ns_types[fs['@name']] = fs['@size']
                        elif type_key == 'enumeration':
                            enum_list = type_val if isinstance(type_val, list) else [type_val]
                            for enum in enum_list:
                                values = {}
                                code_counter = 0
                                val_list = enum['value'] if isinstance(enum['value'], list) else [enum['value']]
                                for val in val_list:
                                    code = val.get('@code')
                                    if code is None:
                                        code = code_counter
                                    else:
                                        try:
                                            code = int(code)
                                        except Exception:
                                            code = code_counter
                                    values[val['@name']] = code
                                    code_counter += 1
                                enums[f"{ns_name}.{enum['@name']}"] = Enum(f"{ns_name}.{enum['@name']}", enum['@type'],
                                                                           values)
                                ns_types[enum['@name']] = Enum(enum['@name'], enum['@type'], values)
                        elif type_key == 'bitmap':
                            bm = type_val
                            bm_list = bm if isinstance(bm, list) else [bm]
                            for bm_item in bm_list:
                                bm_name = bm_item['@name']
                                bm_size = bm_item['@size']
                                bm_values = {}
                                val_list = bm_item['value'] if isinstance(bm_item['value'], list) else [
                                    bm_item['value']]
                                for val in val_list:
                                    bm_values[val['@name']] = val.get('@code', None)
                                enums[f"{ns_name}.{bm_name}"] = Enum(f"{ns_name}.{bm_name}", bm_size, bm_values)
                                ns_types[bm_name] = Enum(bm_name, bm_size, bm_values)
                        else:
                            ns_types[type_key] = type_val
                    namespaces_types[ns_name] = ns_types
        types.set_primitives(primitives)
        types.set_fixed_strings(fixed_strings)
        types.set_ip_address(ip_addresses)
        types.set_enums(enums)
        types.set_bitmap(bitmap)
        types.set_namespaces(namespaces_types)
        self.schema.set_types(types)

        return self

    def debug_parsed_schema(self):
        """
        Debug method to print the parsed schema for verification.
        """
        if not getattr(self, 'schema', None):
            logger.debug("No parsed schema available to debug")
            return
        logger.debug("Parsed schema messages:")
        for message_id, message in self.schema.messages.items():
            logger.debug("Message ID: %s, Message Name: %s", message_id, message.name)
            logger.debug("Data: %s", message.data)

    def debug_parsed_message(self, message_id):
        """
        Debug method to print the parsed data for a specific message ID.
        """
        if not getattr(self, 'schema', None) or message_id not in self.schema.messages:
            logger.debug("Message ID %s not found in schema.", message_id)
            return

        message = self.schema.messages[message_id]
        logger.debug("Message ID: %s, Name: %s", message_id, message.name)
        logger.debug("Data: %s", message.data)

    def _parse_message_element(self, key, value):
        """
        Parse a single message element (data field, struct, etc.) from XML to internal representation.
        Preserves hierarchical structure by recursively parsing nested children.
        """
        if key == 'data':
            return self.DataField(value.get('@name'), value.get('@type'))
        elif key == 'struct':
            children = []
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    if not child_key.startswith('@'):
                        if isinstance(child_value, list):
                            for item in child_value:
                                children.append(self._parse_message_element(child_key, item))
                        else:
                            children.append(self._parse_message_element(child_key, child_value))
            return self.Struct(value.get('@name'), children)
        elif key == 'composite':
            children = []
            if isinstance(value, dict):
                for child_key, child_value in value.items():
                    if not child_key.startswith('@'):
                        if isinstance(child_value, list):
                            for item in child_value:
                                children.append(self._parse_message_element(child_key, item))
                        else:
                            children.append(self._parse_message_element(child_key, child_value))
            return self.Composite(value.get('@type'), value.get('@type'), children)

    class DivModComposite:
        def __init__(self, denominator, type_name, quotient_type, remainder_type):
            if not isinstance(denominator, int) or denominator < 1:
                raise ValueError("Denominator must be an integer greater than or equal to 1")
            self.denominator = denominator
            self.type = type_name
            self.quotient_type = quotient_type
            self.remainder_type = remainder_type

        def compose(self, quotient, remainder, type_handler):
            """
            Compose a value from quotient and remainder.
            """
            value = quotient * self.denominator + remainder
            return type_handler.encode(self.type, value)

        def decompose(self, value, type_handler):
            """
            Decompose a value into quotient and remainder.
            """
            decoded_value = type_handler.decode(self.type, value)
            quotient = decoded_value // self.denominator
            remainder = decoded_value % self.denominator
            return quotient, remainder

