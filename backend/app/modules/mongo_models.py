"""
Pydantic models for MongoDB document validation / application-level schemas.

Defines schemas for:
- snmp_templates
- irp_message_templates
- polling_templates

These are convenience validation models used when reading/writing MongoDB
and for request/response validation inside the app services.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class SNMPTrapTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    traps: List[Dict[str, Any]]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_public: bool = False

    model_config = {
        # `from_attributes` replaces old `orm_mode` in pydantic v2
        "from_attributes": True,
        # preserve extra behavior
        "extra": "ignore",
    }


class PollingTemplate(BaseModel):
    template_name: str = Field(..., max_length=200)
    description: Optional[str]
    json_config: Dict[str, Any]
    user_id: Optional[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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

    # Pydantic v2 disallows names with leading underscores; expose `id` and alias to `_id` for Mongo
    id: Optional[ObjectId] = Field(None, alias="_id")
    name: str = Field(..., max_length=200, description="Unique template name e.g., 'DPX_10_6'")
    description: Optional[str] = None
    template: Dict[str, Any] = Field(..., description="Flexible nested JSON structure for the device template")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "from_attributes": True,
        # `validate_by_name` replaces `allow_population_by_field_name`
        "validate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: lambda oid: str(oid)},
        "extra": "ignore",
    }


class DeviceTemplateCreate(BaseModel):
    """Model for creating a DeviceTemplate (no _id)."""

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    template: Dict[str, Any] = Field(...)

    model_config = {"extra": "ignore"}


class DeviceTemplateUpdate(BaseModel):
    """Model for partial updates to a DeviceTemplate (all fields optional)."""

    name: Optional[str]
    description: Optional[str]
    template: Optional[Dict[str, Any]]

    model_config = {"extra": "ignore"}


class DeviceDriver(BaseModel):
    """Device Driver metadata stored in MongoDB"""
    filename: str  # DefensePro-10.6.0.0-DD-1.00-17.jar
    device_type: str  # DefensePro, Alteon
    device_version: str  # 10.6.0.0
    dd_version: str  # 1.00-17
    file_path: str  # /app/resources/device_drivers/DefensePro-10.6.0.0-DD-1.00-17.jar
    file_size: int  # bytes
    upload_date: datetime
    uploaded_by: Optional[str] = None
    status: str = "available"  # available, deployed, failed
    last_deployed: Optional[datetime] = None


class DeviceDriverUpload(BaseModel):
    """Request for uploading device driver (file handled separately in multipart)"""
    pass


class DeviceDriverDeploy(BaseModel):
    """Request for deploying device drivers to CC"""
    driver_filenames: list[str]  # List of JAR filenames to deploy


__all__ = [
    "SNMPTrapTemplate",
    "IRPMessageTemplate",
    "PollingTemplate",
    "DeviceTemplate",
    "DeviceTemplateCreate",
    "DeviceTemplateUpdate",
    "DeviceDriver",
    "DeviceDriverUpload",
    "DeviceDriverDeploy",
]
