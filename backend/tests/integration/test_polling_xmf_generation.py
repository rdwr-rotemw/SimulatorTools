"""Integration tests for Polling XMF (TCL) file generation.

Tests XMFGenerator.generate_xmf() using predefined EndpointConfig mock objects.
No Sapro connection required.

NOTE on XMF string encoding:
  The XMF generator wraps all JSON keys/values in TCL-escaped double-quotes
  (e.g., \\\"data_source\\\"). Assertions that check JSON *content* use the
  _json_output() helper which extracts and unescapes the SA_xml_append_plain_text
  calls into a plain string, so we can search for '"data_source"' naturally.
  Assertions that check TCL *structure* (proc defs, for loops, set commands)
  operate directly on the raw xmf string.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from backend.app.models.polling import EndpointConfig, FieldType, FieldValue
from backend.app.modules.reporter.polling.xmf_generator import XMFGenerator

# ---------------------------------------------------------------------------
# Mock endpoint definitions
# ---------------------------------------------------------------------------

ATTACK_DATA_ENDPOINT = EndpointConfig(
    path="/v1/attack-data",
    data_key="attack_data",
    polling_interval_seconds=60,
    data_structure={
        "attacks": FieldValue(
            type=FieldType.ARRAY,
            repeat=3,
            item=FieldValue(
                type=FieldType.OBJECT,
                properties={
                    "attack-id": FieldValue(type=FieldType.STRING, mode="random"),
                    "src-ip": FieldValue(type=FieldType.RANDOM_IPV4),
                    "dst-ip": FieldValue(type=FieldType.RANDOM_IPV4),
                    "src-port": FieldValue(
                        type=FieldType.NUMBER, mode="random", min=1024, max=65535
                    ),
                    "dst-port": FieldValue(type=FieldType.NUMBER, value=443),
                    "protocol": FieldValue(
                        type=FieldType.STRING,
                        options=["tcp", "udp", "icmp"],
                    ),
                    "tcp-flag": FieldValue(
                        type=FieldType.STRING,
                        options=["SYN", "ACK", "RST", "FIN"],
                    ),
                    "risk": FieldValue(
                        type=FieldType.STRING,
                        options=["high", "medium", "low"],
                    ),
                    "active": FieldValue(type=FieldType.BOOLEAN, value=True),
                    "score": FieldValue(type=FieldType.NULL),
                    "time-start": FieldValue(type=FieldType.TIMESTAMP, offset=60),
                    "time-end": FieldValue(type=FieldType.TIMESTAMP, offset=0),
                    "packet-count": FieldValue(
                        type=FieldType.NUMBER, mode="random", min=100, max=100000
                    ),
                    "fixed-label": FieldValue(
                        type=FieldType.STRING, value="production"
                    ),
                },
            ),
        )
    },
)

DEVICE_INFO_ENDPOINT = EndpointConfig(
    path="/v1/device-info",
    data_key="device_info",
    polling_interval_seconds=300,
    data_structure={
        "hostname": FieldValue(type=FieldType.RANDOM_FQDN, suffix=".radware.com"),
        "mgmt-ip": FieldValue(type=FieldType.RANDOM_IPV4),
        "stats": FieldValue(
            type=FieldType.OBJECT,
            properties={
                "connections": FieldValue(type=FieldType.RANDOM, min=0, max=10000),
                "bandwidth-kbps": FieldValue(
                    type=FieldType.NUMBER, mode="random", min=1000, max=1000000
                ),
            },
        ),
        "last-polled": FieldValue(type=FieldType.TIMESTAMP, offset=0),
        "firmware": FieldValue(type=FieldType.STRING, value="10.6.0"),
    },
)

FLOW_DATA_ENDPOINT = EndpointConfig(
    path="/v1/flow-data",
    data_key="flows",
    polling_interval_seconds=30,
    data_structure={
        "flows": FieldValue(
            type=FieldType.ARRAY,
            repeat_min=1,
            repeat_max=5,
            item=FieldValue(
                type=FieldType.OBJECT,
                properties={
                    "flow-id": FieldValue(
                        type=FieldType.RANDOM_COMPOSITE,
                        parts=[
                            {"type": "literal", "value": "FL-"},
                            {"type": "random", "min": 1000, "max": 9999},
                        ],
                    ),
                    "policy-ref": FieldValue(
                        type=FieldType.TEMPLATE,
                        value="pol{{INDEX}}",
                    ),
                },
            ),
        )
    },
)

ALL_ENDPOINTS = [ATTACK_DATA_ENDPOINT, DEVICE_INFO_ENDPOINT, FLOW_DATA_ENDPOINT]

TCLSH_AVAILABLE = shutil.which("tclsh") is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_output(xmf: str) -> str:
    """Extract and unescape all SA_xml_append_plain_text string contents.

    The XMF TCL-escapes every JSON quote as \\\" inside SA_xml_append_plain_text
    string literals.  This helper collects all those literals and unescapes them
    so that assertions can check for plain JSON patterns like '"data_source"'
    rather than the raw escaped form.
    """
    # Match content between the outer quotes, handling \\\" escape sequences
    raw = re.findall(r'SA_xml_append_plain_text "((?:[^"\\]|\\.)*)"', xmf)
    return "".join(s.replace('\\"', '"') for s in raw)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def xmf_pretty():
    return XMFGenerator(ALL_ENDPOINTS, pretty_json=True).generate_xmf()


@pytest.fixture(scope="module")
def xmf_compact():
    return XMFGenerator(ALL_ENDPOINTS, pretty_json=False).generate_xmf()


@pytest.fixture(scope="module")
def single_endpoint_xmf():
    return XMFGenerator([ATTACK_DATA_ENDPOINT]).generate_xmf()


@pytest.fixture(scope="module")
def json_out(xmf_pretty):
    """Unescaped JSON text produced by all SA_xml_append_plain_text calls (pretty mode)."""
    return _json_output(xmf_pretty)


@pytest.fixture(scope="module")
def json_out_compact(xmf_compact):
    """Unescaped JSON text produced by all SA_xml_append_plain_text calls (compact mode)."""
    return _json_output(xmf_compact)


# ---------------------------------------------------------------------------
# Required sections and init
# ---------------------------------------------------------------------------

class TestXMFRequiredSections:
    """Required XMF directives and initialisation."""

    def test_xml_init_action_present(self, xmf_pretty):
        assert "%xml_init_action" in xmf_pretty

    def test_sa_getmyip_called(self, xmf_pretty):
        assert "SA_getmyip" in xmf_pretty

    def test_myip_variable_set(self, xmf_pretty):
        assert "set myIP [SA_getmyip]" in xmf_pretty

    def test_http_get_action_for_each_endpoint(self, xmf_pretty):
        for ep in ALL_ENDPOINTS:
            assert f"%http_get_action {ep.path}" in xmf_pretty, (
                f"Missing %http_get_action {ep.path}"
            )

    def test_content_type_set_for_each_endpoint(self, xmf_pretty):
        assert xmf_pretty.count('SA_xml_sethttpcontenttype "application/json"') == len(ALL_ENDPOINTS)

    def test_clear_plain_text_called_for_each_endpoint(self, xmf_pretty):
        assert xmf_pretty.count("SA_xml_clear_plain_text") == len(ALL_ENDPOINTS)


# ---------------------------------------------------------------------------
# Helper proc definitions
# ---------------------------------------------------------------------------

class TestXMFHelperProcs:
    """All 5 helper procs must be defined exactly once in the XMF output."""

    EXPECTED_PROCS = [
        "proc random_int",
        "proc random_ipv4",
        "proc random_fqdn",
        "proc random_policy_name",
        "proc get_timestamp_offset",
    ]

    def test_all_procs_defined(self, xmf_pretty):
        for proc in self.EXPECTED_PROCS:
            assert proc in xmf_pretty, f"Helper proc not found: '{proc}'"

    def test_random_int_has_min_max_params(self, xmf_pretty):
        assert "proc random_int {min max}" in xmf_pretty

    def test_random_ipv4_uses_random_int(self, xmf_pretty):
        proc_section = xmf_pretty[xmf_pretty.index("proc random_ipv4"):]
        next_proc = proc_section.find("proc ", 5)
        proc_body = proc_section[:next_proc] if next_proc > 0 else proc_section
        assert "random_int" in proc_body

    def test_get_timestamp_offset_uses_clock(self, xmf_pretty):
        assert "clock seconds" in xmf_pretty
        assert "clock format" in xmf_pretty

    def test_procs_defined_once_not_per_endpoint(self, xmf_pretty):
        assert xmf_pretty.count("proc random_int") == 1
        assert xmf_pretty.count("proc random_ipv4") == 1
        assert xmf_pretty.count("proc get_timestamp_offset") == 1


# ---------------------------------------------------------------------------
# data_source section  (checks unescaped JSON output)
# ---------------------------------------------------------------------------

class TestXMFDataSource:
    """data_source must appear in every endpoint block with correct fields."""

    def test_data_source_key_present(self, json_out):
        assert json_out.count('"data_source"') == len(ALL_ENDPOINTS)

    def test_data_source_type_is_defensepro(self, json_out):
        assert '"type"' in json_out
        assert '"defensepro"' in json_out

    def test_data_source_ip_is_myip_variable(self, json_out):
        assert '"ip"' in json_out
        # $myIP is a TCL variable – appears literally in the XMF source
        assert '"$myIP"' in json_out

    def test_data_source_version_present(self, json_out):
        assert '"version"' in json_out
        assert '"10.6.0.0"' in json_out


# ---------------------------------------------------------------------------
# transaction section  (checks unescaped JSON output)
# ---------------------------------------------------------------------------

class TestXMFTransaction:
    """transaction must appear in every endpoint block with correct fields."""

    def test_transaction_key_present(self, json_out):
        assert json_out.count('"transaction"') == len(ALL_ENDPOINTS)

    def test_request_url_uses_myip_and_path(self, json_out):
        assert '"request_url"' in json_out
        assert "https://$myIP:8790" in json_out
        for ep in ALL_ENDPOINTS:
            assert f"https://$myIP:8790{ep.path}" in json_out

    def test_response_type_is_complete(self, json_out):
        assert '"response_type"' in json_out
        assert '"complete"' in json_out

    def test_last_update_field_present(self, json_out):
        assert '"last_update"' in json_out

    def test_next_request_time_field_present(self, json_out):
        assert '"next_request_time"' in json_out

    def test_polling_interval_reflected_in_next_request_time(self, xmf_pretty):
        """Each endpoint's interval must appear as a negative offset (TCL code)."""
        assert "get_timestamp_offset -60" in xmf_pretty
        assert "get_timestamp_offset -300" in xmf_pretty
        assert "get_timestamp_offset -30" in xmf_pretty

    def test_last_update_uses_zero_offset(self, xmf_pretty):
        assert "get_timestamp_offset 0" in xmf_pretty


