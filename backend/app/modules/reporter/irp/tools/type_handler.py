import struct
import ipaddress

class TypeHandler:
    """
    Handles conversion of schema types to binary using struct.pack or custom logic.
    Raises clear errors for unknown or unsupported types.
    """
    def __init__(self, schema_types):
        self.schema_types = schema_types
        self.handlers = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        # Integer types
        self.register('uint-8', self._handle_uint(1, signed=False))
        self.register('uint-16', self._handle_uint(2, signed=False))
        self.register('uint-32', self._handle_uint(4, signed=False))
        self.register('uint-64', self._handle_uint(8, signed=False))
        self.register('int-8', self._handle_uint(1, signed=True))
        self.register('int-16', self._handle_uint(2, signed=True))
        self.register('int-32', self._handle_uint(4, signed=True))
        self.register('int-64', self._handle_uint(8, signed=True))

        # Boolean types (different sizes)
        self.register('boolean-8', self._handle_boolean(1))
        self.register('boolean-16', self._handle_boolean(2))
        self.register('boolean-32', self._handle_boolean(4))
        self.register('boolean', self._handle_boolean(1))  # Default to 8-bit

        # Float types
        self.register('float', self._handle_float)
        self.register('double', self._handle_double)

        # String types
        self.register('string', self._handle_variable_string)
        self.register('domain-name', self._handle_domain_name)

        # IP address types
        self.register('ipv4', self._handle_ipv4)
        self.register('ipv6', self._handle_ipv6)
        self.register('ipv4and6', self._handle_ipv4and6)

        # Register fixed-strings, enums, bitmaps, and custom types dynamically
        for name, size in (self.schema_types.fixed_strings or {}).items():
            self.register(name, self._handle_fixed_string(int(size)))
        for name, enum in (self.schema_types.enums or {}).items():
            self.register(name, self._handle_enum(enum))
        if self.schema_types.bitmap:
            self.register(self.schema_types.bitmap.name, self._handle_bitmap(self.schema_types.bitmap))
        # Namespace types
        for ns, ns_types in (self.schema_types.namespaces or {}).items():
            for tname, tval in ns_types.items():
                if isinstance(tval, int) or isinstance(tval, str):
                    self.register(f"{ns}.{tname}", self._handle_fixed_string(int(tval)))
                elif hasattr(tval, 'values'):
                    self.register(f"{ns}.{tname}", self._handle_enum(tval))

    def register(self, type_name, handler_func):
        self.handlers[type_name] = handler_func

    def get(self, type_name):
        handler = self.handlers.get(type_name)
        if not handler:
            raise ValueError(f"No handler registered for type: {type_name}")
        return handler

    def _handle_uint(self, size, signed=False):
        fmt = {1: 'b' if signed else 'B', 2: 'h' if signed else 'H', 4: 'i' if signed else 'I', 8: 'q' if signed else 'Q'}[size]

        def handler(value, field_name=None):
            try:
                if value is None:
                    raise ValueError(f"Value for packing is None. Ensure the JSON file provides a valid value.")

                # Special handling for Radware attack IDs (format: category-timestamp)
                if isinstance(value, str) and '-' in value and 'attack-id' in str(field_name or ''):
                    return self._handle_radware_attack_id(value, fmt)

                # Handle other hyphen-separated values by taking the first part
                elif isinstance(value, str) and '-' in value:
                    value = value.split('-')[0]

                # Convert to int and pack
                int_value = int(value)
                packed_data = struct.pack(f'<{fmt}', int_value)
                return packed_data
            except ValueError as ve:
                if "invalid literal for int()" in str(ve):
                    raise ValueError(f"Failed to pack value '{value}' as {fmt}: Cannot convert to integer. Check the JSON file format.")
                raise ValueError(f"Failed to pack value '{value}' as {fmt}: {ve}. Check the JSON file and schema definition.")
            except Exception as e:
                raise ValueError(f"Failed to pack value '{value}' as {fmt}: {e}. Check the JSON file and schema definition.")
        return handler

    def _handle_radware_attack_id(self, attack_id_str, fmt):
        """
        Handle Radware attack ID format (e.g., "531-1429625097")
        Convert to uint-32 using a meaningful encoding scheme
        """
        try:
            if '-' not in attack_id_str:
                # If no hyphen, treat as regular integer
                return struct.pack(f'<{fmt}', int(attack_id_str))

            category, timestamp = attack_id_str.split('-', 1)
            category = int(category)
            timestamp = int(timestamp)

            # Option 1: Use the timestamp part (more likely to be unique)
            # Since timestamps are typically larger than 32-bit, we may need to truncate
            if timestamp <= 0xFFFFFFFF:  # Fits in uint-32
                encoded_id = timestamp
            else:
                # Truncate to lower 32 bits
                encoded_id = timestamp & 0xFFFFFFFF

            # Option 2: Combine category and timestamp using bit shifting
            # Use upper 8 bits for category (0-255) and lower 24 bits for timestamp
            # This preserves both parts but limits category to 255 and timestamp precision
            # encoded_id = ((category & 0xFF) << 24) | (timestamp & 0xFFFFFF)

            return struct.pack(f'<{fmt}', encoded_id)

        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid Radware attack ID format '{attack_id_str}': {e}")

    def _handle_boolean(self, size):
        fmt_map = {1: 'B', 2: 'H', 4: 'I'}
        fmt = fmt_map.get(size, 'B')

        def handler(value):
            try:
                # Boolean values should be 0 or 1
                bool_value = 1 if bool(value) else 0
                return struct.pack(f'<{fmt}', bool_value)
            except Exception as e:
                raise ValueError(f"Failed to pack boolean value '{value}': {e}")
        return handler

    def _handle_float(self, value):
        try:
            # 32-bit float
            return struct.pack('<f', float(value))
        except Exception as e:
            raise ValueError(f"Failed to pack float value '{value}': {e}")

    def _handle_double(self, value):
        try:
            # 64-bit double
            return struct.pack('<d', float(value))
        except Exception as e:
            raise ValueError(f"Failed to pack double value '{value}': {e}")

    def _handle_variable_string(self, value):
        try:
            # Variable-length string (null-terminated)
            if not isinstance(value, str):
                value = str(value)
            return value.encode('utf-8') + b'\x00'
        except Exception as e:
            raise ValueError(f"Failed to pack string value '{value}': {e}")

    def _handle_domain_name(self, value):
        try:
            # Domain names are typically null-terminated strings
            if not isinstance(value, str):
                value = str(value)
            return value.encode('utf-8') + b'\x00'
        except Exception as e:
            raise ValueError(f"Failed to pack domain-name value '{value}': {e}")

    def _handle_fixed_string(self, size):
        def handler(value):
            # Ensure the string is properly truncated and padded
            if not isinstance(value, str):
                value = str(value)
            b = value.encode('utf-8')
            if len(b) > size:
                b = b[:size]
            return b.ljust(size, b'\x00')
        return handler

    def _handle_enum(self, enum):
        def handler(value):
            # Accept either name or code
            if value in enum.values:
                code = enum.values[value]
            elif value in enum.values.values():
                code = value
            else:
                raise ValueError(f"Invalid enum value: {value} for {enum.name}")

            # Use the underlying type handler
            base_type = enum.var_type if hasattr(enum, 'var_type') else 'uint-32'
            base_handler = self.get(base_type)

            # Apply appropriate mask based on the underlying type
            if base_type.startswith('uint-') or base_type.startswith('int-'):
                size = int(base_type.split('-')[1]) // 8
                masks = {1: 0xFF, 2: 0xFFFF, 4: 0xFFFFFFFF, 8: 0xFFFFFFFFFFFFFFFF}
                code = int(code) & masks[size]

            return base_handler(code)
        return handler

    def _handle_bitmap(self, bitmap):
        def handler(value):
            try:
                # Bitmaps are typically uint-32 values representing flags
                if isinstance(value, str):
                    # Handle hex strings
                    if value.startswith('0x'):
                        int_value = int(value, 16)
                    else:
                        int_value = int(value)
                else:
                    int_value = int(value)

                # Use uint-32 by default for bitmaps
                base_type = bitmap.var_type if hasattr(bitmap, 'var_type') else 'uint-32'
                base_handler = self.get(base_type)
                return base_handler(int_value)
            except Exception as e:
                raise ValueError(f"Failed to pack bitmap value '{value}': {e}")
        return handler

    def _handle_ipv4(self, value):
        try:
            return ipaddress.IPv4Address(value).packed
        except Exception as e:
            raise ValueError(f"Invalid IPv4 address '{value}': {e}")

    def _handle_ipv6(self, value):
        try:
            return ipaddress.IPv6Address(value).packed
        except Exception as e:
            raise ValueError(f"Invalid IPv6 address '{value}': {e}")

    def _handle_ipv4and6(self, value):
        # For ipv4and6 type with version="dynamic", encode with size prefix
        # Format: [1 byte size][address bytes]
        # IPv4: [4][4 bytes] = 5 bytes total
        # IPv6: [16][16 bytes] = 17 bytes total
        try:
            ip_obj = ipaddress.ip_address(value)
            if isinstance(ip_obj, ipaddress.IPv4Address):
                # IPv4: 1 byte size (4) + 4 bytes address = 5 bytes total
                address_bytes = ip_obj.packed
                return struct.pack('B', len(address_bytes)) + address_bytes
            else:
                # IPv6: 1 byte size (16) + 16 bytes address = 17 bytes total
                address_bytes = ip_obj.packed
                return struct.pack('B', len(address_bytes)) + address_bytes
        except Exception as e:
            raise ValueError(f"Invalid IP address '{value}': {e}")
