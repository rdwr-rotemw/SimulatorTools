"""
Complete Template Generator - Generates full templates with all fields and defaults.

Uses proven template generation logic to create complete JSON templates with:
- ALL possible fields included
- Appropriate defaults applied based on type
- Loops include one example (user can create/delete more)
- Ready for UI form integration and e2e testing
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml


class CompleteTemplateGenerator:
    """
    Generates complete JSON templates with all possible fields and defaults.
    """

    def __init__(self, xml_file):
        """Initialize the template generator."""
        self.xml_converter = ConvertXml(xml_file)
        self.xml_converter.convert_xml()
        self.schema = self.xml_converter.schema

    def generate_complete_template(self,
                                   message_id: int,
                                   output_file: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate a complete template with all fields and defaults.

        Args:
            message_id: Message ID to generate template for
            output_file: Optional output file path

        Returns:
            Complete template dictionary with all fields
        """
        message_id_str = str(message_id)
        if message_id_str not in self.schema.messages:
            raise ValueError(f"Message ID {message_id} not found in schema")

        message = self.schema.messages[message_id_str]
        template = {}

        # Process all message data fields
        self._process_message_data(message.data, template)

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)

        return template

    def _process_message_data(self, elements, target_dict):
        """
        Process message data elements and populate template.
        Handles all element types: DataField, Struct, Loop, Clone, Template, etc.
        """
        if not elements:
            return

        for element in elements:
            element_type = type(element).__name__

            if element_type == 'DataField':
                # Simple data field
                target_dict[element.name] = self._get_default_for_type(element.type, element.name)

            elif element_type == 'Struct':
                # Nested structure
                target_dict[element.name] = {}
                if hasattr(element, 'data') and element.data:
                    self._process_message_data(element.data, target_dict[element.name])

            elif element_type in ['WhileLoop', 'ForLoop']:
                # Loop - create array with 1 example
                target_dict[element.name] = []
                example = {}
                if hasattr(element, 'data') and element.data:
                    self._process_message_data(element.data, example)
                target_dict[element.name].append(example)

            elif element_type == 'FixedArray':
                # Fixed size array
                size = getattr(element, 'size', 1)
                try:
                    size = int(size)
                except:
                    size = 1
                array_type = getattr(element, 'array_type', None) or getattr(element, 'type', 'uint-32')
                default_val = self._get_default_for_type(array_type, element.name)
                target_dict[element.name] = [default_val] * size

            elif element_type == 'VarArray':
                # Variable array - create with 1 example
                array_type = getattr(element, 'type', 'uint-32')
                default_val = self._get_default_for_type(array_type, element.name)
                target_dict[element.name] = [default_val]

            elif element_type == 'Clone':
                # Clone with enumeration
                if hasattr(element, 'enumeration'):
                    enum_name = element.enumeration.split('.')[-1] if '.' in element.enumeration else element.enumeration
                    target_dict[enum_name] = {}
                    # Try to get enum values
                    enum_values = self._get_enum_values(element.enumeration)
                    if enum_values:
                        for enum_key in enum_values.keys():
                            target_dict[enum_name][enum_key] = {}
                            if hasattr(element, 'body') and element.body:
                                self._process_message_data(element.body, target_dict[enum_name][enum_key])
                    else:
                        # Fallback - just process body once
                        if hasattr(element, 'body') and element.body:
                            self._process_message_data(element.body, target_dict[enum_name])

            elif element_type == 'Template':
                # Template reference
                if hasattr(element, 'instanceof'):
                    self._resolve_template(element.instanceof, target_dict)

            elif element_type == 'Composite':
                # Composite structure
                if hasattr(element, 'body') and element.body:
                    if hasattr(element, 'name') and element.name:
                        target_dict[element.name] = {}
                        self._process_message_data(element.body, target_dict[element.name])
                    else:
                        self._process_message_data(element.body, target_dict)

    def _resolve_template(self, template_name, target_dict):
        """Resolve template reference and add to target."""
        # Handle namespace prefixes
        if '.' in template_name:
            namespace, local_name = template_name.rsplit('.', 1)
        else:
            namespace = None
            local_name = template_name

        # Try to find in schema templates
        if hasattr(self.schema, 'templates'):
            templates_obj = self.schema.templates

            if hasattr(templates_obj, 'structs') and local_name in templates_obj.structs:
                template_def = templates_obj.structs[local_name]
                if hasattr(template_def, 'data') and template_def.data:
                    self._process_message_data(template_def.data, target_dict)
                elif hasattr(template_def, 'fields') and template_def.fields:
                    self._process_message_data(template_def.fields, target_dict)

    def _get_enum_values(self, enum_name):
        """Get enumeration values from schema."""
        if not hasattr(self.schema, 'types'):
            return None

        types_obj = self.schema.types

        # Handle namespace prefixes
        if '.' in enum_name:
            namespace, local_name = enum_name.rsplit('.', 1)
            if hasattr(types_obj, 'namespaces') and namespace in types_obj.namespaces:
                ns_obj = types_obj.namespaces[namespace]
                if hasattr(ns_obj, 'enums') and local_name in ns_obj.enums:
                    enum_obj = ns_obj.enums[local_name]
                    if hasattr(enum_obj, 'values'):
                        return enum_obj.values
        else:
            # Check global enums
            if hasattr(types_obj, 'enums') and enum_name in types_obj.enums:
                enum_obj = types_obj.enums[enum_name]
                if hasattr(enum_obj, 'values'):
                    return enum_obj.values

        return None

    def _get_default_for_type(self, type_name, field_name=""):
        """Get appropriate default value for a type."""
        import random
        import time

        if not type_name:
            return 0

        # Handle namespace prefixes
        if '.' in type_name:
            namespace, local_type = type_name.rsplit('.', 1)
        else:
            namespace = None
            local_type = type_name

        field_lower = field_name.lower() if field_name else ""

        # Special handling for specific fields
        if field_lower == 'attack-id':
            random_part = random.randint(100, 9999)
            timestamp = int(time.time())
            return f"{random_part}-{timestamp}"

        if field_lower == 'time':
            return int(time.time())

        if field_lower == 'cnt':
            return random.randint(1, 9999)

        # Check if it's an enumeration
        enum_values = self._get_enum_values(type_name)
        if enum_values:
            # Return first enum name
            return next(iter(enum_values.keys())) if enum_values else 0

        # Type-based defaults
        type_lower = local_type.lower()

        if type_lower in ['uint-8', 'uint-16', 'uint-32', 'uint-64']:
            return 0
        elif type_lower == 'boolean-8':
            return False
        elif type_lower == 'float':
            return 0.0
        elif type_lower in ['ipv4', 'ipv6', 'ipv4and6']:
            return "192.168.1.1"
        elif 'string' in type_lower or 'name' in type_lower:
            return ""
        else:
            return 0


def generate_complete_template(xml_file: str, message_id: int, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to generate a complete template.

    Args:
        xml_file: Path to XML schema file
        message_id: Message ID to generate
        output_file: Optional output file

    Returns:
        Template dictionary
    """
    generator = CompleteTemplateGenerator(xml_file)
    return generator.generate_complete_template(message_id, Path(output_file) if output_file else None)

