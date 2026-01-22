"""
SNMP template schemas for saving and managing trap templates.
"""
from __future__ import annotations

from typing import List, Dict, Any

from pydantic import BaseModel, Field


class SNMPTemplate(BaseModel):
    """SNMP template with trap configurations."""
    name: str = Field(..., description="Template name")
    traps: List[Dict[str, Any]] = Field(..., description="List of trap configurations")


class SNMPTemplateResponse(BaseModel):
    """Response schema for SNMP template."""
    name: str = Field(..., description="Template name")
    created_at: str = Field(..., description="Creation timestamp")
    trap_count: int = Field(..., description="Number of traps in template")


__all__ = [
    "SNMPTemplate",
    "SNMPTemplateResponse",
]