# ---------------------------------------------------------------------------
# Field type tests  (JSON content via json_out; TCL structure via xmf_pretty)
# ---------------------------------------------------------------------------

class TestXMFFieldTypes:
    """Each field type must generate recognisable output."""

    def test_boolean_true_generates_true_literal(self, json_out):
        assert '"active": true' in json_out

    def test_null_generates_null_literal(self, json_out):
        assert '"score": null' in json_out

    def test_number_fixed_value_inline(self, json_out):
        assert '"dst-port": 443' in json_out

    def test_number_random_uses_random_int_with_bounds(self, xmf_pretty):
        assert "random_int 1024 65535" in xmf_pretty
        assert "random_int 100 100000" in xmf_pretty

    def test_random_ipv4_calls_proc(self, xmf_pretty):
        assert "random_ipv4" in xmf_pretty
        assert re.search(r"set \w+ \[random_ipv4\]", xmf_pretty)

    def test_random_fqdn_uses_suffix(self, xmf_pretty):
        assert 'random_fqdn ".radware.com"' in xmf_pretty

    def test_timestamp_offset_zero_uses_last_update_variable(self, xmf_pretty):
        assert "$last_update" in xmf_pretty

    def test_timestamp_positive_offset_calls_get_timestamp_offset(self, xmf_pretty):
        assert "get_timestamp_offset 60" in xmf_pretty

    def test_string_fixed_value_inlined(self, json_out):
        assert '"production"' in json_out

    def test_string_options_generates_list_and_random_pick(self, xmf_pretty):
        assert "set options [list" in xmf_pretty
        assert "llength $options" in xmf_pretty

    def test_random_composite_with_literal_and_random(self, xmf_pretty):
        # literal "FL-" appears in TCL code (not inside an SA_xml string)
        assert '"FL-"' in xmf_pretty
        assert "random_int 1000 9999" in xmf_pretty

    def test_template_field_with_index_placeholder(self, xmf_pretty):
        # pol{{INDEX}} → pol$i or pol$j depending on loop depth
        assert "pol$" in xmf_pretty

    def test_random_bare_uses_random_int(self, xmf_pretty):
        assert "random_int 0 10000" in xmf_pretty

    def test_nested_object_opens_and_closes_brace(self, json_out):
        assert '"stats"' in json_out

    def test_firmware_fixed_string_value(self, json_out):
        assert '"10.6.0"' in json_out


