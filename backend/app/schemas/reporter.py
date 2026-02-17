"""
Reporter schemas for SNMP, IRP, and Polling configurations.

These schemas define the API contract for reporter endpoints.
Defaults for optional fields are handled in the reporter/attack_traps modules.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field


class TrapConfig(BaseModel):
    """Single SNMP trap configuration.

    Required fields are validated at the API boundary.
    Optional fields have no defaults here - defaults are handled
    by attack_traps.py for single source of truth.
    """
    # Required fields
    attackCategory: str
    attackName: str
    policy: str
    status: str

    # Optional fields (defaults handled by attack_traps.py)
    attackId: str | None = None
    radwareId: str | None = None
    protocol: str | None = None
    srcIp: str | None = None
    srcPort: str | None = None
    dstIp: str | None = None
    dstPort: str | None = None
    physicalPort: str | None = None
    packetCount: str | None = None
    packetBandwidth: str | None = None
    samples: str | None = None
    risk: str | None = None
    action: str | None = None
    direction: str | None = None
    pause: int | None = Field(None, ge=0, le=60, description="Pause in seconds after sending trap (max 60)")
    randomFields: List[str] | None = None


class ReporterSNMPPayload(BaseModel):
    """SNMP trap configuration payload matching attack_traps structure.

    map can be:
    - str: single map name used for all simulators (backward compatible)
    - Dict[str, str]: map of simulator_ip -> map_name for multi-simulator support
    """
    map: Union[str, Dict[str, str]]
    traps: List[TrapConfig]


class ReporterIRPPayload(BaseModel):
    """IRP message configuration payload."""
    message_type: str
    alarm_code: str
    severity: str = "MAJOR"
    parameters: Dict[str, Any] = {}


class ReporterPollingPayload(BaseModel):
    """Polling configuration payload.

    Either template_id OR endpoints must be provided.

    map can be:
    - str: single map name used for all simulators (backward compatible)
    - Dict[str, str]: map of simulator_ip -> map_name for multi-simulator support
    """
    # Template or endpoint configuration (mutually exclusive)
    template_id: Optional[str] = Field(None, description="MongoDB template ID to use")
    endpoints: Optional[List[Dict[str, Any]]] = Field(None, description="List of endpoint configurations")

    # XMF file configuration
    xmf_filename: str = Field(..., description="XMF filename (e.g., 'attack_data.xmf')")
    overwrite: bool = Field(False, description="Whether to overwrite existing file (default: False)")
    write_xmf: bool = Field(True, description="Whether to write XMF file (default: True). Set to False when XMF already written.")

    # Simulator configuration (required for set polling, optional for save-xmf)
    map: Optional[Union[str, Dict[str, str]]] = Field(None, description="Map name(s) for simulator(s)")


class ReporterResponse(BaseModel):
    """Reporter operation response."""
    success: bool
    message: str
    messages: Dict[str, Tuple[bool, str]] | None = None


class IRPPcapAnalysisMessage(BaseModel):
    message_id: str
    message_name: str
    count: int
    packet_numbers: List[int]
    schema_versions: List[int] = []


class IRPPcapAnalysisError(BaseModel):
    packet_number: int
    error: str


class IRPPcapAnalysisSchemaInfo(BaseModel):
    schema_available: bool
    schema_version: Optional[str] = None


class IRPPcapAnalysisResponse(BaseModel):
    total_packets: int
    irp_packets: int
    messages: List[IRPPcapAnalysisMessage]
    errors: List[IRPPcapAnalysisError] = []
    schema_info: IRPPcapAnalysisSchemaInfo


class IRPSendPayload(BaseModel):
    """Payload for sending IRP messages via custom data."""
    mongo_id: str = Field(..., description="MongoDB _id of the IRP schema to use")
    map: Optional[str] = Field(None, description="Simulator workspace map folder (not used by IRP, kept for API consistency)")
    message_data: Dict[str, Any] = Field(..., description="Message data to populate the template")


class IRPTemplatePayload(BaseModel):
    """Payload for generating IRP message templates."""
    mongo_id: str = Field(..., description="MongoDB _id of the IRP schema")
    message_id: Union[int, str] = Field(..., description="Message ID to generate template for")


__all__ = [
    "TrapConfig",
    "ReporterSNMPPayload",
    "ReporterIRPPayload",
    "ReporterPollingPayload",
    "ReporterResponse",
    "IRPPcapAnalysisMessage",
    "IRPPcapAnalysisError",
    "IRPPcapAnalysisSchemaInfo",
    "IRPPcapAnalysisResponse",
    "IRPSendPayload",
    "IRPTemplatePayload",
]
