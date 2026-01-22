from __future__ import annotations

from datetime import datetime
from typing import Optional, List
import ipaddress
from pydantic import BaseModel, Field, field_validator


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
    status: Optional[str] = Field(None, description="Updated simulator status")
    template_id: Optional[str] = Field(None, description="MongoDB _id of the device template to use for update")

    model_config = {"from_attributes": True}


class SaproSimulatorRangeCreate(BaseModel):
    """Schema for creating multiple simulators from an IP range."""
    start_ip: str = Field(..., description="Starting IP address (inclusive)")
    end_ip: str = Field(..., description="Ending IP address (inclusive)")
    template_id: str = Field(..., description="MongoDB _id of the device template to use")
    map: str = Field(..., description="Map/profile name to assign")

    @field_validator('start_ip', 'end_ip')
    @classmethod
    def validate_ip_format(cls, v: str) -> str:
        try:
            ipaddress.IPv4Address(v)
            return v
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid IPv4 address: {v}")

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


class SaproSimulatorAddResult(BaseModel):
    """Represents the result of adding a single simulator."""
    ip_address: str = Field(..., description="Simulator IP address")
    success: bool = Field(..., description="Whether simulator was added successfully")
    error_message: Optional[str] = Field(None, description="Error message if addition failed")


class SaproSimulatorBatchResponse(BaseModel):
    """Represents the batch addition response for simulators."""
    total: int = Field(..., description="Total number of simulators in batch")
    successful: int = Field(..., description="Number of successfully added simulators")
    failed: int = Field(..., description="Number of failed simulator additions")
    results: List[SaproSimulatorAddResult] = Field(..., description="Individual results for each simulator")