# ---------------------------------------------------------------------------
# Protocol / tcp-flag dependency
# ---------------------------------------------------------------------------

class TestXMFProtocolTcpFlag:
    """tcp-flag must only be emitted when protocol is tcp."""

    def test_protocol_value_stored_in_variable(self, xmf_pretty):
        assert "proto_" in xmf_pretty

    def test_tcp_flag_inside_protocol_conditional(self, xmf_pretty):
        assert 'if {$proto_' in xmf_pretty
        assert '"tcp"' in xmf_pretty

    def test_tcp_flag_emitted_after_conditional(self, json_out):
        assert '"tcp-flag"' in json_out

    def test_tcp_flag_conditional_uses_equality_check(self, xmf_pretty):
        assert re.search(r'if \{\$proto_\w+ == "tcp"\}', xmf_pretty)


# ---------------------------------------------------------------------------
# Array generation
# ---------------------------------------------------------------------------

class TestXMFArrayGeneration:
    """Array fields must produce correct TCL for loop constructs."""

    def test_fixed_repeat_array_uses_literal_count(self, xmf_pretty):
        # Top-level arrays are generated at indent=1 → loop variable is 'j' (chr(ord('i')+1))
        assert "set arr_count_j 3" in xmf_pretty

    def test_random_repeat_array_uses_random_int(self, xmf_pretty):
        assert "random_int 1 5" in xmf_pretty

    def test_array_loop_uses_for_construct(self, xmf_pretty):
        assert re.search(r"for \{set \w+ 0\}", xmf_pretty)

    def test_array_item_suffix_logic_for_trailing_comma(self, xmf_pretty):
        assert "item_suffix" in xmf_pretty
        assert 'set item_suffix ","' in xmf_pretty

    def test_array_opens_bracket(self, xmf_pretty):
        assert r"\[" in xmf_pretty

    def test_array_closes_bracket(self, xmf_pretty):
        assert r"\]" in xmf_pretty


