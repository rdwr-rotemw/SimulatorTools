from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Plaintext password")

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    user: Optional[UserResponse] = Field(None, description="Optional user object")

    model_config = {"from_attributes": True}
