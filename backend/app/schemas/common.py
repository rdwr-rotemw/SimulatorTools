from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    message: str = Field(..., description="Human-readable success message")
    data: Optional[Any] = Field(None, description="Optional payload data")

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Short error code or title")
    detail: Optional[str] = Field(None, description="Detailed error message")

    model_config = {"from_attributes": True}