# ---------------------------------------------------------------------------
# JSON structural integrity
# ---------------------------------------------------------------------------

class TestXMFJsonStructure:
    """The generated append calls must describe well-formed JSON."""

    def test_request_url_contains_https_scheme(self, xmf_pretty):
        assert "https://" in xmf_pretty

    def test_data_source_precedes_transaction(self, json_out):
        """data_source must appear before transaction in every endpoint block."""
        ds_pos = json_out.find('"data_source"')
        tx_pos = json_out.find('"transaction"')
        assert ds_pos != -1, "data_source not found in json output"
        assert tx_pos != -1, "transaction not found in json output"
        assert ds_pos < tx_pos, "data_source must precede transaction"

    def test_no_unbalanced_braces_in_append_calls(self, xmf_pretty):
        """Count { and } across all SA_xml_append_plain_text literals.

        Uses a regex that handles \\\" escapes inside the literals to correctly
        extract the full content between the outer quotes.
        """
        literals = re.findall(r'SA_xml_append_plain_text "((?:[^"\\]|\\.)*)"', xmf_pretty)
        open_total = sum(lit.count("{") - lit.count("\\{") for lit in literals)
        close_total = sum(lit.count("}") - lit.count("\\}") for lit in literals)
        assert open_total == close_total, (
            f"Unbalanced JSON object braces: open={open_total}, close={close_total}"
        )


# ---------------------------------------------------------------------------
# Multiple vs single endpoint
# ---------------------------------------------------------------------------

