import json
from pathlib import Path
from backend.app.modules.reporter.irp.tools.footprint_template_generator import FootprintTemplateGenerator
from backend.app.modules.reporter.irp.models.data_format_models import Enum


class TemplateGenerator:
    """
    Generates JSON templates for IRP messages based on XML schema definitions.
    Creates template files that can be used as starting points for message values.
    Includes specialized handling for footprint structures with var-arrays.
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
                # Loop structures create arrays
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
                # Fixed arrays with predetermined size
                array_size = getattr(element, 'size', 3)
                try:
                    array_size = int(array_size)
                except:
                    array_size = 3

                # Create array with default values based on the array type
                array_type = getattr(element, 'array_type', None) or getattr(element, 'type', 'uint-32')
                default_value = self._get_default_value_for_type(array_type)
                template_dict[element.name] = [default_value] * array_size

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
                    for enum_key in enum_obj.values.keys():
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
                if hasattr(element, 'instanceof'):
                    if hasattr(element, 'name') and element.name:
                        # Named template reference creates a sub-object
                        template_dict[element.name] = {}
                        self._resolve_template_reference(element.instanceof, template_dict[element.name])
                    else:
                        # Unnamed template reference merges into current level
                        self._resolve_template_reference(element.instanceof, template_dict)
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

                                # Process this case as a field with its name
                                if case_name:
                                    # Process the case element's fields directly into template_dict
                                    # Don't nest the case element itself
                                    self._process_elements([case_element], template_dict, array_info, interactive)
                                    break  # Only process first non-empty case as example
                    else:
                        # Top-level switch - use FIRST enum value as default
                        template_dict[enum_name] = {}
                        switch_dict = template_dict[enum_name]

                        enum_values = self._get_enum(element.selector) if self._has_enum(element.selector) else None
                        if enum_values and hasattr(element, 'cases') and element.cases:
                            # Use FIRST enum value (default, usually "none")
                            selected_key = next(iter(enum_values.values.keys()))
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
                                self._process_elements([selected_case], switch_dict[selected_key], array_info, interactive)

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
                    template_dict[element_name] = self._get_default_value_for_type(element['type'])

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
            if hasattr(self.schema, 'templates') and hasattr(self.schema.templates, 'namespaces'):
                if namespace in self.schema.templates.namespaces:
                    namespace_obj = self.schema.templates.namespaces[namespace]
                    if hasattr(namespace_obj, 'templates') and template_local_name in namespace_obj.templates:
                        template_def = namespace_obj.templates[template_local_name]
                        if hasattr(template_def, 'data'):
                            self._process_elements(template_def.data, template_dict)
                        return
                    elif hasattr(namespace_obj, 'structs') and template_local_name in namespace_obj.structs:
                        template_def = namespace_obj.structs[template_local_name]
                        if hasattr(template_def, 'data'):
                            self._process_elements(template_def.data, template_dict)
                        elif hasattr(template_def, 'fields'):
                            self._process_elements(template_def.fields, template_dict)
                        elif hasattr(template_def, 'body'):
                            self._process_elements([template_def], template_dict)
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
                            template_dict[field['name']] = self._get_default_value_for_field(field['name'], field['type'])
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
                relation_choice = input("Enter relation type (0=or, 1=and, default=0): ").strip()
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
            if enum_obj and hasattr(enum_obj, 'values') and enum_obj.values:
                # Return the first enum name instead of its code
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
