from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class AuditLogResponse(BaseModel):
    log_id: int = Field(..., description="Audit log identifier")
    user_id: int = Field(..., description="User who performed the action")
    action: str = Field(..., description="Action performed by user")
    resource: Optional[str] = Field(None, description="Resource affected by the action")
    timestamp: datetime = Field(..., description="When the action occurred")
    ip_address: Optional[str] = Field(None, description="IP address of requester")

    model_config = {"from_attributes": True}

