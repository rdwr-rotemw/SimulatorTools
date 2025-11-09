from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SimulatorCreate(BaseModel):
    ip_address: str = Field(..., description="Simulator IP address")
    type: Optional[str] = Field(None, description="Simulator type")
    map: Optional[str] = Field(None, description="Simulator map or profile")
    cc_ip: Optional[str] = Field(None, description="Associated CyberController IP")
    status: Optional[str] = Field(None, description="Initial status")

    model_config = {"from_attributes": True}


class SimulatorUpdate(BaseModel):
    type: Optional[str] = Field(None, description="Simulator type")
    map: Optional[str] = Field(None, description="Simulator map or profile")
    status: Optional[str] = Field(None, description="Updated status")

    model_config = {"from_attributes": True}


class SimulatorResponse(BaseModel):
    ip_address: str = Field(..., description="Simulator IP address")
    type: Optional[str] = Field(None, description="Simulator type")
    map: Optional[str] = Field(None, description="Simulator map or profile")
    cc_ip: Optional[str] = Field(None, description="Associated CyberController IP")
    status: str = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}

