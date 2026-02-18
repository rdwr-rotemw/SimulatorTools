"""Integration tests for IRP message generation and binary validation.

For each target message ID (1, 4, 7, 19, 20, 52):
  1. Load schema from the local IdsDataFormat100600.xml (no MongoDB needed)
  2. Generate a default template via create_irp_template()
  3. Send message over UDP loopback, capture PCAP, parse with Java parser
  4. Assert no parser errors

Requirements:
  - Java JRE (default-jre-headless, present in backend Docker image)
  - tshark (present in backend Docker image)

Message IDs chosen as commonly broken or heavily exercised:
  1  - Basic/fundamental message
  4  - Frequently used in production flows
  7  - Edge case known to break with schema changes
  19 - Complex field layout
  20 - Large payload
  52 - Involves protocol-specific optional fields
"""

from pathlib import Path

import pytest

from backend.app.modules.reporter.irp.core.message_testing_coordinator import (
    MessageTestingCoordinator,
)
from backend.app.modules.reporter.irp.irp_module import create_irp_template, schema_obj_from_xml_file
from backend.app.modules.reporter.irp.tools.convert_xml import ConvertXml

# Most recent schema version - used for all tests
XML_FILE = (
    Path(__file__).parent.parent.parent
    / "app/modules/reporter/irp/data_formats/IdsDataFormat100600.xml"
)

TARGET_MESSAGE_IDS = [1, 4, 7, 19, 20, 52]


# ---------------------------------------------------------------------------
# Module-scoped fixtures (schema loaded once, messages sent once per ID)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def schema_obj():
    """Load ConvertXml schema from local XML file (module scope = loaded once).
    Used for template generation (create_irp_template).
    """
    assert XML_FILE.exists(), f"IdsDataFormat XML not found: {XML_FILE}"
    converter = ConvertXml(str(XML_FILE))
    converter.convert_xml()
    assert converter.schema is not None, "Schema failed to load from XML"
    return converter


@pytest.fixture(scope="module")
def send_schema_obj():
    """Schema object for sending IRP messages.

    Uses schema_obj_from_xml_file() to produce the same dict-based format
    as load_schema_from_mongo() (bitmap stored as dict, not Enum instance),
    which is required by IrpFormatter / TypeHandler.
    """
    assert XML_FILE.exists(), f"IdsDataFormat XML not found: {XML_FILE}"
    return schema_obj_from_xml_file(str(XML_FILE))


@pytest.fixture(scope="module")
def coordinator(tmp_path_factory):
    """MessageTestingCoordinator with temp capture/results dirs (module scope)."""
    captures = tmp_path_factory.mktemp("irp_captures")
    results = tmp_path_factory.mktemp("irp_results")
    return MessageTestingCoordinator(captures_dir=captures, results_dir=results)


@pytest.fixture(scope="module")
def irp_results(schema_obj, send_schema_obj, coordinator):
    """Run the full send→capture→parse pipeline for all target messages once.

    Results cached at module scope to avoid redundant UDP sends.
    Dict shape: {message_id: {"template": <create_irp_template result>,
                               "test": <coordinator.test_message result or None>}}
    """
    results = {}
    for message_id in TARGET_MESSAGE_IDS:
        template_result = create_irp_template(schema_obj, message_id)
        test_result = None
        if template_result.get("success"):
            test_result = coordinator.test_message(
                message_id=message_id,
                message_data=template_result["template"],
                schema_obj=send_schema_obj,
                xml_file_for_parser=str(XML_FILE),
                from_ip="127.0.0.1",
                to_ip="127.0.0.1",
                timeout=5,
            )
        results[message_id] = {
            "template": template_result,
            "test": test_result,
        }
    return results


# ---------------------------------------------------------------------------
# Template generation tests
# ---------------------------------------------------------------------------

