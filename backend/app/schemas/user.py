from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=150, description="Desired username")
    password: str = Field(..., min_length=8, description="Plaintext password (will be hashed)")

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    user_id: int = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = {"from_attributes": True}


class UserWithRolesResponse(BaseModel):
    """User response that includes role information."""
    user_id: int = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    roles: List[str] = Field(default_factory=list, description="List of role names assigned to user")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=150, description="New username (optional)")

    model_config = {"from_attributes": True}


class AssignRoleRequest(BaseModel):
    """Schema for assigning a role to a user."""
    role_name: str = Field(..., description="Name of the role to assign (e.g., 'admin', 'sapro_admin', 'cc_admin')")

    model_config = {"from_attributes": True}

