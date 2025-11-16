from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SaproSimulatorCreate(BaseModel):
    """Schema for creating a Sapro-managed simulator."""
    ip_address: str = Field(..., description="Simulator IP address (primary key)")
    type: str = Field(..., description="Simulator device type/name")
    template: str = Field(..., description="Simulator device template")
    map: Optional[str] = Field(None, description="Optional map/profile name to assign")

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
    type: str = Field(..., description="Simulator device type/name")
    version: str = Field(..., description="Simulator device version")
    map: Optional[str] = Field(None, description="Assigned map/profile name")
    status: str = Field(..., description="Current status of the simulator (running/stopped/unknown)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}

