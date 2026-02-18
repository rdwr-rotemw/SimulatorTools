"""Integration tests for SNMP attack trap TCL script generation.

Tests build_batch_tcl_content(), build_sa_sendtrap_line(), resolve_trap_fields(),
and set_trap_string_to_send() using 5 predefined mock trap configurations.

No Sapro/SSH connection required - validates generated script content only.

Coverage:
- Script-level structure (SA_settrapmgrs header, ordering, trailing newline)
- SA_sendtrap OID and varbind format
- All 18 named varbind fields with correct positions
- Enum value validity (protocol named not numeric, status, risk, action, direction)
- IPv4 address and port number validity
- samples field zeroed for non-sampled status; preserved for sampled
- Pause 'after' command placement and omission on last trap
- attack_id format (NNN-NNNNNNNNNN)
- attack_name and policy sanitization (no raw double-quotes)
- ValueError on missing required fields
- set_trap_string_to_send field count (19 comma-separated fields)
"""

import re

import pytest

from backend.app.modules.reporter.snmp.attack_traps import (
    ATTACK_ACTION,
    ATTACK_CATEGORY,
    ATTACK_DIRECTION,
    ATTACK_PROTOCOL,
    ATTACK_RISK,
    ATTACK_STATUS,
    build_batch_tcl_content,
    build_sa_sendtrap_line,
    generate_attack_id,
    resolve_trap_fields,
    set_trap_string_to_send,
)

MOCK_CC_IP = "10.0.0.1"

# Five predefined mock traps covering distinct scenarios
MOCK_TRAPS = [
    # Trap 1: TCP / INTRUSIONS / ONGOING - all fields explicit, fixed IDs
    {
        "attackName": "SQL_Injection_Attack",
        "policy": "pol_web_prod",
        "attackId": "123-4567890123",
        "radwareId": "42",
        "attackCategory": "INTRUSIONS",
        "protocol": "TCP",
        "srcIp": "192.168.1.100",
        "srcPort": "4532",
        "dstIp": "10.10.20.5",
        "dstPort": "443",
        "physicalPort": "2",
        "status": "ONGOING",
        "packetCount": "5000",
        "packetBandwidth": "150000",
        "samples": "0-0-0",
        "risk": "HIGH",
        "action": "DROP",
        "direction": "IN",
    },
    # Trap 2: UDP / DOS / START - minimal explicit fields, defaults exercised
    {
        "attackName": "UDP_Flood",
        "policy": "pol_dmz",
        "protocol": "UDP",
        "attackCategory": "DOS",
        "status": "START",
        "risk": "MEDIUM",
        "action": "CHALLENGE",
        "direction": "OUT",
    },
    # Trap 3: ICMP / ANTI_SCANNING / TERM - has pause=2 → 'after 2000' must follow
    {
        "attackName": "ICMP_Ping_Sweep",
        "policy": "pol_internal",
        "protocol": "ICMP",
        "attackCategory": "ANTI_SCANNING",
        "status": "TERM",
        "risk": "LOW",
        "action": "FORWARD",
        "direction": "IN",
        "pause": 2,
    },
    # Trap 4: SAMPLED status - samples "10-20-5" must NOT be zeroed out
    {
        "attackName": "DNS_Amplification",
        "policy": "pol_dns",
        "protocol": "UDP",
        "attackCategory": "DNS_PROTECTION",
        "status": "SAMPLED",
        "samples": "10-20-5",
        "risk": "HIGH",
        "action": "DROP",
        "direction": "IN",
    },
    # Trap 5: IP / BEHAVIORAL_DOS / OCCUR / UNKNOWN direction - last trap, no after
    {
        "attackName": "IP_Spoof_Campaign",
        "policy": "pol_core",
        "protocol": "IP",
        "attackCategory": "BEHAVIORAL_DOS",
        "status": "OCCUR",
        "risk": "HIGH",
        "action": "DROP",
        "direction": "UNKNOWN",
    },
]

VALID_PROTOCOL_VALUES = {p.value for p in ATTACK_PROTOCOL}
VALID_STATUS_VALUES = {s.value for s in ATTACK_STATUS}
VALID_RISK_VALUES = {r.value for r in ATTACK_RISK}
VALID_ACTION_VALUES = {a.value for a in ATTACK_ACTION}
VALID_DIRECTION_VALUES = {d.value for d in ATTACK_DIRECTION}
VALID_CATEGORY_VALUES = {c.value for c in ATTACK_CATEGORY}


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------

