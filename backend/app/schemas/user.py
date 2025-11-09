from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


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

