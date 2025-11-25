"""
Pydantic models for MongoDB document validation / application-level schemas.

Defines schemas for:
- snmp_templates
- irp_message_templates
- polling_templates

These are convenience validation models used when reading/writing MongoDB
and for request/response validation inside the app services.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SNMPTrapTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    traps: List[Dict[str, Any]]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False


class IRPMessageTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    xml_schema: Dict[str, Any]  # Complete schema with messages, types, templates inside
    IdsDataFormat_version: Optional[str]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False


class PollingTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    json_config: Dict[str, Any]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False


__all__ = [
    "SNMPTrapTemplate",
    "IRPMessageTemplate",
    "PollingTemplate",
]

