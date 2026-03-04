"""
CC Favorites schemas for saving CyberController login credentials.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CCFavoriteCreate(BaseModel):
    """Payload for creating/updating a CC favorite."""
    cc_ip: str = Field(..., description="CyberController IP address")
    username: str = Field(..., description="CC login username")
    password: str = Field(..., description="CC login password")


class CCFavoriteResponse(BaseModel):
    """Response schema for a single CC favorite."""
    cc_ip: str = Field(..., description="CyberController IP address")
    username: str = Field(..., description="CC login username")
    password: str = Field(..., description="CC login password")
    created_at: str = Field(..., description="Creation timestamp")
