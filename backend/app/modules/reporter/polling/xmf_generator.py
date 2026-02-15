"""XMF (TCL) generator for polling endpoint configurations."""

from typing import List
from backend.app.models.polling import EndpointConfig, FieldValue, FieldType


class XMFGenerator:
    """Generates XMF (TCL) files from multiple endpoint configurations.

    Key behavior:
    - data_source and transaction are generated IN TCL at runtime
    - They use $myIP from SA_getmyip (simulator's own IP)
    - Timestamps are calculated dynamically using user's intervals
    - User only configures the data_structure part
    - Helper procedures are generated ONCE at the top
    - Multiple endpoints are included in a single XMF file
    """

    def __init__(self, endpoints: List[EndpointConfig], pretty_json: bool = True):
        """Initialize XMF generator with multiple endpoints.

        Args:
            endpoints: List of endpoint configurations
            pretty_json: Whether to format JSON with indentation (default: True)
        """
        self.endpoints = endpoints
        self.indent_level = 0
        self.pretty_json = pretty_json

    def generate_xmf(self) -> str:
        """Generate complete XMF content with all endpoints.

        Returns:
            Complete XMF TCL script
        """
        xmf_parts = []

        # 1. Init section with myIP
        xmf_parts.append(self._generate_init_section())

        # 2. Helper procedures (generated once, used by all endpoints)
        xmf_parts.append(self._generate_procedures())

        # 3. Each endpoint's %http_get_action
        for endpoint in self.endpoints:
            xmf_parts.append(self._generate_endpoint(endpoint))

        return "\n\n".join(xmf_parts)

    def _json_indent(self, level: int) -> str:
        """Get JSON indentation string for given level.

        Args:
            level: Indentation level (0 = root)

        Returns:
            Indentation string (spaces or empty if pretty_json is False)
        """
        if not self.pretty_json:
            return ""
        return "  " * level  # 2 spaces per level

    def _json_newline(self) -> str:
        """Get JSON newline character.

        Returns:
            Newline character or empty if pretty_json is False
        """
        return "\\n" if self.pretty_json else ""

    def _generate_init_section(self) -> str:
        """Generate %xml_init_action section."""
        return """%xml_init_action
    set myIP [SA_getmyip]
    set count 0
    # SA_xml_debugflag 1
    # SA_xml_debugfile xml_$myIP.dbg"""

    def _generate_procedures(self) -> str:
        """Generate helper TCL procedures (once, shared by all endpoints)."""
        return """    proc random_int {min max} {
        return [expr {int(rand() * ($max - $min + 1)) + $min}]
    }

    proc random_ipv4 {} {
        return "[random_int 1 255].[random_int 0 255].[random_int 0 255].[random_int 0 255]"
    }

    proc random_fqdn {suffix} {
        set chars "abcdefghijklmnopqrstuvwxyz"
        set domain ""
        for {set i 0} {$i < [random_int 5 10]} {incr i} {
            append domain [string index $chars [random_int 0 [expr {[string length $chars] - 1}]]]
        }
        return "www.$domain$suffix"
    }

    proc random_policy_name {} {
        set num [random_int 1 200]
        return "pol$num"
    }

    proc get_timestamp_offset {seconds_ago} {
        set ctime [clock seconds]
        set target_time [expr {$ctime - $seconds_ago}]
        return [clock format $target_time -format {%Y-%m-%dT%H:%M:%SZ}]
    }
"""

    def _generate_endpoint(self, endpoint: EndpointConfig) -> str:
        """Generate single endpoint's %http_get_action.

        Args:
            endpoint: Single endpoint configuration

        Returns:
            TCL code for this endpoint
        """
        tcl = f"%http_get_action {endpoint.path}\n\n"
        tcl += '    SA_xml_sethttpcontenttype "application/json"\n'
        tcl += '    SA_xml_clear_plain_text\n\n'

        # Generate timestamp variables for THIS endpoint using helper function
        interval = endpoint.polling_interval_seconds
        tcl += '    set last_update [get_timestamp_offset 0]\n'
        tcl += f'    set next_request_time [get_timestamp_offset -{interval}]\n\n'

        # Start JSON
        nl = self._json_newline()
        tcl += f'    SA_xml_append_plain_text "{{{nl}"\n'

        # data_source (ALWAYS THE SAME)
        tcl += self._generate_data_source()

        # transaction (ALWAYS THE SAME PATTERN)
        tcl += self._generate_transaction(endpoint.path)

        # User's data_structure (UNIQUE PER ENDPOINT)
        tcl += self._generate_user_data_structure_for_endpoint(endpoint)

        # Close JSON
        tcl += f'    SA_xml_append_plain_text "{nl}}}"\n'

        return tcl

    def _generate_data_source(self) -> str:
        """Generate data_source (always the same pattern)."""
        nl = self._json_newline()
        ind1 = self._json_indent(1)
        ind2 = self._json_indent(2)
        tcl = f'    SA_xml_append_plain_text "{ind1}\\"data_source\\": {{{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"type\\": \\"defensepro\\",{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"ip\\": \\"$myIP\\",{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"version\\": \\"10.6.0.0\\"{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind1}}},{nl}"\n'
        return tcl

    def _generate_transaction(self, endpoint_path: str) -> str:
        """Generate transaction (always the same pattern)."""
        nl = self._json_newline()
        ind1 = self._json_indent(1)
        ind2 = self._json_indent(2)
        tcl = f'    SA_xml_append_plain_text "{ind1}\\"transaction\\": {{{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"request_url\\": \\"https://$myIP:8790{endpoint_path}\\",{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"response_type\\": \\"complete\\",{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"last_update\\": \\"$last_update\\",{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind2}\\"next_request_time\\": \\"$next_request_time\\"{nl}"\n'
        tcl += f'    SA_xml_append_plain_text "{ind1}}},{nl}"\n'
        return tcl

    def _generate_user_data_structure_for_endpoint(self, endpoint: EndpointConfig) -> str:
        """Generate user's data structure for a specific endpoint.

        Args:
            endpoint: The endpoint configuration

        Returns:
            TCL code for user's data structure
        """
        # Filter out empty arrays (repeat=0)
        non_empty_fields = []
        for key in endpoint.data_structure.keys():
            field_value = endpoint.data_structure[key]

            # Skip arrays with repeat=0
            if field_value.type == FieldType.ARRAY:
                if field_value.repeat == 0:
                    continue
                if field_value.repeat is None and field_value.repeat_min == 0 and field_value.repeat_max == 0:
                    continue

            non_empty_fields.append((key, field_value))

        # Check if single field with same name as data_key (avoid duplication)
        nl = self._json_newline()
        if len(non_empty_fields) == 1 and non_empty_fields[0][0] == endpoint.data_key:
            # Generate field directly without wrapper
            tcl = self._generate_field_value(non_empty_fields[0][0], non_empty_fields[0][1], indent=1, json_level=1, trailing_comma=False)
        else:
            # Multiple fields or different name - wrap in data_key object
            ind1 = self._json_indent(1)
            tcl = f'    SA_xml_append_plain_text "{ind1}\\"{endpoint.data_key}\\": {{{nl}"\n'

            # Generate TCL for non-empty fields only
            for i, (key, field_value) in enumerate(non_empty_fields):
                has_comma = i < len(non_empty_fields) - 1
                tcl += self._generate_field_value(key, field_value, indent=1, json_level=2, trailing_comma=has_comma)

            tcl += f'    SA_xml_append_plain_text "{nl}{ind1}}}"\n'  # Close data_key

        return tcl

    # ...existing code...

    def _generate_field_value(
        self,
        field_name: str,
        field_value: FieldValue,
        indent: int = 0,
        array_index_var: str = None,
        json_level: int = 2,
        trailing_comma: bool = False
    ) -> str:
        """Generate TCL code for a field value (recursive).

        Args:
            field_name: Name of the field
            field_value: FieldValue configuration
            indent: Current TCL indentation level
            array_index_var: Variable name for array index (e.g., "i", "j")
            json_level: Current JSON indentation level
            trailing_comma: Whether to include a trailing comma after this field
        """
        ind = "    " * indent
        json_ind = self._json_indent(json_level)
        nl = self._json_newline()
        comma = f",{nl}" if trailing_comma else ""
        tcl = ""

        if field_value.type == FieldType.STRING:
            mode = getattr(field_value, 'mode', 'fixed')

            # Check for enum options (dropdown fields like protocol, tcp-flag)
            if hasattr(field_value, 'options') and field_value.options:
                # Enum field - use fixed value if set, otherwise pick randomly from options
                if mode == 'fixed' and field_value.value:
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"{field_value.value}\\"{comma}"\n'
                else:
                    # Pick random option
                    options_str = " ".join(field_value.options)
                    tcl += f'{ind}set options [list {options_str}]\n'
                    tcl += f'{ind}set idx [random_int 0 [expr {{[llength $options] - 1}}]]\n'
                    tcl += f'{ind}set val [lindex $options $idx]\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$val\\"{comma}"\n'
            elif mode == 'random':
                # Check if field name suggests it's an attack_id
                if 'attack' in field_name.lower() and 'id' in field_name.lower():
                    # Generate attack_id: {2-4 digits}-{timestamp±random}
                    tcl += f'{ind}set part1 [random_int 10 9999]\n'
                    tcl += f'{ind}set ctime [clock seconds]\n'
                    tcl += f'{ind}set part2 [expr {{$ctime + [random_int -1000 1000]}}]\n'
                    tcl += f'{ind}set attack_id "$part1-$part2"\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$attack_id\\"{comma}"\n'
                elif 'ip' in field_name.lower():
                    # IP address fields (src-ip, dst-ip, etc.)
                    tcl += f'{ind}set val [random_ipv4]\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$val\\"{comma}"\n'
                elif 'fqdn' in field_name.lower() or 'domain' in field_name.lower():
                    # FQDN fields
                    tcl += f'{ind}set val [random_fqdn ".com"]\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$val\\"{comma}"\n'
                elif 'policy' in field_name.lower() and 'name' in field_name.lower():
                    # Policy name fields - use pol{1-200} format
                    tcl += f'{ind}set val [random_policy_name]\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$val\\"{comma}"\n'
                else:
                    # Generic random string (alphanumeric)
                    tcl += f'{ind}set chars "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"\n'
                    tcl += f'{ind}set val ""\n'
                    tcl += f'{ind}for {{set n 0}} {{$n < [random_int 5 15]}} {{incr n}} {{\n'
                    tcl += f'{ind}    append val [string index $chars [random_int 0 [expr {{[string length $chars] - 1}}]]]\n'
                    tcl += f'{ind}}}\n'
                    tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$val\\"{comma}"\n'
            else:
                # Fixed value
                value = field_value.value or ""
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"{value}\\"{comma}"\n'

        elif field_value.type == FieldType.NUMBER:
            mode = getattr(field_value, 'mode', 'fixed')

            if mode == 'random':
                min_val = field_value.min if field_value.min is not None else 0
                max_val = field_value.max if field_value.max is not None else 100
                tcl += f'{ind}set val [random_int {min_val} {max_val}]\n'
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": $val{comma}"\n'
            else:
                # Fixed value
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": {field_value.value}{comma}"\n'

        elif field_value.type == FieldType.BOOLEAN:
            bool_str = "true" if field_value.value else "false"
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": {bool_str}{comma}"\n'

        elif field_value.type == FieldType.NULL:
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": null{comma}"\n'

        elif field_value.type == FieldType.TIMESTAMP:
            # Generate timestamp using helper function
            # User enters positive numbers (e.g., 120 for "120 seconds ago")
            offset = field_value.offset or 0

            if offset == 0:
                # Current time - use pre-generated variable
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$last_update\\"{comma}"\n'
            else:
                # Use helper function with unique variable name based on field
                # get_timestamp_offset 120 → current_time - 120
                ts_var = f'ts_{field_name.replace("-", "_")}'
                tcl += f'{ind}set {ts_var} [get_timestamp_offset {offset}]\n'
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"${ts_var}\\"{comma}"\n'

        elif field_value.type == FieldType.RANDOM:
            min_val = field_value.min if field_value.min is not None else 0
            max_val = field_value.max if field_value.max is not None else 100
            tcl += f'{ind}set val [random_int {min_val} {max_val}]\n'
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": $val{comma}"\n'

        elif field_value.type == FieldType.RANDOM_IPV4:
            tcl += f'{ind}set ip [random_ipv4]\n'
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$ip\\"{comma}"\n'

        elif field_value.type == FieldType.RANDOM_FQDN:
            suffix = field_value.suffix or ".com"
            tcl += f'{ind}set fqdn [random_fqdn "{suffix}"]\n'
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$fqdn\\"{comma}"\n'

        elif field_value.type == FieldType.TEMPLATE:
            # Replace {{INDEX}} with array index variable
            template = field_value.value
            if "{{INDEX}}" in template and array_index_var:
                # Use TCL variable substitution
                template_expr = template.replace("{{INDEX}}", f"${array_index_var}")
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"{template_expr}\\"{comma}"\n'
            else:
                tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"{template}\\"{comma}"\n'

        elif field_value.type == FieldType.RANDOM_COMPOSITE:
            # Generate composite value from parts
            tcl += f'{ind}set composite ""\n'
            for part in field_value.parts or []:
                if part["type"] == "random":
                    part_min = part.get("min", 0) if part.get("min") is not None else 0
                    part_max = part.get("max", 100) if part.get("max") is not None else 100
                    tcl += f'{ind}append composite [random_int {part_min} {part_max}]\n'
                elif part["type"] == "literal":
                    tcl += f'{ind}append composite "{part["value"]}"\n'
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\"$composite\\"{comma}"\n'

        elif field_value.type == FieldType.OBJECT:
            tcl += f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": {{{nl}"\n'

            # Filter out empty arrays from properties
            props = field_value.properties or {}
            non_empty_props = []

            for prop_key, prop_value in props.items():
                # Skip arrays with repeat=0
                if prop_value.type == FieldType.ARRAY:
                    if prop_value.repeat == 0:
                        continue
                    if prop_value.repeat is None and prop_value.repeat_min == 0 and prop_value.repeat_max == 0:
                        continue
                non_empty_props.append((prop_key, prop_value))

            # Generate TCL for non-empty properties only
            for i, (prop_key, prop_value) in enumerate(non_empty_props):
                has_comma = i < len(non_empty_props) - 1
                tcl += self._generate_field_value(prop_key, prop_value, indent + 1, array_index_var, json_level + 1, trailing_comma=has_comma)

            next_ind = self._json_indent(json_level)
            tcl += f'{ind}SA_xml_append_plain_text "{nl}{next_ind}}}{comma}"\n'

        elif field_value.type == FieldType.ARRAY:
            tcl += self._generate_array_field(field_name, field_value, indent, json_level, trailing_comma)

        return tcl

    def _generate_protocol_value(self, field_value: FieldValue, var_name: str, indent: int) -> str:
        """Generate protocol value and store in variable for conditional logic.

        Args:
            field_value: Protocol field configuration
            var_name: Variable name to store protocol value
            indent: Indentation level

        Returns:
            TCL code that generates and stores protocol value
        """
        ind = "    " * indent
        tcl = ""

        mode = getattr(field_value, 'mode', 'fixed')

        if hasattr(field_value, 'options') and field_value.options:
            # Enum field with options
            if mode == 'fixed' and field_value.value:
                tcl += f'{ind}set {var_name} "{field_value.value}"\n'
            else:
                # Pick random option
                options_str = " ".join(field_value.options)
                tcl += f'{ind}set options [list {options_str}]\n'
                tcl += f'{ind}set idx [random_int 0 [expr {{[llength $options] - 1}}]]\n'
                tcl += f'{ind}set {var_name} [lindex $options $idx]\n'
        else:
            # Default to TCP
            tcl += f'{ind}set {var_name} "tcp"\n'

        return tcl

    def _generate_array_field(
        self,
        field_name: str,
        field_value: FieldValue,
        indent: int,
        json_level: int = 2,
        trailing_comma: bool = False
    ) -> str:
        """Generate TCL code for array field."""
        ind = "    " * indent
        json_ind = self._json_indent(json_level)
        nl = self._json_newline()
        comma = f",{nl}" if trailing_comma else ""
        tcl = f'{ind}SA_xml_append_plain_text "{json_ind}\\"{field_name}\\": \\[{nl}"\n'

        # Determine repeat count
        if field_value.repeat:
            count_expr = str(field_value.repeat)
        else:
            repeat_min = field_value.repeat_min if field_value.repeat_min is not None else 1
            repeat_max = field_value.repeat_max if field_value.repeat_max is not None else 10
            count_expr = f'[random_int {repeat_min} {repeat_max}]'

        # Choose unique loop variable based on indent level
        loop_var = chr(ord('i') + indent)  # i, j, k, l, etc.

        tcl += f'{ind}set arr_count_{loop_var} {count_expr}\n'
        tcl += f'{ind}for {{set {loop_var} 0}} {{${loop_var} < $arr_count_{loop_var}}} {{incr {loop_var}}} {{\n'

        # Generate array item
        if field_value.item:
            if field_value.item.type == FieldType.OBJECT:
                # Array of objects
                item_ind = self._json_indent(json_level + 1)
                tcl += f'{ind}    SA_xml_append_plain_text "{item_ind}{{{nl}"\n'

                props = field_value.item.properties or {}
                prop_keys = list(props.keys())

                # Check if we have protocol-dependent fields (tcp-flag depends on protocol)
                has_protocol = 'protocol' in prop_keys
                has_tcp_flag = 'tcp-flag' in prop_keys

                # If we have protocol field, generate it first and track the value
                if has_protocol:
                    protocol_prop = props['protocol']
                    # Generate protocol value and store in variable
                    protocol_var = f'proto_{loop_var}'
                    tcl += self._generate_protocol_value(protocol_prop, protocol_var, indent + 2)

                # Generate all fields with proper comma handling
                generated_count = 0
                for i, prop_key in enumerate(prop_keys):
                    prop_value = props[prop_key]
                    has_comma = i < len(prop_keys) - 1

                    # Skip protocol if already generated
                    if prop_key == 'protocol' and has_protocol:
                        prop_ind = self._json_indent(json_level + 2)
                        comma_str = f",{nl}" if has_comma else ""
                        tcl += f'{ind}        SA_xml_append_plain_text "{prop_ind}\\"{prop_key}\\": \\"${protocol_var}\\"{comma_str}"\n'
                        generated_count += 1
                        continue

                    # Skip tcp-flag if protocol is not TCP
                    if prop_key == 'tcp-flag' and has_tcp_flag and has_protocol:
                        tcl += f'{ind}        if {{${protocol_var} == "tcp"}} {{\n'
                        tcl += self._generate_field_value(prop_key, prop_value, indent + 3, loop_var, json_level + 2, trailing_comma=has_comma)
                        tcl += f'{ind}        }}\n'
                        generated_count += 1
                        continue

                    # Regular field
                    tcl += self._generate_field_value(prop_key, prop_value, indent + 2, loop_var, json_level + 2, trailing_comma=has_comma)
                    generated_count += 1

                # Use TCL variable to conditionally add comma in single append call
                tcl += f'{ind}    set item_suffix ""\n'
                tcl += f'{ind}    if {{${loop_var} < [expr $arr_count_{loop_var} - 1]}} {{\n'
                tcl += f'{ind}        set item_suffix ","\n'
                tcl += f'{ind}    }}\n'
                tcl += f'{ind}    SA_xml_append_plain_text "{nl}{item_ind}}}$item_suffix{nl}"\n'
            else:
                # Array of primitives (not common but supported)
                tcl += self._generate_field_value("", field_value.item, indent + 1, loop_var, json_level + 1, trailing_comma=False)

        tcl += f'{ind}}}\n'

        tcl += f'{ind}SA_xml_append_plain_text "{nl}{json_ind}\\]{comma}"\n'

        return tcl
