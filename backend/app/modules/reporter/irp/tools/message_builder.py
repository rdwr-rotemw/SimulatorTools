import struct
from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml


class MessageBuilder:
    """
    Builds binary messages from JSON values by processing fields in JSON order
    while preserving all existing XML data field processing functionality.
    """

    def __init__(self, schema, type_handler):
        self.schema = schema
        self.type_handler = type_handler

    def build_message(self, message_id, values):
        """
        Build a binary message by processing JSON fields in order while preserving
        all existing XML processing functionality for templates, clones, and complex structures.
        """
        message_id_str = str(message_id)
        if message_id_str not in self.schema.messages:
            raise ValueError(f"Message ID {message_id} not found in schema")

        message = self.schema.messages[message_id_str]
        binary_data = b''


        # Process each JSON field in order, but use existing deep processing logic
        for json_key, json_value in values.items():
            # SPECIAL CASE: 'overlap' should always be processed as a whole unit
            # Don't extract its children individually
            if json_key == 'overlap':
                xml_element = self._find_and_process_field(message.data, json_key, json_value)
                if xml_element is not None:
                    binary_data += xml_element
                else:
                    raise ValueError(f"Field '{json_key}' not found in message {message_id}")
            # Skip objects without definitive field values - process their children directly
            elif isinstance(json_value, dict) and not self._has_definitive_value(json_value):
                # This is a nested object, process its children instead
                for child_key, child_value in json_value.items():
                    xml_element = self._find_and_process_field(message.data, child_key, child_value)
                    if xml_element is not None:
                        binary_data += xml_element
                    else:
                        raise ValueError(f"Field '{child_key}' not found in message {message_id}")
            else:
                # This is a field with a definitive value, process normally
                xml_element = self._find_and_process_field(message.data, json_key, json_value)
                if xml_element is not None:
                    binary_data += xml_element
                else:
                    raise ValueError(f"Field '{json_key}' not found in message {message_id}")


        return binary_data

    def _has_definitive_value(self, value):
        """
        Check if a value has a definitive field value (not just nested objects).
        Returns True for primitive values, arrays, or objects that represent enumeration structures.
        Returns False for plain nested objects that should be processed as containers.
        """
        if not isinstance(value, dict):
            return True  # Primitive values, arrays, etc.

        # Check if this looks like an enumeration structure (all values are dictionaries with data)
        all_values_are_dicts = all(isinstance(v, dict) for v in value.values())
        if all_values_are_dicts:
            # Check if the keys look like enumeration values (short names without nested structure)
            enum_like_keys = all(len(k) < 20 and '.' not in k for k in value.keys())
            if enum_like_keys:
                return True  # This looks like an enumeration structure

        # Check if this has primitive values mixed in
        for v in value.values():
            if not isinstance(v, dict):
                return True  # Has primitive values, likely an enumeration

        # All values are dictionaries and it doesn't look like enumeration, this is likely a container object
        return False

    def _find_and_process_field(self, message_data, field_name, field_value):
        """
        Find and process a field using existing deep traversal logic for templates, clones, etc.
        """
        for element in message_data:
            # SPECIAL CASE: Match Overlap elements by field name "overlap"
            if field_name == 'overlap' and type(element).__name__ == 'Overlap':
                return self._process_xml_element(element, field_value)

            # Direct field match
            if hasattr(element, 'name') and element.name == field_name:
                return self._process_xml_element(element, field_value)

            # Deep search in clones - preserve existing clone processing
            elif isinstance(element, ConvertXml.Clone):
                result = self._search_in_clone(element, field_name, field_value)
                if result is not None:
                    return result

            # Deep search in templates - preserve existing template processing
            elif isinstance(element, ConvertXml.Template):
                result = self._search_in_template(element, field_name, field_value)
                if result is not None:
                    return result

            # Deep search in complex structures - preserve existing logic
            elif hasattr(element, 'data') and element.data:
                result = self._find_and_process_field(element.data, field_name, field_value)
                if result is not None:
                    return result

            elif hasattr(element, 'body') and element.body:
                result = self._find_and_process_field(element.body, field_name, field_value)
                if result is not None:
                    return result

            elif hasattr(element, 'fields') and element.fields:
                result = self._find_and_process_field(element.fields, field_name, field_value)
                if result is not None:
                    return result

            # Handle Switch elements - map field name to switch case via selector enum
            elif type(element).__name__ == 'Switch':
                if hasattr(element, 'selector') and element.selector:
                    # Extract enum name from selector (e.g., "httpflood.rules-status" -> "rules-status")
                    enum_name = element.selector.split('.')[-1] if '.' in element.selector else element.selector

                    # If field_name matches the enum name, process and return the switch
                    if field_name == enum_name:
                        return self._process_xml_element(element, field_value)

                    # Also search within switch cases for other fields
                    elif hasattr(element, 'cases') and element.cases:
                        result = self._find_and_process_field(element.cases, field_name, field_value)
                        if result is not None:
                            return result

            # Handle Overlap elements - search their children
            elif type(element).__name__ == 'Overlap':
                if hasattr(element, 'data') and element.data:
                    result = self._find_and_process_field(element.data, field_name, field_value)
                    if result is not None:
                        return result

        return None

    def _search_in_template(self, template, field_name, field_value):
        """
        Search for field in template definition using existing template resolution logic.
        Enhanced to properly expand struct fields from templates for field matching.
        """
        if template.instanceof:
            # Look up the template definition in the schema
            template_def = self._resolve_template_definition(template.instanceof)
            if template_def:
                # CRITICAL: Convert model objects to ConvertXml before processing
                if hasattr(template_def, '__module__') and 'models.data_format_models' in str(template_def.__class__):
                    template_def = self._convert_model_to_convertxml(template_def)

                # Check if the template itself matches the field name
                if hasattr(template_def, 'name') and template_def.name == field_name:
                    return self._process_xml_element(template_def, field_value)

                # If template has fields, search in them
                elif hasattr(template_def, 'fields'):
                    result = self._find_and_process_field(template_def.fields, field_name, field_value)
                    if result is not None:
                        return result

                # If template has data, search in it
                elif hasattr(template_def, 'data'):
                    # SPECIAL CASE: If template data is a single Struct element, unwrap and search inside it
                    # This handles cases like bdos.all-protections-data which has a struct wrapping a Clone
                    if (len(template_def.data) == 1 and
                        isinstance(template_def.data[0], ConvertXml.Struct)):
                        struct = template_def.data[0]
                        # Search in struct's data (which may contain Clones)
                        if hasattr(struct, 'data') and struct.data:
                            result = self._find_and_process_field(struct.data, field_name, field_value)
                            if result is not None:
                                return result
                        # Also search in struct's fields if it has them
                        if hasattr(struct, 'fields') and struct.fields:
                            result = self._find_and_process_field(struct.fields, field_name, field_value)
                            if result is not None:
                                return result
                    else:
                        # Normal case: search directly in template data
                        result = self._find_and_process_field(template_def.data, field_name, field_value)
                        if result is not None:
                            return result

                # NEW: Enhanced template field expansion for structs
                # If the template is a struct, expand its fields to make them available for matching
                if isinstance(template_def, ConvertXml.Struct):
                    # Search directly in the struct's fields
                    if hasattr(template_def, 'fields') and template_def.fields:
                        for field in template_def.fields:
                            if hasattr(field, 'name') and field.name == field_name:
                                return self._process_xml_element(field, field_value)

                            # If field is a nested struct, search recursively
                            if isinstance(field, ConvertXml.Struct):
                                result = self._search_in_struct_fields(field, field_name, field_value)
                                if result is not None:
                                    return result
        return None

    def _search_in_struct_fields(self, struct, field_name, field_value):
        """
        Recursively search for a field within a struct's fields.

        Args:
            struct: The struct to search in
            field_name: The field name to find
            field_value: The value to process for the field

        Returns:
            bytes or None: Processed field data if found, None otherwise
        """
        if hasattr(struct, 'fields') and struct.fields:
            for field in struct.fields:
                if hasattr(field, 'name') and field.name == field_name:
                    return self._process_xml_element(field, field_value)

                # Recursively search in nested structs
                if isinstance(field, ConvertXml.Struct):
                    result = self._search_in_struct_fields(field, field_name, field_value)
                    if result is not None:
                        return result
        return None

    def _search_in_clone(self, clone, field_name, field_value):
        """
        Search for field in clone using existing clone processing logic.
        """
        # Check if the field name matches the enumeration base name (e.g., "protocols" for "trafmon.protocols")
        if clone.enumeration:
            enum_base_name = clone.enumeration.split('.')[-1]
            if field_name == enum_base_name:
                return self._process_xml_element(clone, field_value)

        # Check if the field is in the clone's body
        if clone.body:
            if hasattr(clone.body, 'name') and clone.body.name == field_name:
                return self._process_xml_element(clone.body, field_value)
            elif hasattr(clone.body, 'data') and clone.body.data:
                return self._find_and_process_field(clone.body.data, field_name, field_value)
            elif hasattr(clone.body, 'fields'):
                return self._find_and_process_field(clone.body.fields, field_name, field_value)

        # Check enumeration handling
        if clone.enumeration and hasattr(clone, 'name') and clone.name == field_name:
            return self._process_xml_element(clone, field_value)

        return None

    def _resolve_template_definition(self, instanceof):
        """
        Resolve template definition using robust cross-platform template lookup logic.
        """
        template_def = None

        # First try to find in structs (direct lookup)
        if hasattr(self.schema.templates, 'structs') and instanceof in self.schema.templates.structs:
            template_def = self.schema.templates.structs[instanceof]

        # If not found and it's a namespaced template, try namespace lookup
        elif hasattr(self.schema.templates, 'namespaces') and '.' in instanceof:
            namespace, template_name = instanceof.split('.', 1)

            # Try different namespace lookup strategies for cross-platform compatibility
            if namespace in self.schema.templates.namespaces:
                ns_data = self.schema.templates.namespaces[namespace]

                # Strategy 1: Look for template_name directly in namespace
                if hasattr(ns_data, template_name):
                    template_def = getattr(ns_data, template_name)

                # Strategy 2: Look in namespace structs if it has them
                elif hasattr(ns_data, 'structs') and template_name in ns_data.structs:
                    template_def = ns_data.structs[template_name]

                # Strategy 3: Check if the full name exists in the main structs
                elif instanceof in self.schema.templates.structs:
                    template_def = self.schema.templates.structs[instanceof]

        # Fallback: try all namespaces if direct lookup failed
        elif hasattr(self.schema.templates, 'namespaces'):
            for ns_section, ns_data in self.schema.templates.namespaces.items():
                # Try both with and without namespace prefix
                candidates = [
                    instanceof,
                    f"{ns_section}.{instanceof}",
                    f"{ns_section}.{instanceof.split('.')[-1]}" if '.' in instanceof else f"{ns_section}.{instanceof}"
                ]

                for candidate in candidates:
                    if candidate in self.schema.templates.structs:
                        template_def = self.schema.templates.structs[candidate]
                        break

                    # Also check in namespace attributes
                    template_name = candidate.split('.')[-1]
                    if hasattr(ns_data, template_name):
                        template_def = getattr(ns_data, template_name)
                        break

                if template_def:
                    break


        # If it's a model struct, convert it properly
        if template_def and hasattr(template_def, '__module__') and 'models.data_format_models' in str(template_def.__class__):
            converted_fields = []
            # Use 'data' attribute instead of 'fields' for model structs
            if hasattr(template_def, 'data') and template_def.data:
                # Check if data is a model ForLoop or WhileLoop first
                is_model_loop = hasattr(template_def.data, '__class__') and any(x in str(template_def.data.__class__) for x in ['ForLoop', 'WhileLoop'])

                # Check if data is a single object (like ForLoop) or a list of fields
                if (hasattr(template_def.data, '__iter__') and not isinstance(template_def.data, (str, ConvertXml.ForLoop, ConvertXml.WhileLoop))) and not is_model_loop:
                    # It's iterable and not a single loop object, so iterate over it
                    for field in template_def.data:
                        # Check different ways the field might be structured
                        if hasattr(field, 'name') and hasattr(field, 'type'):
                            converted_fields.append(ConvertXml.DataField(field.name, field.type))
                        elif hasattr(field, 'name') and hasattr(field, 'field_type'):
                            converted_fields.append(ConvertXml.DataField(field.name, field.field_type))
                        elif isinstance(field, ConvertXml.DataField):
                            converted_fields.append(field)
                        elif isinstance(field, ConvertXml.FixedArray):
                            # Handle FixedArray objects directly
                            converted_fields.append(field)
                        elif hasattr(field, 'name') and hasattr(field, 'array_type') and hasattr(field, 'size'):
                            # Handle model FixedArray objects
                            converted_fields.append(ConvertXml.FixedArray(field.name, field.array_type, field.size))
                        elif isinstance(field, dict):
                            if 'name' in field and 'type' in field:
                                converted_fields.append(ConvertXml.DataField(field['name'], field['type']))
                        else:
                            # Try to convert other field types recursively
                            converted = self._convert_model_to_convertxml(field)
                            if converted and converted != field:
                                converted_fields.append(converted)
                else:
                    # It's a single object (ForLoop, WhileLoop, or model version), return it directly
                    return template_def.data

            if converted_fields:
                converted_struct = ConvertXml.Struct(template_def.name, converted_fields)
                return converted_struct
            # If no converted fields but it's a model, still try to convert something
            # Instead of returning the empty model, return what we can
            elif hasattr(template_def, '__module__') and 'models.data_format_models' in str(template_def.__class__):
                # Don't return empty model - at least try basic conversion
                return self._convert_model_to_convertxml(template_def)

        return template_def

    def _convert_model_to_convertxml(self, model_obj):
        """
        Convert model objects to ConvertXml objects.
        Handles model Struct (with 'data' attribute), ForLoop, and WhileLoop.
        """
        from backend.app.modules.reporter.irp.models.data_format_models import Struct as ModelStruct

        # If it's already a ConvertXml object, return as-is
        if hasattr(model_obj, '__class__') and 'ConvertXml' in str(model_obj.__class__):
            return model_obj

        # If it's a model ForLoop or WhileLoop, convert it to ConvertXml
        if hasattr(model_obj, '__class__'):
            class_name = str(model_obj.__class__)
            if 'ForLoop' in class_name:
                # Convert model ForLoop to ConvertXml.ForLoop
                # Model ForLoop has: name, iterations, data (not body)
                # ConvertXml.ForLoop needs: name, iterations, transparent, body
                body = getattr(model_obj, 'data', None) or getattr(model_obj, 'body', None)
                body_items = body if body else []
                converted_body = body_items if isinstance(body_items, list) else [body_items] if body_items else []

                return ConvertXml.ForLoop(
                    name=getattr(model_obj, 'name', 'unknown'),
                    iterations=getattr(model_obj, 'iterations', 'uint-8'),
                    transparent=getattr(model_obj, 'transparent', False),
                    body=converted_body
                )
            elif 'WhileLoop' in class_name:
                # Convert model WhileLoop to ConvertXml.WhileLoop
                body = getattr(model_obj, 'data', None) or getattr(model_obj, 'body', None)
                return ConvertXml.WhileLoop(
                    name=getattr(model_obj, 'name', 'unknown'),
                    data=body or [],
                    stop_at=getattr(model_obj, 'stop_at', None)
                )

        # Handle model Struct objects (they have 'data', not 'fields')
        if isinstance(model_obj, ModelStruct):
            # If the struct's data is a single object (ForLoop, WhileLoop), convert it recursively
            if hasattr(model_obj, 'data') and model_obj.data:
                if hasattr(model_obj.data, '__class__') and any(x in str(model_obj.data.__class__) for x in ['ForLoop', 'WhileLoop']):
                    # Recursively convert the ForLoop/WhileLoop too
                    return self._convert_model_to_convertxml(model_obj.data)

                # If data is a list/iterable, convert the fields
                converted_fields = []
                if hasattr(model_obj.data, '__iter__') and not isinstance(model_obj.data, str):
                    for field in model_obj.data:
                        # Recursively convert field if it's a model object
                        if hasattr(field, '__module__') and 'models.data_format_models' in str(field.__class__):
                            converted = self._convert_model_to_convertxml(field)
                        elif hasattr(field, 'name') and hasattr(field, 'type'):
                            converted = ConvertXml.DataField(field.name, field.type)
                        elif hasattr(field, '__class__') and 'DataField' in str(field.__class__):
                            converted = field  # Already a DataField
                        elif isinstance(field, dict) and 'name' in field and 'type' in field:
                            converted = ConvertXml.DataField(field['name'], field['type'])
                        else:
                            converted = field

                        if converted:
                            converted_fields.append(converted)

                if converted_fields:
                    return ConvertXml.Struct(model_obj.name, converted_fields)
            # Empty struct or no data - return empty ConvertXml struct
            return ConvertXml.Struct(model_obj.name, [])

        # Return as-is if we can't convert it
        return model_obj

    def _process_xml_element(self, xml_element, json_value):
        """
        Process an XML element using the existing processing logic.
        This preserves all the original functionality while allowing JSON-ordered processing.
        """
        # Process data fields using existing type handler logic
        if isinstance(xml_element, ConvertXml.DataField):
            return self._process_data_field(xml_element, json_value)

        # Process while-loops using existing logic
        elif isinstance(xml_element, ConvertXml.WhileLoop):
            return self._process_while_loop(xml_element, json_value)

        # Process for-loops using existing logic
        elif isinstance(xml_element, ConvertXml.ForLoop):
            return self._process_for_loop(xml_element, json_value)

        # Process structs using existing logic
        elif isinstance(xml_element, ConvertXml.Struct):
            return self._process_struct(xml_element, json_value)

        # Process clones using existing logic
        elif isinstance(xml_element, ConvertXml.Clone):
            return self._process_clone(xml_element, json_value)

        # Process composites using existing logic
        elif isinstance(xml_element, ConvertXml.Composite):
            return self._process_composite(xml_element, json_value)

        # Process templates using existing logic
        elif isinstance(xml_element, ConvertXml.Template):
            return self._process_template(xml_element, json_value)

        # Process fixed arrays using existing logic
        elif isinstance(xml_element, ConvertXml.FixedArray):
            return self._process_fixed_array(xml_element, json_value)

        # Handle model objects by converting them first
        elif hasattr(xml_element, '__module__') and 'models.data_format_models' in str(xml_element.__class__):
            converted_element = self._convert_model_to_convertxml(xml_element)
            return self._process_xml_element(converted_element, json_value)

        # Process if-conditions using existing logic
        elif isinstance(xml_element, ConvertXml.IfCondition):
            return self._process_if_condition(xml_element, json_value)

        # Process switch elements recursively - iterate all children that exist in values
        elif type(xml_element).__name__ == 'Switch':
            binary_data = b''

            # Check if this is a NAMED switch (a case of an outer switch)
            is_named_switch = hasattr(xml_element, 'name') and xml_element.name

            if isinstance(json_value, dict) and hasattr(xml_element, 'cases'):
                selected_case_name = None

                # For nested switches, json_value structure is {"case_name": {case_data}}
                # The single key IS the selected case name
                if len(json_value) == 1:
                    # Extract the case name from the single key
                    potential_case_name = list(json_value.keys())[0]

                    # Verify this key matches a case in the switch
                    for case_element in xml_element.cases:
                        case_name = getattr(case_element, 'name', None)
                        if case_name == potential_case_name:
                            selected_case_name = potential_case_name
                            break

                # Encode the selector if we have one
                if selected_case_name and hasattr(xml_element, 'selector') and xml_element.selector:
                    try:
                        selector = xml_element.selector
                        selector_handler = self.type_handler.get(selector)


                        # Call the handler to get full encoding
                        full_encoding = selector_handler(selected_case_name)


                        # Log namespace enum values if available
                        enum_info = None
                        try:
                            if '.' in selector:
                                ns, lname = selector.rsplit('.', 1)
                                types_ns = getattr(getattr(self.schema, 'types', {}), 'namespaces', None) or getattr(self.schema.types, 'namespaces', {}) if hasattr(self.schema, 'types') else None
                                if isinstance(types_ns, dict) and ns in types_ns:
                                    ns_obj = types_ns[ns]
                                    # ns_obj might be dict-like
                                    if isinstance(ns_obj, dict) and lname in ns_obj:
                                        type_def = ns_obj[lname]
                                        if isinstance(type_def, dict):
                                            enum_info = type_def.get('values', None)
                                        else:
                                            enum_info = getattr(type_def, 'values', None)
                            else:
                                enums = getattr(getattr(self.schema, 'types', {}), 'enums', None) or (getattr(self.schema, 'types', 'enums') if False else None)
                                # Fallback attempt: try attribute on schema types
                                if enums and isinstance(enums, dict) and selector in enums:
                                    type_def = enums[selector]
                                    enum_info = type_def.get('values') if isinstance(type_def, dict) else getattr(type_def, 'values', None)
                        except Exception as _e:
                            enum_info = f"error retrieving enum info: {_e}"


                        # Use the full enum encoding returned by the selector handler (do not extract/repack)
                        selector_binary = full_encoding

                    except Exception as e:
                        # Fallback: create implicit enum mapping based on case order
                        case_names = [getattr(c, 'name', None) for c in xml_element.cases if getattr(c, 'name', None)]
                        selector_handler = lambda val, names=case_names: struct.pack('B', names.index(val))
                        self.type_handler.register(xml_element.selector, selector_handler)
                        selector_binary = selector_handler(selected_case_name)

                    # Append selector bytes
                    binary_data += selector_binary

                # Process the selected case content
                if selected_case_name:
                    for child in xml_element.cases:
                        child_name = getattr(child, 'name', None)
                        if child_name and child_name == selected_case_name:
                            if type(child).__name__ not in ['Nil', 'Error']:
                                # Pass the case data (the value from the single-key dict)
                                binary_data += self._process_xml_element(child, json_value[selected_case_name])
                            break
            return binary_data

        # Process overlap elements - ALL children encode from the SAME position
        elif type(xml_element).__name__ == 'Overlap':
            if isinstance(json_value, dict) and hasattr(xml_element, 'data'):
                encoded_children = []

                for child in xml_element.data:
                    child_name = getattr(child, 'name', None)
                    child_type = type(child).__name__

                    # Handle named DataFields
                    if child_name and child_name in json_value:
                        child_value = json_value[child_name]

                        if isinstance(child, ConvertXml.DataField):
                            child_binary = self._process_xml_element(child, child_value)
                            encoded_children.append(child_binary)

                    # Handle Switch elements
                    elif child_type == 'Switch' and hasattr(child, 'selector'):
                        # Extract data key from selector (e.g., "httpflood.rules-status" -> "rules-status")
                        selector_str = child.selector
                        data_key = selector_str.split('.')[-1] if '.' in selector_str else selector_str

                        # Get the switch data
                        if data_key in json_value:
                            switch_data = json_value[data_key]

                            # switch_data should be like: {"changed": {"source": {...}}}
                            # Pass it directly to the Switch encoder
                            child_binary = self._process_xml_element(child, switch_data)
                            encoded_children.append(child_binary)

                if encoded_children:
                    return max(encoded_children, key=len)
                else:
                    return b''
            return b''

        # Process other types as needed
        else:
            raise ValueError(f"Unsupported XML element type: {type(xml_element)}")

    def _process_data_field(self, data_field, value):
        """
        Process a single data field using the existing type handler logic.
        """
        try:
            # SPECIAL CASE: For overlap selector/switch pattern
            # If value is a dict with single key and field type is an enum,
            # extract the key as the enum value (the key represents the selected case)
            if isinstance(value, dict) and len(value) == 1:
                # Check if this looks like an enum type (has dots or ends with common enum suffixes)
                if '.' in data_field.type or 'status' in data_field.type.lower() or 'type' in data_field.type.lower():
                    # Extract the single key as the enum value
                    value = list(value.keys())[0]

            handler = self.type_handler.get(data_field.type)
            return handler(value)
        except Exception as e:
            raise ValueError(f"Failed to process field '{data_field.name}' of type '{data_field.type}': {e}")

    def _process_while_loop(self, while_loop, values):
        """
        Process a while-loop using existing deep traversal logic, but in JSON field order.
        """
        binary_data = b''

        if not isinstance(values, list):
            raise ValueError(f"While-loop '{while_loop.name}' expects a list of values")

        # Process each item in the while-loop using deep search for each JSON field
        for item in values:
            # Process fields in JSON order within each item using deep search
            for json_key, json_value in item.items():
                # First check if this is a definitive field value that should be processed directly
                if not (isinstance(json_value, dict) and not self._has_definitive_value(json_value)):
                    # This is a field with a definitive value or an enumeration structure, process normally
                    found_element = self._find_and_process_field(while_loop.data, json_key, json_value)
                    if found_element is not None:
                        binary_data += found_element
                    else:
                        raise ValueError(f"Field '{json_key}' not found in while-loop '{while_loop.name}'")
                else:
                    # This is a nested object without definitive values, process its children
                    for child_key, child_value in json_value.items():
                        found_element = self._find_and_process_field(while_loop.data, child_key, child_value)
                        if found_element is not None:
                            binary_data += found_element
                        else:
                            raise ValueError(f"Field '{child_key}' not found in while-loop '{while_loop.name}'")

        # Add sentinel value if specified (preserving existing logic)
        if while_loop.stop_at:
            sentinel_value = int(while_loop.stop_at)
            binary_data += struct.pack('<I', sentinel_value)

        return binary_data

    def _process_for_loop(self, for_loop, values):
        """
        Process a for-loop using existing deep traversal logic, but in JSON field order.
        Implements Java for-loop behavior correctly: ALWAYS encode iteration count first.
        """
        binary_data = b''

        # Handle the case where values is a dict containing the actual array
        if isinstance(values, dict) and len(values) == 1:
            # Extract the actual array from the dict
            actual_values = list(values.values())[0]
            if isinstance(actual_values, list):
                values = actual_values

        if not isinstance(values, list):
            raise ValueError(f"For-loop '{for_loop.name}' expects a list of values")

        # CRITICAL Java behavior: ALWAYS encode iteration count first
        # This happens in ForLoopField.encodeIterations() before processing iterations
        iteration_handler = self.type_handler.get(for_loop.iterations)
        binary_data += iteration_handler(len(values))

        # Check if this is a footprint-values for-loop with switch inside
        if for_loop.name == 'footprint-values':
            # For footprint-values, use specialized processing that handles the switch
            # Don't add another iteration count since it was already added above
            return binary_data + self._process_footprint_values_switch_iterations(for_loop, values)

        # Process each iteration using deep search for each JSON field
        for item in values:
            if isinstance(item, dict):
                for json_key, json_value in item.items():
                    # Skip objects without definitive field values - process their children directly
                    if isinstance(json_value, dict) and not self._has_definitive_value(json_value):
                        # This is a nested object, process its children instead
                        for child_key, child_value in json_value.items():
                            found_element = self._find_and_process_field(for_loop.body, child_key, child_value)
                            if found_element is not None:
                                binary_data += found_element
                            else:
                                raise ValueError(f"Field '{child_key}' not found in for-loop '{for_loop.name}'")
                    else:
                        # This is a field with a definitive value, process normally
                        found_element = self._find_and_process_field(for_loop.body, json_key, json_value)
                        if found_element is not None:
                            binary_data += found_element
                        else:
                            raise ValueError(f"Field '{json_key}' not found in for-loop '{for_loop.name}'")

        return binary_data

    def _process_footprint_values_switch_iterations(self, for_loop, values):
        """
        Process the iterations of a footprint-values for-loop that contains a switch.
        This method only processes the iteration data, NOT the iteration count.

        Args:
            for_loop: The for-loop definition
            values: List of footprint entries

        Returns:
            bytes: Encoded binary data for all iterations (without iteration count)
        """
        binary_data = b''

        # Map footprint type names to their enum codes (from vsecure.footprint-types)
        footprint_type_codes = {
            "checksum": 0,
            "sequence-number": 1,
            "id-number": 2,
            "dns-id": 3,
            "dns-qname": 4,
            "dns-subdomain": 5,
            "dns-qcount": 6,
            "source-port": 7,
            "source-ip": 8,
            "fragment-offset": 9,
            "flow-label": 10,
            "tos": 11,
            "packet-size": 12,
            "destination-port": 13,
            "destination-ip": 14,
            "fragment": 15,
            "message-type": 19,
            "ttl": 20,
            "context-tag": 28,
            "dns-ancount": 30,
            "dns-flags": 31
        }

        # Handle empty values case
        if not values or len(values) == 0:
            return binary_data

        # Process each footprint entry (iteration data only)
        for item in values:
            if isinstance(item, dict):
                # Each item should have exactly one key (the footprint type name)
                for footprint_type_name, footprint_values in item.items():
                    if footprint_type_name in footprint_type_codes:
                        # Encode the switch selector (footprint type enum)
                        type_code = footprint_type_codes[footprint_type_name]
                        selector_handler = self.type_handler.get('vsecure.footprint-types')
                        binary_data += selector_handler(type_code)

                        # Encode the var-array
                        if isinstance(footprint_values, list):
                            # Encode var-array size (uint-8)
                            size_handler = self.type_handler.get('uint-8')
                            binary_data += size_handler(len(footprint_values))

                            # Encode each value in the var-array
                            for value in footprint_values:
                                # Determine the appropriate type handler based on footprint type
                                if footprint_type_name in ['source-ip', 'destination-ip']:
                                    value_handler = self.type_handler.get('ipv4and6')
                                elif footprint_type_name in ['dns-qname', 'dns-subdomain']:
                                    # Use the specific namespace types
                                    value_handler = self.type_handler.get(f'vsecure.{footprint_type_name}')
                                else:
                                    # Most footprint types use uint-32
                                    value_handler = self.type_handler.get('uint-32')

                                binary_data += value_handler(value)
                        else:
                            raise ValueError(f"Footprint values for '{footprint_type_name}' must be a list")
                    else:
                        raise ValueError(f"Unknown footprint type: '{footprint_type_name}'. Valid types: {list(footprint_type_codes.keys())}")
            else:
                raise ValueError(f"Footprint entry must be a dictionary, got: {type(item)}")

        return binary_data

    def _process_struct(self, struct, values):
        """
        Process a struct using existing deep traversal logic, but in JSON field order.
        Includes special handling for footprint structures.
        """
        binary_data = b''

        if not isinstance(values, dict):
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        binary_data += self._process_struct(struct, item)
                    else:
                        raise ValueError(f"Struct '{struct.name}' expects a dictionary of values")
            else:
                raise ValueError(f"Struct '{struct.name}' expects a dictionary of values")

        # Special handling for footprint structures that have a relation field
        # Only use special processing if this is actually a footprint struct with relation logic
        if struct.name == 'footprint' and self._has_relation_field(struct):
            return self._process_footprint_struct(struct, values)

        # Process fields in JSON order using deep search
        # Get the fields/data to search in
        search_list = struct.fields if hasattr(struct, 'fields') and struct.fields else (struct.data if hasattr(struct, 'data') and struct.data else [])

        if not search_list:
            raise ValueError(f"Struct '{struct.name}' has no fields or data to process")

        # SPECIAL CASE: If struct has only ONE element, process it directly with all values
        # This handles wrapper structs like <struct name="ipv4"><template instanceof="..."/></struct>
        if len(search_list) == 1:
            single_element = search_list[0]
            return binary_data + self._process_xml_element(single_element, values)

        # SPECIAL CASE: Check if struct contains a Clone that should consume all values at once
        # This handles cases like bdos.all-protections-data where all keys are enum values
        clone_element = None
        for element in search_list:
            if isinstance(element, ConvertXml.Clone):
                clone_element = element
                break

        # If we found a Clone and all JSON keys look like enum values (no nested processing needed),
        # process the entire values dict with the Clone at once
        if clone_element and all(not (isinstance(v, dict) and not self._has_definitive_value(v)) for v in values.values()):
            # All values are definitive (enum-value-like), process the Clone with entire dict
            binary_data += self._process_xml_element(clone_element, values)
        else:
            # Normal field-by-field processing
            for json_key, json_value in values.items():
                # Skip objects without definitive field values - process their children directly
                if isinstance(json_value, dict) and not self._has_definitive_value(json_value):
                    # This is a nested object, process its children instead
                    for child_key, child_value in json_value.items():
                        found_element = self._find_and_process_field(search_list, child_key, child_value)
                        if found_element is not None:
                            binary_data += found_element
                        else:
                            raise ValueError(f"Field '{child_key}' not found in struct '{struct.name}'")
                else:
                    # This is a field with a definitive value, process normally
                    found_element = self._find_and_process_field(search_list, json_key, json_value)
                    if found_element is not None:
                        binary_data += found_element
                    else:
                        raise ValueError(f"Field '{json_key}' not found in struct '{struct.name}'")

        return binary_data

    def _has_relation_field(self, struct):
        """
        Check if a struct has a relation field, indicating it needs special footprint processing.

        Args:
            struct: The struct to check

        Returns:
            bool: True if the struct has a relation field
        """
        if not hasattr(struct, 'fields') or not struct.fields:
            return False

        for field in struct.fields:
            if hasattr(field, 'name') and field.name == 'relation':
                return True
        return False

    def _process_footprint_struct(self, struct, values):
        """
        Special processing for footprint structures.

        For structs with relation field (like message 2):
        - relation=0: encode "or" template with data, "and" template with empty data
        - relation=1: encode "and" template with data, "or" template with empty data

        For structs without relation field:
        - Process templates normally based on the JSON data provided
        """
        binary_data = b''

        # Check if this struct has a relation field
        has_relation = self._has_relation_field(struct)
        relation_value = 0  # default value

        if has_relation:
            # Get the relation value to determine which template has data
            relation_value = values.get('relation', 0)

            # First encode the relation enum
            if 'relation' in values:
                relation_field = None
                for field in struct.fields:
                    if hasattr(field, 'name') and field.name == 'relation':
                        relation_field = field
                        break

                if relation_field:
                    binary_data += self._process_data_field(relation_field, relation_value)
                else:
                    raise ValueError("Relation field not found in footprint struct")

        # Process templates based on whether we have relation logic or not
        if has_relation:
            # Process both "or" and "and" templates with relation-based logic
            binary_data += self._process_relation_based_templates(struct, values, relation_value)
        else:
            # Process templates normally without relation logic
            for json_key, json_value in values.items():
                found_element = self._find_and_process_field(struct.fields, json_key, json_value)
                if found_element is not None:
                    binary_data += found_element
                else:
                    raise ValueError(f"Field '{json_key}' not found in struct '{struct.name}'")

        return binary_data

    def _process_relation_based_templates(self, struct, values, relation_value):
        """
        Process "or" and "and" templates based on relation value.

        Args:
            struct: The struct containing the templates
            values: The JSON values
            relation_value: The relation enum value (0 for "or", 1 for "and")

        Returns:
            bytes: Encoded binary data for both templates
        """
        binary_data = b''

        # Process "or" template
        or_template_field = None
        for field in struct.fields:
            if (hasattr(field, 'name') and field.name == 'or' and
                    isinstance(field, ConvertXml.Template)):
                or_template_field = field
                break

        if or_template_field:

            # Relation=0 means "or" template has data
            template_data = values['or']
            if isinstance(template_data, dict) and 'footprint-values' in template_data:
                    # Correctly extract the footprint-values array
                    footprint_values = template_data['footprint-values']
                    binary_data += self._process_template(or_template_field, footprint_values)

        else:
            raise ValueError("Template field 'or' not found in footprint struct")

        # Process "and" template
        and_template_field = None
        for field in struct.fields:
            if (hasattr(field, 'name') and field.name == 'and' and
                    isinstance(field, ConvertXml.Template)):
                and_template_field = field
                break

        if and_template_field:
            if relation_value == 1 and 'and' in values:
                # Relation=1 means "and" template has data
                template_data = values['and']
                if isinstance(template_data, dict) and 'footprint-values' in template_data:
                    # Correctly extract the footprint-values array
                    footprint_values = template_data['footprint-values']
                    binary_data += self._process_template(and_template_field, footprint_values)
                else:
                    # No valid footprint-values found, process as empty
                    binary_data += self._process_template(and_template_field, [])
            else:
                # Relation=0 or no "and" data means empty "and" template
                binary_data += self._process_template(and_template_field, [])
        else:
            raise ValueError("Template field 'and' not found in footprint struct")

        return binary_data

    def _process_clone(self, clone, values):
        """
        Process a clone using existing logic, preserving enumeration handling.
        Handles both single element and list of elements in clone body.
        """
        binary_data = b''

        # Process the enumeration with values being a dictionary of enum_key -> template_data
        if clone.enumeration and isinstance(values, dict):
            # Each key in values is an enumeration value, each value is the template data
            for enum_key, template_data in values.items():
                # Process only the template/body data for this enumeration value
                # No need to encode the enumeration value itself
                if clone.body:
                    try:
                        # Handle clone body as either a single element or a list of elements
                        if isinstance(clone.body, list):
                            # If body is a list with a single DataField, unwrap the template_data if needed
                            if len(clone.body) == 1:
                                body_element = clone.body[0]
                                # If template_data is a dict with a single key matching the field name, unwrap it
                                if isinstance(template_data, dict) and len(template_data) == 1:
                                    field_name = body_element.name if hasattr(body_element, 'name') else None
                                    if field_name in template_data:
                                        unwrapped_data = template_data[field_name]
                                        template_binary = self._process_xml_element(body_element, unwrapped_data)
                                        binary_data += template_binary
                                    else:
                                        # If the key doesn't match, just process the dict as-is
                                        template_binary = self._process_xml_element(body_element, template_data)
                                        binary_data += template_binary
                                else:
                                    # Not a single-key dict, process normally
                                    template_binary = self._process_xml_element(body_element, template_data)
                                    binary_data += template_binary
                            else:
                                # Multiple elements in body, process each
                                for body_element in clone.body:
                                    template_binary = self._process_xml_element(body_element, template_data)
                                    binary_data += template_binary
                        else:
                            # If body is a single element, process it directly
                            template_binary = self._process_xml_element(clone.body, template_data)
                            binary_data += template_binary
                    except Exception as e:
                        raise ValueError(f"Failed to process template data for enum '{enum_key}': {e}")

        return binary_data

    def _process_composite(self, composite, values):
        """
        Process a composite element, including div-mod composites.
        """
        # if isinstance(composite, ConvertXml.DivModComposite):
        #     return self._process_div_mod_composite(composite, values)
        composite = self.get_composite_type(composite)

        # Existing logic for other composite types
        binary_data = b''
        if isinstance(composite, ConvertXml.DivModComposite):
            binary_data += self._process_div_mod_composite(composite, values)
        else:
            for json_key, json_value in values.items():
                found_element = self._find_and_process_field(composite.body, json_key, json_value)
                if found_element is not None:
                    binary_data += found_element
                else:
                    raise ValueError(f"Field '{json_key}' not found in composite")

        return binary_data

    def get_composite_type(self, composite):
        """
        Determine the composite type (e.g., 'div-mod').

        Args:
            composite (ConvertXml.Composite): The composite structure.

        Returns:
            str: The type of the composite ('div-mod', etc.) or None if unknown.
        """
        if "." in composite.composite_type:
            ns_base, ns_type = composite.composite_type.split(".")
            if 'composite' in self.schema.types.namespaces[ns_base] and ns_type == \
                    self.schema.types.namespaces[ns_base]['composite']['@name']:
                composite_def = self.schema.types.namespaces[ns_base]['composite']
                if 'div-mod' in composite_def:
                    quotient_type = composite.body[0].type
                    remainder_type = composite.body[1].type
                    return ConvertXml.DivModComposite(int(composite_def['div-mod']['@denominator']),
                                                      composite_def['div-mod']['@type'], quotient_type, remainder_type)
        return composite

    def _process_div_mod_composite(self, composite, values):
        """
        Process a div-mod composite type during message building.

        Args:
            composite (ConvertXml.DivModComposite): The div-mod composite structure.
            values (dict): The JSON values for the composite.

        Returns:
            bytes: Encoded binary data for the div-mod composite.
        """
        values_list = list(values.values())
        quotient = values_list[0]
        remainder = values_list[1]

        if quotient is None or remainder is None:
            raise ValueError("Missing 'quotient' or 'remainder' values for div-mod composite")

        # Convert string values to their corresponding enum values if applicable
        if isinstance(quotient, str):
            quotient = self._resolve_enum_value(composite.quotient_type, quotient)
        if isinstance(remainder, str):
            remainder = self._resolve_enum_value(composite.remainder_type, remainder)

        # Calculate the final value using the div-mod logic
        value = quotient * composite.denominator + remainder

        # Encode the final value using the type handler
        try:
            handler = self.type_handler.get(composite.type)
            return handler(value)
        except Exception as e:
            raise ValueError(f"Failed to encode div-mod composite value: {e}")

    def _resolve_enum_value(self, enum_type, value_name):
        """
        Resolve an enumeration value from the schema based on its type and name.

        Args:
            enum_type (str): The type of the enumeration (e.g., 'bdos.protection').
            value_name (str): The name of the enumeration value (e.g., 'udp').

        Returns:
            int: The corresponding integer value of the enumeration.
        """
        if '.' in enum_type:
            namespace, enum_name = enum_type.split('.')
            if namespace in self.schema.types.namespaces:
                namespace_obj = self.schema.types.namespaces[namespace]
                if hasattr(namespace_obj, 'enums') and enum_name in namespace_obj.enums:
                    enum_obj = namespace_obj.enums[enum_name]
                    if value_name in enum_obj.values:
                        return enum_obj.values[value_name]
                elif enum_name in namespace_obj:
                    enum_obj = namespace_obj[enum_name]
                    if hasattr(enum_obj, 'values') and value_name in enum_obj.values:
                        return enum_obj.values[value_name]
        raise ValueError(f"Enumeration value '{value_name}' not found in type '{enum_type}'")

    def _process_template(self, template, values):
        """
        Process a template by looking up its definition and processing accordingly.
        Handles both standalone footprint-values templates and relation-based footprint usage.
        """
        # Look up the template definition first
        if not template.instanceof:
            raise ValueError("Template has no instanceof attribute")

        template_def = self._resolve_template_definition(template.instanceof)

        if not template_def:
            raise ValueError(f"Template definition not found for: {template.instanceof}")

        # CRITICAL: Convert model objects to ConvertXml before processing
        if hasattr(template_def, '__module__') and 'models.data_format_models' in str(template_def.__class__):
            template_def = self._convert_model_to_convertxml(template_def)

        # Special handling for vsecure.footprint-values template
        if (template.instanceof == 'vsecure.footprint-values' or
            (isinstance(template_def, ConvertXml.ForLoop) and template_def.name == 'footprint-values')):

            # Check if this is part of a relation-based footprint struct
            # by examining if the template has a name like "or" or "and"
            is_relation_based = hasattr(template, 'name') and template.name in ['or', 'and']

            if is_relation_based:
                # This is within a footprint struct with relation logic
                # Handle empty values for inactive relation side
                if not values or len(values) == 0:
                    # CRITICAL FIX: Even empty templates must encode iteration count of 0
                    # The Java parser always expects the iteration count, even for empty for-loops
                    if isinstance(template_def, ConvertXml.ForLoop):
                        iteration_handler = self.type_handler.get(template_def.iterations)
                        return iteration_handler(0)  # Encode iteration count of 0
                    elif hasattr(template_def, 'data') and isinstance(template_def.data, ConvertXml.ForLoop):
                        iteration_handler = self.type_handler.get(template_def.data.iterations)
                        return iteration_handler(0)  # Encode iteration count of 0

            # Process the footprint-values for-loop with correct iteration count handling
            if isinstance(template_def, ConvertXml.ForLoop):
                return self._process_for_loop(template_def, values)
            elif hasattr(template_def, 'data') and isinstance(template_def.data, ConvertXml.ForLoop):
                return self._process_for_loop(template_def.data, values)
            elif hasattr(template_def, 'fields') and template_def.fields:
                for field in template_def.fields:
                    if isinstance(field, ConvertXml.ForLoop) and field.name == 'footprint-values':
                        return self._process_for_loop(field, values)

        # For all other templates, process normally
        return self._process_xml_element(template_def, values)


    def _process_fixed_array(self, fixed_array, values):
        """
        Process a fixed array element using the type handler.
        If the provided array has fewer elements than required, it will be padded with zero values.
        """
        binary_data = b''

        if not isinstance(values, list):
            raise ValueError(f"Fixed array '{fixed_array.name}' expects a list of values")

        # Get the expected array size
        try:
            array_size = int(fixed_array.size)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid array size '{fixed_array.size}' for fixed array '{fixed_array.name}'")

        # If array has fewer elements than required, pad with zero values
        if len(values) < array_size:
            # Determine the zero value based on the array type
            zero_value = self._get_zero_value_for_type(fixed_array.array_type)
            padding_needed = array_size - len(values)
            values = values + [zero_value] * padding_needed
        elif len(values) > array_size:
            # If too many elements provided, raise error
            raise ValueError(f"Fixed array '{fixed_array.name}' expects {array_size} elements, got {len(values)}")

        # Process each element using the array type handler
        try:
            element_handler = self.type_handler.get(fixed_array.array_type)
            for value in values:
                binary_data += element_handler(value)
        except Exception as e:
            raise ValueError(
                f"Failed to process fixed array '{fixed_array.name}' of type '{fixed_array.array_type}': {e}")

        return binary_data

    def _get_zero_value_for_type(self, type_name):
        """
        Get the appropriate zero/default value for a given type.
        """
        # Integer types
        if type_name in ['uint-8', 'uint-16', 'uint-32', 'uint-64',
                         'int-8', 'int-16', 'int-32', 'int-64']:
            return 0

        # Float types
        if type_name in ['float', 'double']:
            return 0.0

        # String types
        if type_name in ['string', 'utf8-string']:
            return ""

        # Boolean
        if type_name == 'boolean':
            return False

        # IP addresses
        if type_name in ['ipv4', 'ipv4and6', 'ipv6']:
            return "0.0.0.0"

        # MAC address
        if type_name == 'mac':
            return "00:00:00:00:00:00"

        # Default to 0 for unknown types (likely numeric)
        return 0

    def _create_field_mapping(self, message_data):
        """
        Create a mapping of field names to their XML elements, preserving all processing logic.
        """
        field_mapping = {}

        for element in message_data:
            self._map_element_fields(element, field_mapping)

        return field_mapping

    def _map_element_fields(self, element, field_mapping):
        """
        Recursively map all fields from XML elements to create a lookup dictionary.
        """
        # Map data fields directly
        if isinstance(element, ConvertXml.DataField):
            if element.name:
                field_mapping[element.name] = element

        # Map complex structures by their names
        elif hasattr(element, 'name') and element.name:
            field_mapping[element.name] = element

        # Recursively map nested elements
        if hasattr(element, 'data') and element.data:
            for sub_element in element.data:
                self._map_element_fields(sub_element, field_mapping)

        # Handle other nested structures
        elif hasattr(element, 'body') and element.body:
            for sub_element in element.body:
                self._map_element_fields(sub_element, field_mapping)

        elif hasattr(element, 'fields') and element.fields:
            for sub_element in element.fields:
                self._map_element_fields(sub_element, field_mapping)

    def _process_if_condition(self, if_condition, values):
        """
        Process an if-condition element based on the presence of a field in the JSON values.

        Args:
            if_condition (ConvertXml.IfCondition): The if-condition element to process.
            values (dict): The JSON values to check.

        Returns:
            bytes: Encoded binary data for the if-condition.
        """
        binary_data = b''

        # Check if the condition field exists in the JSON values
        condition_field = if_condition.name
        condition_value = values

        # Encode the condition value as a boolean
        condition_handler = self.type_handler.get(if_condition.condition)
        binary_data += condition_handler(condition_value)

        # If the condition is True, process the body
        if condition_value and if_condition.body:
            for element in if_condition.body:
                element_data = self._process_xml_element(element, values.get(element.name, {}))
                binary_data += element_data


        return binary_data

