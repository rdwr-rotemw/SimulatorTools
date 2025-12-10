import json
from pathlib import Path
from backend.app.modules.reporter.irp.tools.footprint_template_generator import FootprintTemplateGenerator
from backend.app.modules.reporter.irp.models.data_format_models import Enum


class TemplateGenerator:
    """
    Generates JSON templates for IRP messages based on XML schema definitions.
    Creates template files that can be used as starting points for message values.
    Includes specialized handling for footprint structures with var-arrays.
    NOW WITH METADATA: Can generate field metadata for dynamic UI form generation.
    """

    def __init__(self, schema):
        self.schema = schema
        self.footprint_generator = FootprintTemplateGenerator()

    def generate_template(self, message_id, output_file=None, interactive=False):
        """
        Generate a JSON template for the specified message ID.

        Args:
            message_id (int): The message ID to generate template for
            output_file (str): Optional output file path. If None, returns the template dict
            interactive (bool): If True, prompt user for array sizes and footprint configuration

        Returns:
            dict: Template structure if output_file is None
            str: Output file path if template was written to file
        """
        message_id_str = str(message_id)
        if message_id_str not in self.schema.messages:
            raise ValueError(f"Message ID {message_id} not found in schema")

        message = self.schema.messages[message_id_str]

        # Collect array information for interactive mode
        array_info = []
        if interactive:
            array_info = self._collect_array_info(message.data)

        template = {}

        # Process message data elements to create template structure
        self._process_elements(message.data, template, array_info, interactive)

        if output_file:
            # Write template to file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)

            return str(output_path)
        else:
            return template

    def generate_template_with_metadata(self, message_id, interactive=False):
        """
        Generate a JSON template with field metadata for UI form generation.

        Args:
            message_id (int): The message ID to generate template for
            interactive (bool): If True, prompt user for array sizes

        Returns:
            dict: {
                "template": {...},  # Default values
                "schema": {...}     # Field metadata (type, options, etc.)
            }
        """
        message_id_str = str(message_id)
        if message_id_str not in self.schema.messages:
            raise ValueError(f"Message ID {message_id} not found in schema")

        message = self.schema.messages[message_id_str]

        # Collect array information
        array_info = []
        if interactive:
            array_info = self._collect_array_info(message.data)
        else:
            array_info = self._collect_array_info_with_defaults(message.data)

        template = {}
        schema = {}

        # Process message data elements to create both template and schema
        self._process_elements_with_metadata(message.data, template, schema, array_info, interactive)

        return {
            "template": template,
            "schema": schema
        }

    def _collect_array_info(self, elements, path=""):
        """
        Recursively collect information about arrays in the message structure.
        Returns a list of array configurations chosen by the user.
        """
        array_info = []

        def collect_from_elements(elem_list, current_path):
            for element in elem_list:
                element_type = type(element).__name__
                element_name = getattr(element, 'name', 'unnamed')
                full_path = f"{current_path}.{element_name}" if current_path else element_name

                if element_type in ['WhileLoop', 'ForLoop']:
                    # This is an array structure
                    array_context = self._get_array_context(element_name, element_type)
                    size = self._prompt_array_size(element_name, element_type, array_context)
                    array_info.append({
                        'path': full_path,
                        'name': element_name,
                        'type': element_type,
                        'size': size
                    })

                    # Recursively check children for nested arrays
                    if hasattr(element, 'data') and element.data:
                        collect_from_elements(element.data, full_path)

                # Check nested structures
                elif hasattr(element, 'data') and element.data:
                    collect_from_elements(element.data, full_path)

        collect_from_elements(elements, path)
        return array_info

    def _collect_array_info_with_defaults(self, elements, path=""):
        """
        Recursively collect information about arrays with default size of 1 example.
        Used for non-interactive/automated template generation.
        """
        array_info = []

        def collect_from_elements(elem_list, current_path):
            for element in elem_list:
                element_type = type(element).__name__
                element_name = getattr(element, 'name', 'unnamed')
                full_path = f"{current_path}.{element_name}" if current_path else element_name

                if element_type in ['WhileLoop', 'ForLoop']:
                    # Default: generate 1 example for each loop
                    array_info.append({
                        'path': full_path,
                        'name': element_name,
                        'type': element_type,
                        'size': 1  # Default: 1 example
                    })

                    # Recursively check children for nested arrays
                    if hasattr(element, 'data') and element.data:
                        collect_from_elements(element.data, full_path)

                # Check nested structures
                elif hasattr(element, 'data') and element.data:
                    collect_from_elements(element.data, full_path)

        collect_from_elements(elements, path)
        return array_info

    def _get_field_metadata(self, field_name, type_name):
        """
        Extract field metadata including type, options (for enums), min/max, etc.

        Returns:
            dict: Field metadata for UI form generation
        """
        metadata = {
            "type": type_name,
            "required": True
        }

        # Check if it's an enum
        if self._has_enum(type_name):
            enum_obj = self._get_enum(type_name)
            if enum_obj:
                options = []
                if isinstance(enum_obj, dict):
                    values_dict = enum_obj.get('values', {})
                    if values_dict:
                        options = list(values_dict.keys())
                elif hasattr(enum_obj, 'values') and enum_obj.values:
                    options = list(enum_obj.values.keys())

                metadata["fieldType"] = "enum"
                metadata["options"] = options
                metadata["default"] = options[0] if options else ""
            return metadata

        # Handle basic types
        type_lower = type_name.lower() if type_name else ""

        if 'uint' in type_lower or 'int' in type_lower:
            metadata["fieldType"] = "integer"
            metadata["default"] = 0

            # Extract size for range hints
            if 'uint-8' in type_lower:
                metadata["min"] = 0
                metadata["max"] = 127
            elif 'uint-16' in type_lower:
                metadata["min"] = 0
                metadata["max"] = 32767
            elif 'uint-32' in type_lower:
                metadata["min"] = 0
                metadata["max"] = 2147483647
            elif 'uint-64' in type_lower:
                metadata["min"] = 0
                metadata["max"] = 9223372036854775807

        elif 'boolean' in type_lower:
            metadata["fieldType"] = "boolean"
            metadata["default"] = False

        elif 'float' in type_lower:
            metadata["fieldType"] = "float"
            metadata["default"] = 0.0

        elif 'ipv4' in type_lower:
            metadata["fieldType"] = "ipv4"
            metadata["default"] = "192.168.1.1"

        elif 'ipv6' in type_lower:
            metadata["fieldType"] = "ipv6"
            metadata["default"] = "2001:db8::1"

        elif 'string' in type_lower or 'name' in type_lower:
            metadata["fieldType"] = "string"
            metadata["default"] = ""

            # Check for fixed-string size
            if '.' in type_name:
                namespace, type_local_name = type_name.rsplit('.', 1)
                if (hasattr(self.schema, 'types') and
                        hasattr(self.schema.types, 'namespaces') and
                        namespace in self.schema.types.namespaces):
                    namespace_obj = self.schema.types.namespaces[namespace]
                    if type_local_name in namespace_obj and isinstance(namespace_obj[type_local_name], str):
                        metadata["maxLength"] = 255  # Could extract actual size if needed

        else:
            # Unknown type - treat as string
            metadata["fieldType"] = "string"
            metadata["default"] = ""

        return metadata

    def _process_elements_with_metadata(self, elements, template_dict, schema_dict, array_info=None, interactive=False):
        """
        Process elements and build both template (with defaults) and schema (with metadata).
        """
        if not elements:
            return

        if array_info is None:
            array_info = []

        # Ensure elements is iterable
        if not isinstance(elements, (list, tuple)):
            return

        for element in elements:
            element_type = type(element).__name__

            if element_type == 'DataField':
                # Simple data field
                field_name = element.name
                field_type = element.type
                default_value = self._get_default_value_for_field(field_name, field_type)

                template_dict[field_name] = default_value
                schema_dict[field_name] = self._get_field_metadata(field_name, field_type)

            elif element_type == 'IfCondition':
                # Boolean condition field
                condition_value = self._get_default_value_for_type(element.condition)
                template_dict[element.name] = condition_value
                schema_dict[element.name] = {
                    "type": element.condition,
                    "fieldType": "boolean",
                    "default": condition_value,
                    "required": True
                }

                # Process the body if condition is True
                if condition_value and hasattr(element, 'body') and element.body:
                    template_dict[element.name] = {}
                    schema_dict[element.name]["fields"] = {}
                    self._process_elements_with_metadata(
                        element.body,
                        template_dict[element.name],
                        schema_dict[element.name]["fields"],
                        array_info,
                        interactive
                    )

            elif element_type in ['WhileLoop', 'ForLoop']:
                # Array structures
                array_size = self._get_array_size_for_element(element.name, element.name, array_info)

                template_dict[element.name] = []
                item_template = {}
                item_schema = {}

                children = self._get_element_children(element)

                # Check if the loop contains a Switch (discriminated union pattern)
                has_switch_child = False
                switch_element = None
                if children and len(children) == 1:
                    child = children[0]
                    if type(child).__name__ == 'Switch':
                        has_switch_child = True
                        switch_element = child

                if has_switch_child and switch_element:
                    # Generate switch-based schema for discriminated union
                    switch_selector = getattr(switch_element, 'selector', None)
                    switch_cases = getattr(switch_element, 'cases', [])

                    # Build options dict with each case's schema
                    options = {}
                    for case_element in switch_cases:
                        case_name = getattr(case_element, 'name', None)
                        case_type = type(case_element).__name__

                        # Skip Nil and Error cases
                        if case_type in ['Nil', 'Error'] or not case_name:
                            continue

                        # Generate schema for this case
                        case_schema = {}
                        if case_type == 'VarArray':
                            var_type = getattr(case_element, 'type', 'uint-32')
                            case_schema = {
                                "type": "var-array",
                                "fieldType": "array",
                                "itemType": var_type,
                                "itemSchema": self._get_field_metadata(case_name, var_type),
                                "default": []
                            }
                        else:
                            # Process other case types
                            case_template = {}
                            self._process_elements_with_metadata([case_element], case_template, case_schema, array_info, interactive)

                        options[case_name] = {
                            "label": case_name.replace('-', ' ').title(),
                            "schema": case_schema
                        }

                    # Create switch schema
                    item_schema = {
                        "fieldType": "switch",
                        "discriminator": switch_selector,
                        "options": options
                    }

                    # For template, add examples (already generated by footprint_generator)
                    # Keep existing template structure
                    if children:
                        self._process_elements_with_metadata(children, item_template, item_schema, array_info, interactive)
                else:
                    # Regular ForLoop - process normally
                    if children:
                        self._process_elements_with_metadata(children, item_template, item_schema, array_info, interactive)

                        # Add examples to template
                        for i in range(array_size):
                            example_iteration = dict(item_template)
                            if 'port' in example_iteration:
                                example_iteration['port'] = i + 1
                            template_dict[element.name].append(example_iteration)

                schema_dict[element.name] = {
                    "type": "array",
                    "fieldType": "array",
                    "itemSchema": item_schema,
                    "default": []
                }

            elif element_type == 'FixedArray':
                # Fixed-size arrays - don't pre-generate all items
                # UI will decide how many items to include (up to max size)
                # Backend will pad with defaults
                array_size = getattr(element, 'size', 3)
                try:
                    array_size = int(array_size)
                except:
                    array_size = 3

                array_type = getattr(element, 'array_type', None) or getattr(element, 'type', 'uint-32')
                default_value = self._get_default_value_for_type(array_type)

                # Start with empty array - UI controls count up to max size
                template_dict[element.name] = []
                schema_dict[element.name] = {
                    "type": "fixed-array",
                    "fieldType": "fixed-array",
                    "itemType": array_type,
                    "size": array_size,
                    "maxItems": array_size,
                    "editable": True,
                    "default": []
                }

            elif element_type == 'VarArray':
                # Variable arrays
                array_size = self._get_array_size_for_element(element.name, element.name, array_info)
                default_value = self._get_default_value_for_type(getattr(element, 'type', 'uint-32'))
                template_dict[element.name] = [default_value] * array_size
                schema_dict[element.name] = {
                    "type": "var-array",
                    "fieldType": "array",
                    "itemType": getattr(element, 'type', 'uint-32'),
                    "default": []
                }

            elif element_type == 'Clone':
                # Clone creates object with enumeration keys
                if self._has_enum(element.enumeration):
                    enum_obj = self._get_enum(element.enumeration)
                    protocols_name = element.enumeration.split('.')[
                        -1] if '.' in element.enumeration else element.enumeration
                    template_dict[protocols_name] = {}
                    schema_dict[protocols_name] = {"type": "clone", "fieldType": "object", "fields": {}}

                    if isinstance(enum_obj, dict):
                        enum_values = enum_obj.get('values', {})
                        enum_keys = enum_values.keys() if isinstance(enum_values, dict) else []
                    else:
                        enum_keys = enum_obj.values.keys() if hasattr(enum_obj, 'values') and enum_obj.values else []

                    for enum_key in enum_keys:
                        template_dict[protocols_name][enum_key] = {}
                        schema_dict[protocols_name]["fields"][enum_key] = {"type": "object", "fields": {}}
                        self._process_clone_body_with_metadata(
                            element.body,
                            template_dict[protocols_name][enum_key],
                            schema_dict[protocols_name]["fields"][enum_key].get("fields", {})
                        )
                else:
                    # Fallback if enum not found
                    protocols_name = element.enumeration.split('.')[
                        -1] if '.' in element.enumeration else element.enumeration
                    template_dict[protocols_name] = {}
                    schema_dict[protocols_name] = {"type": "clone", "fieldType": "object", "fields": {}}
                    example_item = {}
                    example_schema = {}
                    self._process_clone_body_with_metadata(element.body, example_item, example_schema)
                    template_dict[protocols_name]["example"] = example_item
                    schema_dict[protocols_name]["fields"]["example"] = example_schema

            elif element_type == 'Struct':
                # Nested structures
                template_dict[element.name] = {}
                schema_dict[element.name] = {"type": "object", "fieldType": "object", "fields": {}}

                # Special handling for footprint structures
                if self._handle_footprint_struct(element.name, element, template_dict, interactive):
                    # Footprint handled specially - build schema dynamically using FootprintTemplateGenerator.FOOTPRINT_TYPES
                    # Build options for the discriminated union (switch) where each option is a var-array schema
                    options = {}
                    fp_types = getattr(self.footprint_generator, 'FOOTPRINT_TYPES', {})
                    fp_examples = getattr(self.footprint_generator, 'FOOTPRINT_VALUE_EXAMPLES', {})

                    for code, name in fp_types.items():
                        # Determine item type based on example value (default to uint-32 for ints)
                        example_val = fp_examples.get(name, None)
                        if isinstance(example_val, int):
                            item_type = 'uint-32'
                            item_schema = {
                                "type": item_type,
                                "fieldType": "integer",
                                "default": 0,
                                "min": 0,
                                "max": 4294967295,
                                "required": True
                            }
                        else:
                            # Fallback to string type
                            item_type = 'string'
                            item_schema = {
                                "type": item_type,
                                "fieldType": "string",
                                "default": ""
                            }

                        # Case schema: var-array with appropriate itemType and optional itemSchema for integers
                        case_schema = {
                            "type": "var-array",
                            "fieldType": "array",
                            "itemType": item_type,
                            "default": []
                        }
                        # Add itemSchema for integer-like types to provide UI hints
                        if item_type == 'uint-32':
                            case_schema["itemSchema"] = item_schema

                        options[name] = {
                            "label": name.replace('-', ' ').title(),
                            "schema": case_schema
                        }

                    # Build footprint-values switch itemSchema
                    footprint_item_schema = {
                        "fieldType": "switch",
                        "discriminator": "vsecure.footprint-types",
                        "options": options
                    }

                    # Assign the full footprint schema with dynamic options for both 'or' and 'and'
                    schema_dict[element.name] = {
                        "type": "footprint",
                        "fieldType": "object",
                        "fields": {
                            "relation": {
                                "type": "vsecure.relation",
                                "fieldType": "enum",
                                "options": ["or", "and"],
                                "default": "or",
                                "required": True
                            },
                            "or": {
                                "type": "object",
                                "fieldType": "object",
                                "fields": {
                                    "footprint-values": {
                                        "type": "array",
                                        "fieldType": "array",
                                        "default": [],
                                        "itemSchema": footprint_item_schema,
                                        "required": True
                                    }
                                }
                            },
                            "and": {
                                "type": "object",
                                "fieldType": "object",
                                "fields": {
                                    "footprint-values": {
                                        "type": "array",
                                        "fieldType": "array",
                                        "default": [],
                                        "itemSchema": footprint_item_schema,
                                        "required": True
                                    }
                                }
                            }
                        }
                    }
                else:
                    # Regular struct processing
                    children = self._get_element_children(element)
                    if children and isinstance(children, (list, tuple)) and len(children) > 0:
                        self._process_elements_with_metadata(
                            children,
                            template_dict[element.name],
                            schema_dict[element.name]["fields"],
                            array_info,
                            interactive
                        )

            elif element_type == 'Template':
                # Template reference - resolve it
                template_ref = getattr(element, 'instanceof', None)
                if template_ref:
                    # Special handling for footprint-values templates at root level
                    if template_ref == 'vsecure.footprint-values' or template_ref.endswith('.footprint-values'):
                        # Generate footprint-values template with actual data
                        footprint_template = self.footprint_generator.generate_footprint_template(relation=0)
                        # Extract the footprint-values array from the generated template
                        if 'or' in footprint_template and 'footprint-values' in footprint_template['or']:
                            template_dict[element.name] = footprint_template['or']['footprint-values']
                        else:
                            template_dict[element.name] = []

                        # Build schema for footprint-values array with switch items
                        options = {}
                        fp_types = getattr(self.footprint_generator, 'FOOTPRINT_TYPES', {})
                        fp_examples = getattr(self.footprint_generator, 'FOOTPRINT_VALUE_EXAMPLES', {})

                        for code, name in fp_types.items():
                            # Determine item type based on example value
                            example_val = fp_examples.get(name, None)
                            if isinstance(example_val, int):
                                item_type = 'uint-32'
                                item_schema = {
                                    "type": item_type,
                                    "fieldType": "integer",
                                    "default": 0,
                                    "min": 0,
                                    "max": 4294967295,
                                    "required": True
                                }
                            else:
                                item_type = 'string'
                                item_schema = {
                                    "type": item_type,
                                    "fieldType": "string",
                                    "default": ""
                                }

                            case_schema = {
                                "type": "var-array",
                                "fieldType": "array",
                                "itemType": item_type,
                                "default": []
                            }
                            if item_type == 'uint-32':
                                case_schema["itemSchema"] = item_schema

                            options[name] = {
                                "label": name.replace('-', ' ').title(),
                                "schema": case_schema
                            }

                        footprint_item_schema = {
                            "fieldType": "switch",
                            "discriminator": "vsecure.footprint-types",
                            "options": options
                        }

                        schema_dict[element.name] = {
                            "type": "array",
                            "fieldType": "array",
                            "itemSchema": footprint_item_schema,
                            "default": []
                        }
                    else:
                        # Resolve template into the simple template dict (no schema available)
                        self._resolve_template_with_metadata(template_ref, template_dict, schema_dict)

            elif element_type == 'Composite':
                if hasattr(element, 'body') and element.body:
                    if hasattr(element, 'name') and element.name:
                        template_dict[element.name] = {}
                        schema_dict[element.name] = {"type": "composite", "fieldType": "object", "fields": {}}
                        self._process_elements_with_metadata(
                            element.body,
                            template_dict[element.name],
                            schema_dict[element.name]["fields"],
                            array_info,
                            interactive
                        )
                    else:
                        name = element.composite_type.split('.')[1] if hasattr(element,
                                                                               'composite_type') else 'composite'
                        template_dict[name] = {}
                        schema_dict[name] = {"type": "composite", "fieldType": "object", "fields": {}}
                        self._process_elements_with_metadata(
                            element.body,
                            template_dict[name],
                            schema_dict[name]["fields"],
                            array_info,
                            interactive
                        )

            elif element_type == 'Switch':
                # Switch handling
                if hasattr(element, 'selector'):
                    enum_name = element.selector.split('.')[-1] if '.' in element.selector else element.selector
                    is_named_switch = hasattr(element, 'name') and element.name

                    if is_named_switch:
                        # Nested switch - process all cases directly
                        if hasattr(element, 'cases') and element.cases:
                            for case_element in element.cases:
                                case_type = type(case_element).__name__
                                if case_type not in ['Nil', 'Error']:
                                    self._process_elements_with_metadata([case_element], template_dict, schema_dict,
                                                                         array_info, interactive)
                                    # NOTE: Don't break - process all children for named switches
                    else:
                        # Top-level switch
                        template_dict[enum_name] = {}
                        schema_dict[enum_name] = {"type": "switch", "fieldType": "object", "selector": element.selector,
                                                  "fields": {}}

                        enum_values = self._get_enum(element.selector) if self._has_enum(element.selector) else None
                        if enum_values and hasattr(element, 'cases') and element.cases:
                            # Handle both dict and object enum formats
                            if isinstance(enum_values, dict):
                                enum_dict = enum_values.get('values', {})
                                enum_keys = enum_dict.keys() if isinstance(enum_dict, dict) else []
                            else:
                                enum_keys = enum_values.values.keys() if hasattr(enum_values, 'values') and enum_values.values else []

                            # Find first non-Nil/Error case to use as default
                            selected_key = None
                            for case_element in element.cases:
                                case_name = getattr(case_element, 'name', None)
                                case_type = type(case_element).__name__
                                if case_name and case_type not in ['Nil', 'Error']:
                                    selected_key = case_name
                                    break

                            # If no non-Nil/Error case, use first enum key as fallback
                            if not selected_key:
                                selected_key = next(iter(enum_keys)) if enum_keys else None

                            # Build template and schema for cases
                            for case_element in element.cases:
                                case_name = getattr(case_element, 'name', None)
                                case_type = type(case_element).__name__

                                if case_name:
                                    # Populate template for the selected case
                                    if case_name == selected_key:
                                        template_dict[enum_name][case_name] = {}
                                        # Only build schema/process content if not Nil/Error
                                        if case_type not in ['Nil', 'Error']:
                                            schema_dict[enum_name]["fields"][case_name] = {"type": "object", "fields": {}}
                                            self._process_elements_with_metadata(
                                                [case_element],
                                                template_dict[enum_name][case_name],
                                                schema_dict[enum_name]["fields"][case_name]["fields"],
                                                array_info,
                                                interactive
                                            )
                                    elif case_type not in ['Nil', 'Error']:
                                        # Build schema and template for non-selected cases so UI can switch to them
                                        schema_dict[enum_name]["fields"][case_name] = {"type": "object", "fields": {}}
                                        self._process_elements_with_metadata(
                                            [case_element],
                                            {},  # Don't populate template
                                            schema_dict[enum_name]["fields"][case_name]["fields"],
                                            array_info,
                                            interactive
                                        )

            elif element_type == 'Overlap':
                # Overlap structures
                template_dict['overlap'] = {}
                schema_dict['overlap'] = {"type": "overlap", "fieldType": "object", "fields": {}}
                children = self._get_element_children(element)
                if children:
                    self._process_elements_with_metadata(
                        children,
                        template_dict['overlap'],
                        schema_dict['overlap']["fields"],
                        array_info,
                        interactive
                    )

            elif isinstance(element, dict) and 'name' in element:
                # Dictionary-style elements
                element_name = element['name']
                if 'type' in element:
                    template_dict[element_name] = self._get_default_value_for_type(element['type'])
                    schema_dict[element_name] = self._get_field_metadata(element_name, element['type'])

            else:
                # Elements without names but with children
                children = self._get_element_children(element)
                if children:
                    if hasattr(element, 'name') and element.name:
                        template_dict[element.name] = {}
                        schema_dict[element.name] = {"type": "unknown", "fieldType": "object", "fields": {}}
                        self._process_elements_with_metadata(
                            children,
                            template_dict[element.name],
                            schema_dict[element.name]["fields"],
                            array_info,
                            interactive
                        )
                    else:
                        self._process_elements_with_metadata(children, template_dict, schema_dict, array_info,
                                                             interactive)

    def _process_clone_body_with_metadata(self, body, target_dict, target_schema):
        """Process the body of a clone element with metadata."""
        if not body:
            return

        if isinstance(body, list):
            for item in body:
                self._process_clone_body_item_with_metadata(item, target_dict, target_schema)
        else:
            self._process_clone_body_item_with_metadata(body, target_dict, target_schema)

    def _process_clone_body_item_with_metadata(self, item, target_dict, target_schema):
        """Process a single item in clone body with metadata."""
        if hasattr(item, 'instanceof'):
            self._resolve_template_with_metadata(item.instanceof, target_dict, target_schema)
        elif hasattr(item, 'name') and hasattr(item, 'type'):
            target_dict[item.name] = self._get_default_value_for_field(item.name, item.type)
            target_schema[item.name] = self._get_field_metadata(item.name, item.type)
        elif hasattr(item, 'data'):
            if hasattr(item, 'name') and item.name:
                target_dict[item.name] = {}
                target_schema[item.name] = {"type": "object", "fields": {}}
                self._process_elements_with_metadata(item.data, target_dict[item.name],
                                                     target_schema[item.name]["fields"])
            else:
                self._process_elements_with_metadata(item.data, target_dict, target_schema)
        else:
            temp_dict = {}
            temp_schema = {}
            self._process_elements_with_metadata([item], temp_dict, temp_schema)
            target_dict.update(temp_dict)
            target_schema.update(temp_schema)

    def _resolve_template_with_metadata(self, template_name, template_dict, schema_dict):
        """Resolve template reference and build both template and schema."""
        # Handle namespace prefixes
        if '.' in template_name:
            namespace, template_local_name = template_name.rsplit('.', 1)

            if (hasattr(self.schema, 'templates') and
                    hasattr(self.schema.templates, 'namespaces') and
                    namespace in self.schema.templates.namespaces):

                namespace_obj = self.schema.templates.namespaces[namespace]

                # Check for structs
                if hasattr(namespace_obj, 'structs') and template_local_name in namespace_obj.structs:
                    template_def = namespace_obj.structs[template_local_name]

                    if hasattr(template_def, 'fields'):
                        for field in template_def.fields:
                            if hasattr(field, 'name') and hasattr(field, 'type'):
                                template_dict[field.name] = self._get_default_value_for_field(field.name, field.type)
                                schema_dict[field.name] = self._get_field_metadata(field.name, field.type)
                        return
                    elif hasattr(template_def, 'data'):
                        self._process_elements_with_metadata(template_def.data, template_dict, schema_dict)
                        return

        # Check global templates
        if hasattr(self.schema, 'templates') and hasattr(self.schema.templates, 'structs'):
            if template_name in self.schema.templates.structs:
                template_def = self.schema.templates.structs[template_name]

                if hasattr(template_def, 'fields') and template_def.fields:
                    for field in template_def.fields:
                        field_type = type(field).__name__
                        if field_type == 'DataField':
                            template_dict[field.name] = self._get_default_value_for_field(field.name, field.type)
                            schema_dict[field.name] = self._get_field_metadata(field.name, field.type)
                    return
                elif hasattr(template_def, 'data') and template_def.data:
                    self._process_elements_with_metadata(template_def.data, template_dict, schema_dict)
                    return

        # Fallback to regular resolution without metadata
        self._resolve_template_reference(template_name, template_dict)

    def _get_array_context(self, element_name, element_type):
        """
        Provide contextual information about what the array represents.
        """
        name_lower = element_name.lower()

        if 'attack' in name_lower:
            return "repeated attack entries"
        elif 'global-data' in name_lower or 'port' in name_lower:
            return "network ports (each element represents data for one port)"
        elif 'event' in name_lower or 'trap' in name_lower:
            return "events or security incidents"
        elif 'counter' in name_lower:
            return "performance counters"
        elif 'application' in name_lower:
            return "application instances"
        elif 'connection' in name_lower:
            return "network connections"
        elif 'history' in name_lower:
            return "historical data points"
        else:
            return f"repeated {element_name} entries"

    def _prompt_array_size(self, element_name, element_type, context):
        """
        Prompt user for array size with intelligent suggestions.
        """
        print(f"\n📋 Array Configuration: {element_name}")
        print(f"   Type: {element_type}")
        print(f"   Context: {context}")

        # Provide smart defaults based on context
        if 'attack' in element_name.lower():
            suggestion = 2
            print(f"   💡 Suggestion: {suggestion} (reasonable default)")
        elif 'port' in element_name.lower() or 'global-data' in element_name.lower():
            suggestion = 2
            print(f"   💡 Suggestion: {suggestion} (common for multi-port scenarios)")
        elif 'history' in element_name.lower():
            suggestion = 10
            print(f"   💡 Suggestion: {suggestion} (good sample size for history)")
        elif 'event' in element_name.lower():
            suggestion = 5
            print(f"   💡 Suggestion: {suggestion} (typical for event samples)")
        else:
            suggestion = 3
            print(f"   💡 Suggestion: {suggestion} (reasonable default)")

        while True:
            try:
                response = input(f"   Enter number of elements (default {suggestion}): ").strip()
                if not response:
                    return suggestion

                size = int(response)
                if size < 0:
                    print("   ❌ Please enter a non-negative number")
                    continue
                elif size == 0:
                    confirm = input("   ⚠️  0 elements means empty array. Continue? (y/n): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        return 0
                    continue
                elif size > 100:
                    confirm = input(f"   ⚠️  {size} is quite large. Continue? (y/n): ").strip().lower()
                    if confirm not in ['y', 'yes']:
                        continue

                return size

            except ValueError:
                print("   ❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n   🚫 Template generation cancelled")
                raise

    def _get_element_children(self, element):
        """
        Get the children of an element, checking for 'data', 'body', or 'fields' attributes.
        This handles all element types consistently.
        """
        if hasattr(element, 'data') and element.data:
            return element.data
        elif hasattr(element, 'body') and element.body:
            return element.body
        elif hasattr(element, 'fields') and element.fields:
            return element.fields
        return None

    def _get_array_size_for_element(self, element_path, element_name, array_info):
        """
        Get the configured size for an array element.
        """
        for info in array_info:
            if info['path'] == element_path or info['name'] == element_name:
                return info['size']
        return 1  # Default size

    def _process_elements(self, elements, template_dict, array_info=None, interactive=False):
        """
        Process XML elements and populate template dictionary with appropriate structure.
        ORIGINAL METHOD - preserved for backwards compatibility with generate_template()
        """
        if not elements:
            return

        if array_info is None:
            array_info = []

        for element in elements:
            element_type = type(element).__name__

            if element_type == 'DataField':
                # Simple data field
                template_dict[element.name] = self._get_default_value_for_field(element.name, element.type)

            elif element_type == 'IfCondition':
                # IfCondition creates a boolean field
                condition_value = self._get_default_value_for_type(element.condition)
                template_dict[element.name] = condition_value

                # Process the body of the IfCondition if the condition is True
                if condition_value and hasattr(element, 'body') and element.body:
                    template_dict[element.name] = {}
                    self._process_elements(element.body, template_dict[element.name], array_info, interactive)

            elif element_type in ['WhileLoop', 'ForLoop']:
                # Array structures
                template_dict[element.name] = []

                # Get configured size for this array
                array_size = self._get_array_size_for_element(element.name, element.name, array_info)

                # Generate multiple iterations based on user choice
                for i in range(array_size):
                    example_iteration = {}
                    # Use helper to get children - checks data, body, or fields
                    children = self._get_element_children(element)
                    if children:
                        self._process_elements(children, example_iteration, array_info, interactive)

                        # For port-related arrays, increment port numbers
                        if 'port' in example_iteration:
                            example_iteration['port'] = i + 1
                    template_dict[element.name].append(example_iteration)

            elif element_type == 'FixedArray':
                # Fixed arrays - don't pre-generate all items
                # Start with empty array, UI decides count up to max size
                array_size = getattr(element, 'size', 3)
                try:
                    array_size = int(array_size)
                except:
                    array_size = 3

                # Create empty array - backend will pad with defaults
                array_type = getattr(element, 'array_type', None) or getattr(element, 'type', 'uint-32')
                template_dict[element.name] = []

            elif element_type == 'VarArray':
                # Variable arrays need size specification
                array_size = self._get_array_size_for_element(element.name, element.name, array_info)
                default_value = self._get_default_value_for_type(getattr(element, 'type', 'uint-32'))
                template_dict[element.name] = [default_value] * array_size

            elif element_type == 'Clone':
                # Clone creates object with enumeration keys
                if self._has_enum(element.enumeration):
                    enum_obj = self._get_enum(element.enumeration)
                    protocols_name = element.enumeration.split('.')[
                        -1] if '.' in element.enumeration else element.enumeration
                    template_dict[protocols_name] = {}
                    # enum_obj may be a dict (e.g. {'values': {...}}) or an Enum instance with .values
                    if isinstance(enum_obj, dict):
                        enum_values = enum_obj.get('values', {})
                        enum_keys = enum_values.keys() if isinstance(enum_values, dict) else []
                    else:
                        enum_keys = enum_obj.values.keys() if hasattr(enum_obj, 'values') and enum_obj.values else []

                    for enum_key in enum_keys:
                        template_dict[protocols_name][enum_key] = {}
                        self._process_clone_body(element.body, template_dict[protocols_name][enum_key])
                else:
                    # Fallback if enum not found
                    protocols_name = element.enumeration.split('.')[
                        -1] if '.' in element.enumeration else element.enumeration
                    template_dict[protocols_name] = {}
                    example_item = {}
                    self._process_clone_body(element.body, example_item)
                    template_dict[protocols_name]["example"] = example_item

            elif element_type == 'Struct':
                # Struct creates nested object
                template_dict[element.name] = {}

                # Special handling for footprint structures
                if self._handle_footprint_struct(element.name, element, template_dict, interactive):
                    # Footprint struct was handled specially
                    pass
                else:
                    # Use helper to get children - checks data, body, or fields
                    children = self._get_element_children(element)
                    if children:
                        self._process_elements(children, template_dict[element.name], array_info, interactive)

            elif element_type == 'Template':
                # Template reference - resolve it
                template_ref = getattr(element, 'instanceof', None)
                if template_ref:
                    # Special handling for footprint-values templates at root level
                    if template_ref == 'vsecure.footprint-values' or template_ref.endswith('.footprint-values'):
                        # Generate footprint-values template with actual data
                        footprint_template = self.footprint_generator.generate_footprint_template(relation=0)
                        # Extract the footprint-values array from the generated template
                        if 'or' in footprint_template and 'footprint-values' in footprint_template['or']:
                            template_dict[element.name] = footprint_template['or']['footprint-values']
                        else:
                            template_dict[element.name] = []
                    else:
                        # Resolve template into the simple template dict (no schema available)
                        self._resolve_template_reference(template_ref, template_dict)
            elif element_type == 'Composite':
                if hasattr(element, 'body') and element.body:
                    if hasattr(element, 'name') and element.name:
                        template_dict[element.name] = {}
                        self._process_elements(element.body, template_dict[element.name], array_info, interactive)
                    else:
                        name = element.composite_type.split('.')[1] if hasattr(element,
                                                                               'composite_type') else 'composite'
                        template_dict[name] = {}
                        self._process_elements(element.body, template_dict[name], array_info, interactive)

            elif element_type == 'Switch':
                # Switch handling - different for top-level vs nested
                if hasattr(element, 'selector'):
                    enum_name = element.selector.split('.')[-1] if '.' in element.selector else element.selector

                    # Check if this switch is named (it's a case itself, like nested switch "changed")
                    is_named_switch = hasattr(element, 'name') and element.name

                    # For named switches (nested cases), process directly into parent
                    if is_named_switch:
                        # This is a switch that IS a case (has a name)
                        # Process all its field cases directly
                        if hasattr(element, 'cases') and element.cases:
                            for case_element in element.cases:
                                case_name = getattr(case_element, 'name', None)
                                case_type = type(case_element).__name__

                                # Skip Nil and Error
                                if case_type in ['Nil', 'Error']:
                                    continue

                                # Process all non-Nil/Error elements
                                if case_name:
                                    # Process the case element's fields directly into template_dict
                                    # Don't nest the case element itself
                                    self._process_elements([case_element], template_dict, array_info, interactive)
                                    # NOTE: Don't break - process all children for named switches
                    else:
                        # Top-level switch - use FIRST enum value as default
                        template_dict[enum_name] = {}
                        switch_dict = template_dict[enum_name]

                        enum_values = self._get_enum(element.selector) if self._has_enum(element.selector) else None
                        if enum_values and hasattr(element, 'cases') and element.cases:
                            # Handle both dict and object enum formats
                            if isinstance(enum_values, dict):
                                enum_dict = enum_values.get('values', {})
                                enum_keys = enum_dict.keys() if isinstance(enum_dict, dict) else []
                            else:
                                enum_keys = enum_values.values.keys() if hasattr(enum_values, 'values') and enum_values.values else []

                            selected_key = next(iter(enum_keys)) if enum_keys else None

                            if selected_key:
                                selected_case = None
                                selected_case_type = None

                                # Find matching case element
                                for case_element in element.cases:
                                    case_name = getattr(case_element, 'name', None)
                                    if case_name == selected_key:
                                        selected_case = case_element
                                        selected_case_type = type(case_element).__name__
                                        break

                                # Only add content if case is NOT Nil or Error
                                if selected_case and selected_case_type not in ['Nil', 'Error']:
                                    switch_dict[selected_key] = {}
                                    self._process_elements([selected_case], switch_dict[selected_key], array_info,
                                                       interactive)

            elif element_type == 'Overlap':
                # Overlap creates a nested structure to preserve hierarchy
                # All overlap children are processed into a nested dict
                template_dict['overlap'] = {}
                children = self._get_element_children(element)
                if children:
                    self._process_elements(children, template_dict['overlap'], array_info, interactive)

            elif isinstance(element, dict) and 'name' in element:
                # Handle dictionary-style elements (from parsed XML)
                element_name = element['name']
                if 'type' in element:
                    template_dict[element_name] = self._get_default_value_for_field(element_name, element['type'])

            # Handle elements that don't have names but might contain other structures
            else:
                # Use helper to get children - checks data, body, or fields
                children = self._get_element_children(element)
                if children:
                    if hasattr(element, 'name') and element.name:
                        template_dict[element.name] = {}
                        self._process_elements(children, template_dict[element.name], array_info)
                    else:
                        self._process_elements(children, template_dict, array_info)

    def _process_clone_body(self, body, target_dict):
        """
        Process the body of a clone element, handling Template objects specially.
        """
        if not body:
            return

        if isinstance(body, list):
            for item in body:
                self._process_clone_body_item(item, target_dict)
        else:
            self._process_clone_body_item(body, target_dict)

    def _process_clone_body_item(self, item, target_dict):
        """
        Process a single item in clone body, handling Template objects.
        """
        # Check if this is a Template object with instanceof reference
        if hasattr(item, 'instanceof'):
            self._resolve_template_reference(item.instanceof, target_dict)
        elif hasattr(item, 'name') and hasattr(item, 'type'):
            # This is a data field
            target_dict[item.name] = self._get_default_value_for_field(item.name, item.type)
        elif hasattr(item, 'data'):
            # This is a struct or container
            if hasattr(item, 'name') and item.name:
                target_dict[item.name] = {}
                self._process_elements(item.data, target_dict[item.name])
            else:
                self._process_elements(item.data, target_dict)
        else:
            # Try to process as a regular element
            temp_dict = {}
            self._process_elements([item], temp_dict)
            target_dict.update(temp_dict)

    def _resolve_template_reference(self, template_name, template_dict):
        """
        Resolve a template reference and add its structure to the template dictionary.
        Includes specialized handling for footprint structures.
        """
        # Special handling for footprint-values templates
        if 'footprint-values' in template_name:
            if hasattr(template_dict, 'get') or isinstance(template_dict, dict):
                # Generate proper footprint-values structure using var-arrays
                template_dict['footprint-values'] = self._generate_footprint_values_template()
                return

        # Special handling for complete footprint structures (or/and templates)
        if template_name in ['vsecure.footprint-values'] and 'footprint' in str(template_dict):
            parent_key = None
            # Check if we're in an 'or' or 'and' context
            for key in ['or', 'and']:
                if key in template_dict:
                    parent_key = key
                    break

            if parent_key:
                template_dict[parent_key] = {
                    'footprint-values': self._generate_footprint_values_template()
                }
                return

        # Handle namespace prefixes
        if '.' in template_name:
            namespace, template_local_name = template_name.rsplit('.', 1)

            if hasattr(self.schema, 'templates'):
                if hasattr(self.schema.templates, 'namespaces'):
                    if namespace in self.schema.templates.namespaces:
                        namespace_obj = self.schema.templates.namespaces[namespace]

                        # Check for templates
                        if hasattr(namespace_obj, 'templates'):
                            if template_local_name in namespace_obj.templates:
                                template_def = namespace_obj.templates[template_local_name]
                                if hasattr(template_def, 'data'):
                                    self._process_elements(template_def.data, template_dict)
                                return

                        # Check for structs
                        if hasattr(namespace_obj, 'structs'):
                            if template_local_name in namespace_obj.structs:
                                template_def = namespace_obj.structs[template_local_name]

                                if hasattr(template_def, 'data'):
                                    self._process_elements(template_def.data, template_dict)
                                elif hasattr(template_def, 'fields'):
                                    self._process_elements(template_def.fields, template_dict)
                                elif hasattr(template_def, 'body'):
                                    self._process_elements([template_def], template_dict)
                                return

                        return

        # Check global templates
        if hasattr(self.schema, 'templates') and hasattr(self.schema.templates, 'structs'):
            if template_name in self.schema.templates.structs:
                template_def = self.schema.templates.structs[template_name]

                # Handle templates with 'fields' attribute (ConvertXml.DataField objects)
                if hasattr(template_def, 'fields') and template_def.fields:
                    for field in template_def.fields:
                        field_type = type(field).__name__
                        if field_type == 'DataField':
                            template_dict[field.name] = self._get_default_value_for_field(field.name, field.type)
                    return

                # Handle templates with 'data' attribute (dictionary objects from XML parsing)
                elif hasattr(template_def, 'data') and template_def.data:
                    for field in template_def.data:
                        if isinstance(field, dict) and 'name' in field and 'type' in field:
                            template_dict[field['name']] = self._get_default_value_for_field(field['name'],
                                                                                             field['type'])
                        elif hasattr(field, 'name') and hasattr(field, 'type'):
                            template_dict[field.name] = self._get_default_value_for_field(field.name, field.type)
                    return

                # Fallback: try to process as elements
                elif hasattr(template_def, 'data'):
                    self._process_elements(template_def.data, template_dict)
                    return

        # Fallback - create placeholder for unknown template
        template_dict[f"template_{template_name.replace('.', '_')}"] = f"TEMPLATE_REF: {template_name}"

    def _handle_footprint_struct(self, struct_name, struct_element, template_dict, interactive=False):
        """
        Handle footprint struct creation with proper relation enum and single operator structure.
        Detects if the struct has a 'relation' field or just 'or'/'and' templates.
        """
        if struct_name == 'footprint':
            # Check if the struct has a relation field by looking at its children
            children = self._get_element_children(struct_element)
            has_relation = False
            if children:
                for child in children:
                    if hasattr(child, 'name') and child.name == 'relation':
                        has_relation = True
                        break

            # If no relation field, just process the children normally (or/and templates)
            if not has_relation:
                # For message 52 style footprint with no relation, process children normally
                if children:
                    self._process_elements(children, template_dict[struct_name], interactive=interactive)
                return True

            # Original logic for footprints with relation field
            if interactive:
                print(f"\n🔍 Configuring Footprint Structure")
                print("Footprint contains 'relation' enum (0=or, 1=and) and corresponding footprint-values")

                # Ask for relation type
                relation_choice = input("Enter relation type (0=or, 1=and, default=0): ")

                try:
                    relation = int(relation_choice) if relation_choice else 0
                    if relation not in [0, 1]:
                        print("⚠️  Invalid relation, using default (0=or)")
                        relation = 0
                except ValueError:
                    relation = 0

                # Ask for footprint configuration
                use_footprint_interactive = input(
                    "Configure footprint types interactively? (y/n, default=n): ").strip().lower()
                if use_footprint_interactive in ['y', 'yes']:
                    footprint_examples = self.footprint_generator._interactive_footprint_selection()
                    footprint_template = self.footprint_generator.generate_footprint_template(
                        relation=relation,
                        footprint_examples=footprint_examples
                    )
                else:
                    # Use default footprint template with specified relation
                    footprint_template = self.footprint_generator.generate_footprint_template(relation=relation)

                template_dict['footprint'] = footprint_template
            else:
                # Non-interactive mode - use defaults (relation=0 for "or")
                template_dict['footprint'] = self.footprint_generator.generate_footprint_template(relation=0)

            return True
        return False

    def _generate_footprint_values_template(self):
        """
        Generate a proper footprint-values template structure using var-arrays.
        Returns dictionary format with field names as keys: {"checksum": [0], "id-number": [2654]}
        """
        # Use FootprintTemplateGenerator to generate proper dictionary format
        # For a named template like "found-values", we need just the footprint-values array
        # Generate with default examples (checksum and id-number)
        footprint_entries = []

        # Default footprint examples: checksum (0) and id-number (2)
        for footprint_type_code in [0, 2]:
            if footprint_type_code in self.footprint_generator.FOOTPRINT_TYPES:
                footprint_name = self.footprint_generator.FOOTPRINT_TYPES[footprint_type_code]
                example_value = self.footprint_generator.FOOTPRINT_VALUE_EXAMPLES.get(footprint_name, 0)

                # Create dictionary format with field name as key
                footprint_entries.append({
                    footprint_name: [example_value]
                })

        return footprint_entries

    def _get_default_value_for_field(self, field_name, type_name):
        """
        Get appropriate default value for a field - with special handling for specific fields.

        Args:
            field_name: Field name (used for smart defaults like attack-id, time, cnt)
            type_name: Field type

        Returns:
            Appropriate default value
        """
        import random
        import time

        field_name_lower = field_name.lower() if field_name else ""

        # Special handling for attack-id: format is "random(2-4 digits)-timestamp"
        if field_name_lower == 'attack-id':
            random_part = random.randint(100, 9999)
            timestamp = int(time.time())
            return f"{random_part}-{timestamp}"

        # Special handling for report-id fields
        if field_name_lower == 'time':
            return int(time.time())

        if field_name_lower == 'cnt':
            return random.randint(1, 9999)

        # Fall back to type-based defaults
        return self._get_default_value_for_type(type_name)

    def _get_default_value_for_type(self, type_name):
        """
        Get appropriate default value for a given type.
        """
        if not type_name:
            return 0

        # Handle namespace prefixes
        if '.' in type_name:
            namespace, type_local_name = type_name.rsplit('.', 1)
        else:
            namespace = None
            type_local_name = type_name

        # Check if it's an enumeration
        if self._has_enum(type_name):
            enum_obj = self._get_enum(type_name)
            if enum_obj:
                # Handle both dict and Enum object formats
                if isinstance(enum_obj, dict):
                    # Deserialized format: {'type': ..., 'values': {...}}
                    values_dict = enum_obj.get('values', {})
                    if values_dict and isinstance(values_dict, dict):
                        first_key = next(iter(values_dict.keys()))
                        return first_key
                elif hasattr(enum_obj, 'values'):
                    # Enum object format
                    if enum_obj.values:
                        first_key = next(iter(enum_obj.values.keys()))
                        return first_key
            return 0

        # Handle basic types
        type_lower = type_local_name.lower()

        if type_lower in ['uint-8', 'uint-16', 'uint-32', 'uint-64']:
            return 0
        elif type_lower in ['boolean-8']:
            return False
        elif type_lower in ['float']:
            return 0.0
        elif type_lower == 'ipv4':
            return "192.168.1.1"
        elif type_lower == 'ipv6':
            return "2001:db8::1"
        elif type_lower == 'ipv4and6':
            return "192.168.1.1"
        elif 'string' in type_lower or 'name' in type_lower:
            return ""
        else:
            # Check if it's a fixed-string type by looking in schema types
            if '.' in type_name:
                namespace, type_local_name = type_name.rsplit('.', 1)
                if (hasattr(self.schema, 'types') and
                        hasattr(self.schema.types, 'namespaces') and
                        namespace in self.schema.types.namespaces):
                    namespace_obj = self.schema.types.namespaces[namespace]
                    # Fixed-strings are stored as string values in the namespace dict
                    if type_local_name in namespace_obj and isinstance(namespace_obj[type_local_name], str):
                        return ""  # Fixed-string type - return empty string

            # For unknown types, return 0 as safe default
            return 0

    def _has_enum(self, enum_name):
        """
        Check if an enumeration exists in the schema.
        """
        if '.' in enum_name:
            namespace, enum_local_name = enum_name.rsplit('.', 1)
            # Check through types.namespaces instead of schema.namespaces
            if (hasattr(self.schema, 'types') and
                    hasattr(self.schema.types, 'namespaces') and
                    namespace in self.schema.types.namespaces):
                namespace_obj = self.schema.types.namespaces[namespace]
                if enum_local_name in namespace_obj:
                    namespace_var = namespace_obj[enum_local_name]
                    return type(namespace_var) is Enum
                return hasattr(namespace_obj, 'enums') and enum_local_name in namespace_obj.enums

        # Check global enums through types
        if (hasattr(self.schema, 'types') and
                hasattr(self.schema.types, 'enums') and
                enum_name in self.schema.types.enums):
            return True

        return False

    def _get_enum(self, enum_name):
        """
        Get enumeration object from schema.
        """
        if '.' in enum_name:
            namespace, enum_local_name = enum_name.rsplit('.', 1)
            # Check through types.namespaces instead of schema.namespaces
            if (hasattr(self.schema, 'types') and
                    hasattr(self.schema.types, 'namespaces') and
                    namespace in self.schema.types.namespaces):
                namespace_obj = self.schema.types.namespaces[namespace]
                if hasattr(namespace_obj, 'enums') and enum_local_name in namespace_obj.enums:
                    return namespace_obj.enums[enum_local_name]

        # Check global enums through types
        if (hasattr(self.schema, 'types') and
                hasattr(self.schema.types, 'enums') and
                enum_name in self.schema.types.enums):
            return self.schema.types.enums[enum_name]

        return None

    def list_available_messages(self):
        """
        Get a list of all available messages in the schema.
        """
        messages = []
        for message_id, message in self.schema.messages.items():
            messages.append({
                'id': int(message_id),
                'name': message.name
            })
        return sorted(messages, key=lambda x: x['id'])