def _extract_sendtrap_lines(script: str) -> list:
    return [line for line in script.splitlines() if line.startswith("SA_sendtrap")]


def _extract_varbind_string(sendtrap_line: str) -> str:
    """Extract the OctetString content from a SA_sendtrap line.

    Handles escaped double-quotes (\\") inside the OctetString value.
    """
    match = re.search(
        r'rsIDSIntrusionErrorDesc\.0 OctetString "((?:[^"\\]|\\.)*)"',
        sendtrap_line,
    )
    assert match, f"No varbind OctetString found in:\n  {sendtrap_line[:150]}"
    return match.group(1)


def _parse_varbind_fields(varbind: str) -> dict:
    """Parse the V_8 varbind string into a named-field dict.

    Varbind format (backslash-escaped quotes around attack_name and policy):
        V_8 {attack_id} {radware_id} {category} \"{attack_name}\" {protocol}
        {src_ip} {src_port} {dst_ip} {dst_port} {physical_port} Regular
        \"{policy}\" {status} {packet_count} {packet_bandwidth} {samples}
        {risk} {action} 0 0 19 N/A {direction} 0
    """
    pattern = (
        r"^V_8\s+"
        r"(?P<attack_id>\S+)\s+"
        r"(?P<radware_id>\S+)\s+"
        r"(?P<category>\S+)\s+"
        r'\\"(?P<attack_name>[^\\"]+)\\"\s+'
        r"(?P<protocol>\S+)\s+"
        r"(?P<src_ip>\S+)\s+"
        r"(?P<src_port>\S+)\s+"
        r"(?P<dst_ip>\S+)\s+"
        r"(?P<dst_port>\S+)\s+"
        r"(?P<physical_port>\S+)\s+"
        r"Regular\s+"
        r'\\"(?P<policy>[^\\"]+)\\"\s+'
        r"(?P<status>\S+)\s+"
        r"(?P<packet_count>\S+)\s+"
        r"(?P<packet_bandwidth>\S+)\s+"
        r"(?P<samples>\S+)\s+"
        r"(?P<risk>\S+)\s+"
        r"(?P<action>\S+)\s+"
        r"0\s+0\s+19\s+N/A\s+"
        r"(?P<direction>\S+)\s+"
        r"0$"
    )
    m = re.match(pattern, varbind)
    assert m, f"Varbind does not match expected format:\n  {varbind}"
    return m.groupdict()


def _is_valid_ipv4(ip: str) -> bool:
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _is_valid_port(port: str) -> bool:
    try:
        return 1 <= int(port) <= 65535
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def script():
    return build_batch_tcl_content(MOCK_CC_IP, MOCK_TRAPS)


@pytest.fixture(scope="module")
def trap_lines(script):
    return _extract_sendtrap_lines(script)


@pytest.fixture(scope="module")
def all_fields(trap_lines):
    return [
        _parse_varbind_fields(_extract_varbind_string(line))
        for line in trap_lines
    ]


# ---------------------------------------------------------------------------
# Script-level structure
# ---------------------------------------------------------------------------

class TestScriptStructure:
    """Overall TCL script structure."""

    def test_starts_with_settrapmgrs(self, script):
        assert script.splitlines()[0] == f"SA_settrapmgrs {MOCK_CC_IP}"

    def test_blank_line_after_settrapmgrs(self, script):
        assert script.splitlines()[1] == ""

    def test_ends_with_newline(self, script):
        assert script.endswith("\n")

    def test_correct_sendtrap_count(self, trap_lines):
        assert len(trap_lines) == 5

    def test_after_command_follows_trap3(self, script):
        """Trap 3 (index 2) has pause=2 → 'after 2000' must be the next line."""
        lines = script.splitlines()
        trap_positions = [i for i, l in enumerate(lines) if l.startswith("SA_sendtrap")]
        third_trap_pos = trap_positions[2]
        assert lines[third_trap_pos + 1] == "after 2000"

    def test_no_after_command_after_last_trap(self, script):
        lines = script.splitlines()
        trap_positions = [i for i, l in enumerate(lines) if l.startswith("SA_sendtrap")]
        remaining = lines[trap_positions[-1] + 1:]
        after_lines = [l for l in remaining if l.startswith("after ")]
        assert len(after_lines) == 0

    def test_exactly_one_after_command_in_script(self, script):
        """Only trap 3 has a pause - so exactly one 'after' must exist."""
        after_lines = [l for l in script.splitlines() if l.startswith("after ")]
        assert len(after_lines) == 1
        assert after_lines[0] == "after 2000"


