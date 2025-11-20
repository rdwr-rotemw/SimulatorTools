class Schema:
    def __init__(self):
        self.messages = None
        self.templates = None
        self.types = None

    def set_messages(self, messages):
        self.messages = messages

    def set_templates(self, templates):
        self.templates = templates

    def set_types(self, types):
        self.types = types

    @staticmethod
    def convert_value_to_type(value, expected_type):
        """
        Convert value to the expected type, handling string-to-int conversions.
        """
        if expected_type in ['uint-32', 'uint-16', 'uint-8', 'int-32', 'int-16', 'int-8']:
            if isinstance(value, str):
                # Handle hyphen-separated values by taking the first part
                if '-' in value:
                    return int(value.split('-')[0])
                # Handle other string numeric values
                try:
                    return int(value)
                except ValueError:
                    return 0
            elif isinstance(value, (int, float)):
                return int(value)
            else:
                return 0
        return value

    @staticmethod
    def prepare_value_for_packing(value, field_type):
        """
        Prepare value for struct.pack operations.
        """
        # Convert string values to appropriate types for binary packing
        if field_type == 'uint-32' or field_type == 'int-32':
            if isinstance(value, str):
                if '-' in value:
                    return int(value.split('-')[0])
                try:
                    return int(value)
                except ValueError:
                    return 0
            return int(value) if value is not None else 0
        elif field_type == 'uint-16' or field_type == 'int-16':
            if isinstance(value, str):
                if '-' in value:
                    return int(value.split('-')[0])
                try:
                    return int(value)
                except ValueError:
                    return 0
            return int(value) if value is not None else 0
        elif field_type == 'uint-8' or field_type == 'int-8':
            if isinstance(value, str):
                if '-' in value:
                    return int(value.split('-')[0])
                try:
                    return int(value)
                except ValueError:
                    return 0
            return int(value) if value is not None else 0
        return value

    @staticmethod
    def safe_int_conversion(value):
        """
        Safely convert any value to integer, handling special string formats.
        """
        if isinstance(value, str):
            # Handle hyphen-separated values like '39-1630605835'
            if '-' in value:
                try:
                    return int(value.split('-')[0])
                except ValueError:
                    return 0
            # Handle regular string numbers
            try:
                return int(value)
            except ValueError:
                return 0
        elif isinstance(value, (int, float)):
            return int(value)
        else:
            return 0

    @staticmethod
    def convert_for_struct_pack(value, struct_format):
        """
        Convert value specifically for struct.pack operations based on format character.
        """
        # Integer formats (unsigned and signed)
        if struct_format in ['I', 'i', 'H', 'h', 'B', 'b', 'L', 'l', 'Q', 'q']:
            return Schema.safe_int_conversion(value)
        # Float formats
        elif struct_format in ['f', 'd']:
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        # String/bytes formats
        elif struct_format in ['s', 'p']:
            if isinstance(value, str):
                return value.encode('utf-8')
            return value
        return value


class Message:
    def __init__(self, name, data):
        self.name = name
        self.data = data


class Templates:
    def __init__(self):
        self.structs = None
        self.namespaces = None

    def set_structs(self, structs):
        self.structs = structs

    def set_namespaces(self, namespaces):
        self.namespaces = namespaces


class Types:
    def __init__(self):
        self.primitives = None
        self.fixed_strings = None
        self.ip_address = None
        self.enums = None
        self.bitmap = None
        self.namespaces = None

    def set_primitives(self, primitives):
        self.primitives = primitives

    def set_fixed_strings(self, fixed_strings):
        self.fixed_strings = fixed_strings

    def set_ip_address(self, ip_address):
        self.ip_address = ip_address

    def set_enums(self, enums):
        self.enums = enums

    def set_bitmap(self, bitmap):
        self.bitmap = bitmap

    def set_namespaces(self, namespaces):
        self.namespaces = namespaces


class Enum:
    def __init__(self, name, var_type, values):
        self.name = name
        self.var_type = var_type
        self.values = values


class Struct:
    def __init__(self, name, data):
        self.name = name
        self.data = data


class Namespace:
    def __init__(self, name, structs):
        self.name = name
        self.structs = structs
