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

from bson import ObjectId
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
    xml_blob: Optional[str] = Field(
        None,
        description="Base64-encoded IdsDataFormat XML file content for testing"
    )
    xml_checksum: Optional[str] = Field(
        None,
        description="SHA256 checksum of the XML blob for cache validation"
    )
    IdsDataFormat_version: Optional[str]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False

    class Config:
        """Pydantic model configuration.

        - `orm_mode` enables compatibility with ORM objects if needed.
        - `extra = 'ignore'` ensures the model is tolerant of additional fields
          stored in Mongo documents that are not declared on the model.
        """
        orm_mode = True
        extra = "ignore"


class PollingTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    json_config: Dict[str, Any]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_public: bool = False


# DeviceTemplate models for Sapro simulator device templates stored in MongoDB.
class DeviceTemplate(BaseModel):
    """Device template stored in MongoDB for Sapro simulator creation.

    Fields:
    - _id: ObjectId (auto, primary key)
    - name: str (unique, e.g., "DPX_10_6", "ALTEON1")
    - description: str (optional, e.g., "DefensePro 10.6.0")
    - template: dict (flexible nested JSON structure describing the device template)
    - created_at: datetime
    - updated_at: datetime
    """

    _id: Optional[ObjectId] = Field(None, alias="_id")
    name: str = Field(..., max_length=200, description="Unique template name e.g., 'DPX_10_6'")
    description: Optional[str] = None
    template: Dict[str, Any] = Field(..., description="Flexible nested JSON structure for the device template")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        # Allow using the alias `_id` when creating/reading models
        allow_population_by_field_name = True
        # Permit BSON ObjectId as a field type and ensure it serializes to str in JSON
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: lambda oid: str(oid)}
        extra = "ignore"


class DeviceTemplateCreate(BaseModel):
    """Model for creating a DeviceTemplate (no _id)."""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    template: Dict[str, Any] = Field(...)

    class Config:
        extra = "ignore"


class DeviceTemplateUpdate(BaseModel):
    """Model for partial updates to a DeviceTemplate (all fields optional)."""

    name: Optional[str]
    description: Optional[str]
    template: Optional[Dict[str, Any]]

    class Config:
        extra = "ignore"


__all__ = [
    "SNMPTrapTemplate",
    "IRPMessageTemplate",
    "PollingTemplate",
    "DeviceTemplate",
    "DeviceTemplateCreate",
    "DeviceTemplateUpdate",
]