# ---------------------------------------------------------------------------
# SA_sendtrap format
# ---------------------------------------------------------------------------

class TestSendtrapFormat:
    """Each SA_sendtrap line format, OID, and varbind structure."""

    EXPECTED_PREFIX = "SA_sendtrap { 1.3.6.1.4.1.89.35.1.65.107 6 1 {"

    def test_all_lines_start_with_correct_oid(self, trap_lines):
        for i, line in enumerate(trap_lines):
            assert line.startswith(self.EXPECTED_PREFIX), (
                f"Trap {i + 1}: wrong OID prefix\n  Got: {line[:100]}"
            )

    def test_all_lines_contain_desc_octetstring(self, trap_lines):
        for i, line in enumerate(trap_lines):
            assert "rsIDSIntrusionErrorDesc.0 OctetString" in line, (
                f"Trap {i + 1}: missing OctetString varbind"
            )

    def test_all_lines_contain_severity_integer(self, trap_lines):
        for i, line in enumerate(trap_lines):
            assert 'rsIDSIntrusionErrorSeverity.0 Integer "2"' in line, (
                f"Trap {i + 1}: missing severity varbind"
            )

    def test_all_varbinds_start_with_v8(self, trap_lines):
        for i, line in enumerate(trap_lines):
            varbind = _extract_varbind_string(line)
            assert varbind.startswith("V_8 "), (
                f"Trap {i + 1}: varbind does not start with 'V_8'"
            )

    def test_all_varbinds_parse_to_18_fields(self, all_fields):
        for i, fields in enumerate(all_fields):
            assert len(fields) == 18, (
                f"Trap {i + 1}: expected 18 named fields, got {len(fields)}"
            )

    def test_trap1_all_fields_match_explicit_values(self, all_fields):
        """Trap 1 uses fully explicit inputs - every field must match exactly."""
        f = all_fields[0]
        assert f["attack_id"] == "123-4567890123"
        assert f["radware_id"] == "42"
        assert f["category"] == "Intrusions"       # enum value for INTRUSIONS
        assert f["attack_name"] == "SQL_Injection_Attack"
        assert f["protocol"] == "TCP"
        assert f["src_ip"] == "192.168.1.100"
        assert f["src_port"] == "4532"
        assert f["dst_ip"] == "10.10.20.5"
        assert f["dst_port"] == "443"
        assert f["physical_port"] == "2"
        assert f["policy"] == "pol_web_prod"
        assert f["status"] == "ongoing"            # enum value for ONGOING
        assert f["packet_count"] == "5000"
        assert f["packet_bandwidth"] == "150000"
        assert f["samples"] == "0-0-0"
        assert f["risk"] == "high"                 # enum value for HIGH
        assert f["action"] == "drop"               # enum value for DROP
        assert f["direction"] == "in"              # enum value for IN

    def test_trap4_sampled_status_values(self, all_fields):
        """Trap 4 is sampled - verify status and that samples are preserved."""
        f = all_fields[3]
        assert f["status"] == "sampled"
        assert f["samples"] == "10-20-5"

    def test_trap5_direction_unknown(self, all_fields):
        f = all_fields[4]
        assert f["direction"] == "unknown"


# ---------------------------------------------------------------------------
# Field validity across all traps
# ---------------------------------------------------------------------------

