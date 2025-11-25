"""
Reporter schemas for SNMP, IRP, and Polling configurations.

These schemas define the API contract for reporter endpoints.
Defaults for optional fields are handled in the reporter/attack_traps modules.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pydantic import BaseModel


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


class ReporterSNMPPayload(BaseModel):
    """SNMP trap configuration payload matching attack_traps structure."""
    traps: List[TrapConfig]


class ReporterIRPPayload(BaseModel):
    """IRP message configuration payload."""
    message_type: str
    alarm_code: str
    severity: str = "MAJOR"
    parameters: Dict[str, Any] = {}


class ReporterPollingPayload(BaseModel):
    """Polling configuration payload."""
    poll_interval: int = 60
    oids: list[str] = []
    enabled: bool = True


class ReporterResponse(BaseModel):
    """Reporter operation response."""
    success: bool
    message: str
    messages: Dict[str, Tuple[bool, str]] | None = None


__all__ = [
    "TrapConfig",
    "ReporterSNMPPayload",
    "ReporterIRPPayload",
    "ReporterPollingPayload",
    "ReporterResponse",
]