class TestXMFMultipleEndpoints:
    """Three endpoints produce three distinct %http_get_action blocks."""

    def test_three_http_get_action_blocks(self, xmf_pretty):
        count = xmf_pretty.count("%http_get_action")
        assert count == 3, f"Expected 3 %http_get_action blocks, got {count}"

    def test_all_paths_present(self, xmf_pretty):
        for ep in ALL_ENDPOINTS:
            assert ep.path in xmf_pretty

    def test_attack_data_has_correct_data_key(self, json_out):
        assert '"attack_data"' in json_out or '"attacks"' in json_out

    def test_single_endpoint_generates_one_action_block(self, single_endpoint_xmf):
        assert single_endpoint_xmf.count("%http_get_action") == 1

    def test_single_endpoint_has_correct_path(self, single_endpoint_xmf):
        assert "/v1/attack-data" in single_endpoint_xmf


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestXMFEdgeCases:
    """Edge cases: zero-repeat arrays, compact mode."""

    def test_array_with_repeat_zero_is_omitted(self):
        endpoint = EndpointConfig(
            path="/v1/empty-test",
            data_key="data",
            polling_interval_seconds=60,
            data_structure={
                "active-attacks": FieldValue(
                    type=FieldType.ARRAY,
                    repeat=3,
                    item=FieldValue(type=FieldType.OBJECT, properties={
                        "id": FieldValue(type=FieldType.NUMBER, value=1),
                    }),
                ),
                "empty-list": FieldValue(
                    type=FieldType.ARRAY,
                    repeat=0,
                    item=FieldValue(type=FieldType.STRING, value="x"),
                ),
            },
        )
        xmf = XMFGenerator([endpoint]).generate_xmf()
        out = _json_output(xmf)
        assert '"active-attacks"' in out
        assert '"empty-list"' not in out

    def test_array_with_repeat_min_max_zero_is_omitted(self):
        endpoint = EndpointConfig(
            path="/v1/empty-test2",
            data_key="data",
            polling_interval_seconds=60,
            data_structure={
                "present-field": FieldValue(type=FieldType.STRING, value="yes"),
                "absent-array": FieldValue(
                    type=FieldType.ARRAY,
                    repeat_min=0,
                    repeat_max=0,
                    item=FieldValue(type=FieldType.STRING, value="x"),
                ),
            },
        )
        xmf = XMFGenerator([endpoint]).generate_xmf()
        out = _json_output(xmf)
        assert '"present-field"' in out
        assert '"absent-array"' not in out

    def test_pretty_mode_includes_newline_tokens(self, xmf_pretty):
        # pretty_json=True embeds literal \n (two chars) inside append strings
        assert "\\n" in xmf_pretty

    def test_compact_mode_has_no_newline_tokens(self, xmf_compact):
        # pretty_json=False must produce no \n tokens inside append literals
        literals = re.findall(r'SA_xml_append_plain_text "((?:[^"\\]|\\.)*)"', xmf_compact)
        for lit in literals:
            assert "\\n" not in lit, (
                f"Compact mode append literal contains \\n: {lit[:80]}"
            )

    def test_compact_mode_has_no_json_indentation(self, xmf_compact):
        # No leading spaces inside append string literals in compact mode
        literals = re.findall(r'SA_xml_append_plain_text "((?:[^"\\]|\\.)*)"', xmf_compact)
        for lit in literals:
            assert not lit.startswith("  "), (
                f"Compact mode append literal has leading spaces: '{lit[:40]}'"
            )


# ---------------------------------------------------------------------------
# TCL syntax check (requires tclsh in PATH)
# ---------------------------------------------------------------------------

class TestXMFTclSyntax:
    """Execute XMF content via tclsh with SA_xml_* procs stubbed out."""

    _TCL_STUBS = """\
proc SA_getmyip {} { return "192.168.1.1" }
proc SA_xml_sethttpcontenttype {args} {}
proc SA_xml_clear_plain_text {args} {}
proc SA_xml_append_plain_text {args} {}
proc SA_xml_debugflag {args} {}
proc SA_xml_debugfile {args} {}
"""

    @staticmethod
    def _build_tclsh_script(xmf_content: str) -> str:
        converted_lines = []
        for line in xmf_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("%xml_init_action") or stripped.startswith("%http_get_action"):
                converted_lines.append(f"# {stripped}")
            else:
                converted_lines.append(line)
        return TestXMFTclSyntax._TCL_STUBS + "\n".join(converted_lines)

    @pytest.mark.skipif(not TCLSH_AVAILABLE, reason="tclsh not available")
    def test_generated_xmf_is_valid_tcl(self, xmf_pretty):
        tcl_script = self._build_tclsh_script(xmf_pretty)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tcl", delete=False, encoding="utf-8"
        ) as f:
            f.write(tcl_script)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["tclsh", tmp_path], capture_output=True, text=True, timeout=15
            )
            assert result.returncode == 0, (
                f"tclsh exited {result.returncode}\n"
                f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.skipif(not TCLSH_AVAILABLE, reason="tclsh not available")
    def test_compact_xmf_is_valid_tcl(self, xmf_compact):
        tcl_script = self._build_tclsh_script(xmf_compact)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tcl", delete=False, encoding="utf-8"
        ) as f:
            f.write(tcl_script)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["tclsh", tmp_path], capture_output=True, text=True, timeout=15
            )
            assert result.returncode == 0, (
                f"tclsh (compact) exited {result.returncode}\nstderr: {result.stderr[:500]}"
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @pytest.mark.skipif(not TCLSH_AVAILABLE, reason="tclsh not available")
    def test_each_endpoint_individually_is_valid_tcl(self):
        for ep in ALL_ENDPOINTS:
            xmf = XMFGenerator([ep]).generate_xmf()
            tcl_script = self._build_tclsh_script(xmf)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tcl", delete=False, encoding="utf-8"
            ) as f:
                f.write(tcl_script)
                tmp_path = f.name
            try:
                result = subprocess.run(
                    ["tclsh", tmp_path], capture_output=True, text=True, timeout=15
                )
                assert result.returncode == 0, (
                    f"Endpoint '{ep.path}': tclsh exited {result.returncode}\n"
                    f"stderr: {result.stderr[:400]}"
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