class TestFieldValidity:
    """Field values belong to valid enum sets and correct data formats."""

    def test_protocol_is_named_not_numeric(self, all_fields):
        for i, f in enumerate(all_fields):
            proto = f["protocol"]
            assert proto in VALID_PROTOCOL_VALUES, (
                f"Trap {i + 1}: protocol '{proto}' not in {VALID_PROTOCOL_VALUES}"
            )
            assert not proto.isdigit(), (
                f"Trap {i + 1}: protocol '{proto}' is numeric (must be named)"
            )

    def test_status_is_valid_enum_value(self, all_fields):
        for i, f in enumerate(all_fields):
            assert f["status"] in VALID_STATUS_VALUES, (
                f"Trap {i + 1}: status '{f['status']}' not in {VALID_STATUS_VALUES}"
            )

    def test_risk_is_valid_enum_value(self, all_fields):
        for i, f in enumerate(all_fields):
            assert f["risk"] in VALID_RISK_VALUES, (
                f"Trap {i + 1}: risk '{f['risk']}' not in {VALID_RISK_VALUES}"
            )

    def test_action_is_valid_enum_value(self, all_fields):
        for i, f in enumerate(all_fields):
            assert f["action"] in VALID_ACTION_VALUES, (
                f"Trap {i + 1}: action '{f['action']}' not in {VALID_ACTION_VALUES}"
            )

    def test_direction_is_valid_enum_value(self, all_fields):
        for i, f in enumerate(all_fields):
            assert f["direction"] in VALID_DIRECTION_VALUES, (
                f"Trap {i + 1}: direction '{f['direction']}' not in {VALID_DIRECTION_VALUES}"
            )

    def test_src_ip_is_valid_ipv4(self, all_fields):
        for i, f in enumerate(all_fields):
            assert _is_valid_ipv4(f["src_ip"]), (
                f"Trap {i + 1}: src_ip '{f['src_ip']}' is not valid IPv4"
            )

    def test_dst_ip_is_valid_ipv4(self, all_fields):
        for i, f in enumerate(all_fields):
            assert _is_valid_ipv4(f["dst_ip"]), (
                f"Trap {i + 1}: dst_ip '{f['dst_ip']}' is not valid IPv4"
            )

    def test_src_port_is_valid(self, all_fields):
        for i, f in enumerate(all_fields):
            assert _is_valid_port(f["src_port"]), (
                f"Trap {i + 1}: src_port '{f['src_port']}' not in range 1-65535"
            )

    def test_dst_port_is_valid(self, all_fields):
        for i, f in enumerate(all_fields):
            assert _is_valid_port(f["dst_port"]), (
                f"Trap {i + 1}: dst_port '{f['dst_port']}' not in range 1-65535"
            )

    def test_packet_count_is_positive_integer(self, all_fields):
        for i, f in enumerate(all_fields):
            val = f["packet_count"]
            assert val.isdigit() and int(val) > 0, (
                f"Trap {i + 1}: packet_count '{val}' is not a positive integer"
            )

    def test_packet_bandwidth_is_positive_integer(self, all_fields):
        for i, f in enumerate(all_fields):
            val = f["packet_bandwidth"]
            assert val.isdigit() and int(val) > 0, (
                f"Trap {i + 1}: packet_bandwidth '{val}' is not a positive integer"
            )

    def test_physical_port_is_integer(self, all_fields):
        for i, f in enumerate(all_fields):
            assert f["physical_port"].isdigit(), (
                f"Trap {i + 1}: physical_port '{f['physical_port']}' is not an integer"
            )

    def test_attack_id_contains_dash_separator(self, all_fields):
        for i, f in enumerate(all_fields):
            assert "-" in f["attack_id"], (
                f"Trap {i + 1}: attack_id '{f['attack_id']}' missing dash separator"
            )

    def test_trap1_attack_id_matches_fixed_format(self, all_fields):
        """Trap 1 has a fixed attack_id - validate 3-digit prefix / 10-digit suffix."""
        assert re.match(r"^\d{3}-\d{10}$", all_fields[0]["attack_id"]), (
            f"attack_id '{all_fields[0]['attack_id']}' does not match \\d{{3}}-\\d{{10}}"
        )

    def test_attack_name_has_no_raw_double_quotes(self, all_fields):
        """attack_name must be sanitized - double-quotes stripped."""
        for i, f in enumerate(all_fields):
            assert '"' not in f["attack_name"], (
                f"Trap {i + 1}: attack_name contains unescaped double-quote"
            )

    def test_policy_has_no_raw_double_quotes(self, all_fields):
        for i, f in enumerate(all_fields):
            assert '"' not in f["policy"], (
                f"Trap {i + 1}: policy contains unescaped double-quote"
            )


# ---------------------------------------------------------------------------
# Samples / status consistency
# ---------------------------------------------------------------------------