class TestIRPTemplateGeneration:
    """Schema-based template generation must succeed for all target messages."""

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_generation_succeeds(self, irp_results, message_id):
        result = irp_results[message_id]["template"]
        assert result.get("success"), (
            f"Message {message_id}: create_irp_template failed\n  Result: {result}"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_contains_template_key(self, irp_results, message_id):
        result = irp_results[message_id]["template"]
        assert "template" in result, (
            f"Message {message_id}: 'template' key missing from result"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_is_dict(self, irp_results, message_id):
        template = irp_results[message_id]["template"].get("template")
        assert isinstance(template, dict), (
            f"Message {message_id}: template is {type(template).__name__}, expected dict"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_is_non_empty(self, irp_results, message_id):
        template = irp_results[message_id]["template"].get("template")
        assert template, (
            f"Message {message_id}: template dict is empty"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_has_message_name(self, irp_results, message_id):
        result = irp_results[message_id]["template"]
        assert result.get("name"), (
            f"Message {message_id}: missing 'name' in template result"
        )


# ---------------------------------------------------------------------------
# Round-trip tests (send → capture → parse)
# ---------------------------------------------------------------------------

class TestIRPRoundTrip:
    """Full binary round-trip: generate → send UDP → capture PCAP → parse with Java."""

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_template_generation_prerequisite(self, irp_results, message_id):
        """Pre-check: template must succeed before round-trip is meaningful."""
        assert irp_results[message_id]["template"].get("success"), (
            f"Message {message_id}: template generation failed - cannot validate round-trip"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_round_trip_status_is_completed(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None, (
            f"Message {message_id}: test was not run (template generation failed)"
        )
        assert test_result["status"] == "completed", (
            f"Message {message_id}: round-trip status is '{test_result['status']}'\n"
            f"  Errors: {test_result.get('errors', [])}\n"
            f"  Error:  {test_result.get('error', 'none')}\n"
            f"  Steps:  {test_result.get('steps', [])}"
        )


# ---------------------------------------------------------------------------
# Step-level checks
# ---------------------------------------------------------------------------

class TestIRPSteps:
    """Each pipeline step must be present and completed."""

    EXPECTED_STEPS = ["capture_packet", "extract_bytes", "parse_message"]

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_all_three_steps_present(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        step_names = [s["step"] for s in test_result.get("steps", [])]
        for expected in self.EXPECTED_STEPS:
            assert expected in step_names, (
                f"Message {message_id}: step '{expected}' not found in {step_names}\n"
                f"  Coordinator error: {test_result.get('error', 'none')}"
            )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_capture_packet_step_completed(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "capture_packet" in steps, (
            f"Message {message_id}: capture_packet step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        assert steps["capture_packet"]["status"] == "completed", (
            f"Message {message_id}: capture_packet step: {steps['capture_packet']}"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_capture_packet_step_has_pcap_file(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "capture_packet" in steps, (
            f"Message {message_id}: capture_packet step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        pcap_file = Path(steps["capture_packet"]["pcap_file"])
        assert pcap_file.exists(), (
            f"Message {message_id}: PCAP file not created at {pcap_file}"
        )
        assert pcap_file.stat().st_size > 0, (
            f"Message {message_id}: PCAP file is empty"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_extract_bytes_step_completed(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "extract_bytes" in steps, (
            f"Message {message_id}: extract_bytes step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        assert steps["extract_bytes"]["status"] == "completed", (
            f"Message {message_id}: extract_bytes step: {steps['extract_bytes']}"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_extract_bytes_step_has_extracted_file(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "extract_bytes" in steps, (
            f"Message {message_id}: extract_bytes step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        extracted_file = Path(steps["extract_bytes"]["extracted_file"])
        assert extracted_file.exists(), (
            f"Message {message_id}: extracted bytes file not found at {extracted_file}"
        )
        assert extracted_file.stat().st_size > 0, (
            f"Message {message_id}: extracted bytes file is empty"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_parse_message_step_completed(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "parse_message" in steps, (
            f"Message {message_id}: parse_message step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        assert steps["parse_message"]["status"] == "completed", (
            f"Message {message_id}: parse_message step: {steps['parse_message']}"
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_parse_result_file_exists_and_non_empty(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        steps = {s["step"]: s for s in test_result.get("steps", [])}
        assert "parse_message" in steps, (
            f"Message {message_id}: parse_message step missing, coordinator error: {test_result.get('error', 'none')}"
        )
        result_file = Path(steps["parse_message"]["parse_result_file"])
        assert result_file.exists(), (
            f"Message {message_id}: parse result file not created at {result_file}"
        )
        assert result_file.stat().st_size > 0, (
            f"Message {message_id}: parse result file is empty"
        )


# ---------------------------------------------------------------------------
# Parser error / warning checks
# ---------------------------------------------------------------------------

class TestIRPParserOutput:
    """Java parser output must be error-free for all target messages."""

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_no_parser_errors(self, irp_results, message_id):
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        errors = test_result.get("errors", [])
        assert len(errors) == 0, (
            f"Message {message_id}: parser reported {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("message_id", TARGET_MESSAGE_IDS)
    def test_result_has_timestamp(self, irp_results, message_id):
        """Each result must carry an ISO timestamp (proves coordinator ran fully)."""
        test_result = irp_results[message_id]["test"]
        assert test_result is not None
        assert "timestamp" in test_result, (
            f"Message {message_id}: 'timestamp' missing from test result"
        )
        assert test_result["timestamp"], (
            f"Message {message_id}: 'timestamp' is empty"
        )
