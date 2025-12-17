from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SaproSimulatorCreate(BaseModel):
    """Schema for creating a Sapro-managed simulator.

    New shape:
      - ip_address: str
      - map: str
      - template_id: str
    """
    ip_address: str = Field(..., description="Simulator IP address (primary key)")
    map: str = Field(..., description="Map/profile name to assign")
    template_id: str = Field(..., description="MongoDB _id of the device template to use")

    model_config = {"from_attributes": True}


class SaproSimulatorUpdate(BaseModel):
    """Schema for updating a Sapro-managed simulator."""
    type: Optional[str] = Field(None, description="Updated simulator device type")
    version: Optional[str] = Field(None, description="Updated simulator device version")
    map: Optional[str] = Field(None, description="Updated map/profile name")

    model_config = {"from_attributes": True}


class SaproSimulatorResponse(BaseModel):
    """Response schema returned for Sapro simulator operations."""
    ip_address: str = Field(..., description="Simulator IP address (primary key)")
    type: Optional[str] = Field(None, description="Simulator device type/name (None if SNMP query failed)")
    version: Optional[str] = Field(None, description="Simulator device version (None if SNMP query failed)")
    map: Optional[str] = Field(None, description="Assigned map/profile name")
    status: str = Field(..., description="Current status of the simulator (running/stopped/unknown)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}
