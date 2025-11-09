from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CCCredentialsCreate(BaseModel):
    cc_ip: str = Field(..., description="CyberController IP address")
    cc_host: Optional[str] = Field(None, description="CyberController hostname")
    cc_port: Optional[int] = Field(443, description="CyberController port")
    username: str = Field(..., description="Username for CC")
    encrypted_password: str = Field(..., description="Encrypted or protected password")

    model_config = {"from_attributes": True}


class CCCredentialsResponse(BaseModel):
    cc_ip: str = Field(..., description="CyberController IP address")
    cc_host: Optional[str] = Field(None, description="CyberController hostname")
    cc_port: int = Field(..., description="CyberController port")
    username: str = Field(..., description="Username for CC")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}

