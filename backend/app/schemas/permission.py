from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PermissionCreate(BaseModel):
    permission_name: str = Field(..., description="Permission unique name")
    resource: Optional[str] = Field(None, description="Resource this permission applies to")
    action: Optional[str] = Field(None, description="Action allowed by this permission")
    description: Optional[str] = Field(None, description="Permission description")

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    permission_id: int = Field(..., description="Permission identifier")
    permission_name: str = Field(..., description="Permission unique name")
    resource: Optional[str] = Field(None, description="Resource this permission applies to")
    action: Optional[str] = Field(None, description="Action allowed by this permission")
    description: Optional[str] = Field(None, description="Permission description")

    model_config = {"from_attributes": True}

