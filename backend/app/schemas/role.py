from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    role_name: str = Field(..., description="Name of the role")
    description: Optional[str] = Field(None, description="Role description")

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    role_id: int = Field(..., description="Role identifier")
    role_name: str = Field(..., description="Name of the role")
    description: Optional[str] = Field(None, description="Role description")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}