class TestSamplesConsistency:
    """samples field must be 0-0-0 unless status is 'sampled'."""

    def test_non_sampled_traps_have_zero_samples(self, all_fields):
        non_sampled_indices = [0, 1, 2, 4]  # traps 1, 2, 3, 5
        for i in non_sampled_indices:
            assert all_fields[i]["samples"] == "0-0-0", (
                f"Trap {i + 1}: status='{all_fields[i]['status']}' but samples='{all_fields[i]['samples']}'"
            )

    def test_sampled_trap_preserves_samples(self, all_fields):
        f = all_fields[3]  # trap 4
        assert f["status"] == "sampled"
        assert f["samples"] == "10-20-5", (
            f"Trap 4: expected samples='10-20-5' for sampled status, got '{f['samples']}'"
        )

    def test_all_samples_match_n_n_n_format(self, all_fields):
        for i, f in enumerate(all_fields):
            assert re.match(r"^\d+-\d+-\d+$", f["samples"]), (
                f"Trap {i + 1}: samples '{f['samples']}' does not match N-N-N format"
            )


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Unit tests for individual helper functions."""

    def test_generate_attack_id_format(self):
        """generate_attack_id must return exactly 3 digits, dash, 10 digits."""
        for _ in range(20):
            aid = generate_attack_id()
            assert re.match(r"^\d{3}-\d{10}$", aid), (
                f"generate_attack_id() returned '{aid}' - expected \\d{{3}}-\\d{{10}}"
            )

    def test_resolve_trap_fields_returns_all_19_keys(self):
        required = {
            "trap_manager", "attack_id", "radware_id", "category", "attack_name",
            "protocol", "src_ip", "src_port", "dst_ip", "dst_port", "physical_port",
            "policy", "status", "packet_count", "packet_bandwidth", "samples",
            "risk", "action", "direction",
        }
        result = resolve_trap_fields(MOCK_CC_IP, MOCK_TRAPS[0])
        assert set(result.keys()) == required

    def test_resolve_trap_fields_trap_manager_equals_cc_ip(self):
        result = resolve_trap_fields(MOCK_CC_IP, MOCK_TRAPS[0])
        assert result["trap_manager"] == MOCK_CC_IP

    def test_set_trap_string_to_send_has_19_fields(self):
        trap_str = set_trap_string_to_send(MOCK_CC_IP, MOCK_TRAPS[0])
        parts = trap_str.split(",")
        assert len(parts) == 19, (
            f"Expected 19 comma-separated fields, got {len(parts)}:\n  {trap_str}"
        )

    def test_set_trap_string_to_send_first_field_is_cc_ip(self):
        trap_str = set_trap_string_to_send(MOCK_CC_IP, MOCK_TRAPS[0])
        assert trap_str.startswith(MOCK_CC_IP + ",")

    def test_missing_attack_name_raises_value_error(self):
        with pytest.raises(ValueError, match="attackName"):
            resolve_trap_fields(MOCK_CC_IP, {"policy": "pol_test"})

    def test_missing_policy_raises_value_error(self):
        with pytest.raises(ValueError, match="policy"):
            resolve_trap_fields(MOCK_CC_IP, {"attackName": "Test_Attack"})

    def test_pause_zero_produces_no_after_command(self):
        traps = [
            {**MOCK_TRAPS[0], "pause": 0},
            MOCK_TRAPS[1],
        ]
        script = build_batch_tcl_content(MOCK_CC_IP, traps)
        assert "after " not in script

    def test_pause_on_last_trap_produces_no_after_command(self):
        """The 'after' guard (index < total - 1) must suppress pause on last trap."""
        traps = [
            MOCK_TRAPS[0],
            {**MOCK_TRAPS[1], "pause": 5},
        ]
        script = build_batch_tcl_content(MOCK_CC_IP, traps)
        assert "after " not in script

    def test_build_sa_sendtrap_line_directly(self):
        """build_sa_sendtrap_line with a fully specified fields dict."""
        fields = resolve_trap_fields(MOCK_CC_IP, MOCK_TRAPS[0])
        line = build_sa_sendtrap_line(fields)
        assert line.startswith("SA_sendtrap { 1.3.6.1.4.1.89.35.1.65.107 6 1 {")
        assert 'rsIDSIntrusionErrorSeverity.0 Integer "2"' in line
        varbind = _extract_varbind_string(line)
        parsed = _parse_varbind_fields(varbind)
        assert parsed["attack_id"] == "123-4567890123"

    def test_single_trap_script_has_no_after(self):
        script = build_batch_tcl_content(MOCK_CC_IP, [MOCK_TRAPS[0]])
        assert "after " not in script
        assert len(_extract_sendtrap_lines(script)) == 1
