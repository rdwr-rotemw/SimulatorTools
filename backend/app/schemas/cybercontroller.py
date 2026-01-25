"""
CyberController schemas for API requests and responses.

These schemas define the API contract for CyberController endpoints
including login, device management, IRP schemas, and IdsDataFormat operations.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CCLoginPayload(BaseModel):
    """Login payload for CyberController authentication."""
    username: str = Field(..., description="CyberController username")
    password: str = Field(..., description="CyberController password")


class CCLoginResponse(BaseModel):
    """Response for CC login."""
    success: bool = Field(..., description="Whether login was successful")
    message: str = Field(..., description="Login status message")


class CCAddDevicePayload(BaseModel):
    """Payload for adding a device to CyberController."""
    name: str = Field(..., description="Device name")
    type: str = Field(..., description="Device type (DefensePro or Alteon)")
    cli_username: str = Field(..., description="CLI username for device")
    cli_password: str = Field(..., description="CLI password for device")
    http_username: str = Field(..., description="HTTP username for device")
    https_password: str = Field(..., description="HTTPS password for device")
    management_ip: str = Field(..., description="Device management IP address")
    vision_mgt_port: str = Field(..., description="Vision management port (e.g., G1)")
    register_device_events: bool = Field(False, description="Whether to register device events")


class CCDeviceResponse(BaseModel):
    """Single device response."""
    management_ip: str = Field(..., description="Device management IP address")
    name: Optional[str] = Field(None, description="Device name")
    device_id: Optional[str] = Field(None, description="Device ID in CyberController")
    device_type: Optional[str] = Field(None, description="Device type")
    status: Optional[str] = Field(None, description="Device status")
    version: Optional[str] = Field(None, description="Device software version")
    map: Optional[str] = Field(None, description="Sapro device map name")


class CCDevicesListResponse(BaseModel):
    """List of devices response."""
    devices: List[CCDeviceResponse] = Field(..., description="List of devices")


class CCDeleteResponse(BaseModel):
    """Response for device deletion."""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Deletion status message")


class CCLogoutResponse(BaseModel):
    """Response for CC logout."""
    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field(..., description="Logout status message")


class CCIdsDataFormatResponse(BaseModel):
    """Response for IdsDataFormat XML files."""
    files: List[str] = Field(..., description="List of IdsDataFormat XML filenames")


class IdsDataFormatPayload(BaseModel):
    """Payload for listing IdsDataFormat files via SSH credentials."""
    username: str = Field(..., description="SSH username")
    password: str = Field(..., description="SSH password")


class ManagementPort(BaseModel):
    """Single management port."""
    interface: str = Field(..., description="Interface name (e.g., G1)")
    address: str = Field(..., description="IP address of the interface")


class ManagementPortsResponse(BaseModel):
    """Response for management ports list."""
    ports: List[ManagementPort] = Field(..., description="List of management ports")


class IRPSchemaListItem(BaseModel):
    """Single IRP schema item."""
    mongo_id: str = Field(..., description="MongoDB ObjectId as string")
    template_name: str = Field(..., description="Schema template name")
    version: str = Field(..., description="Schema version")
    created_at: str = Field(..., description="Creation timestamp")


class IRPSchemaListResponse(BaseModel):
    """Response for IRP schemas list."""
    schemas: List[IRPSchemaListItem] = Field(..., description="List of IRP schemas")


class CCDeviceAddResult(BaseModel):
    """Represents the result of adding a single device."""
    management_ip: str = Field(..., description="Device management IP")
    name: str = Field(..., description="Device name")
    success: bool = Field(..., description="Whether device was added successfully")
    error_message: Optional[str] = Field(None, description="Error message if addition failed")


class CCBatchDeviceResponse(BaseModel):
    """Represents the batch addition response for devices."""
    total: int = Field(..., description="Total number of devices in batch")
    successful: int = Field(..., description="Number of successfully added devices")
    failed: int = Field(..., description="Number of failed device additions")
    results: List[CCDeviceAddResult] = Field(..., description="Individual results for each device")


class IdsDownloadPayload(BaseModel):
    """Payload for downloading an IdsDataFormat based on simulator version.

    sim_version: Simulator version string such as "10.3.0" or "8.2.1". This
    will be converted to the corresponding IdsDataFormat filename (for example
    "10.3.0" -> "IdsDataFormat100300.xml") and that file will be downloaded
    via SCP to /tmp/data_formats/ on the backend host.

    revert_to_original: If True and backup exists, restore original and download it.
    """
    sim_version: str = Field(..., description="Simulator version (e.g., 10.3.0)")
    username: str = Field(..., description="SSH username")
    password: str = Field(..., description="SSH password")
    revert_to_original: bool = Field(False, description="Revert to original backup if exists")


class IdsUploadPayload(BaseModel):
    """Payload for uploading custom IdsDataFormat XML."""
    simulator_ip: str = Field(..., description="Simulator IP address (used to extract version)")
    username: str = Field(..., description="SSH username")
    password: str = Field(..., description="SSH password")


__all__ = [
    "CCLoginPayload",
    "CCLoginResponse",
    "CCAddDevicePayload",
    "CCDeviceResponse",
    "CCDevicesListResponse",
    "CCDeleteResponse",
    "CCLogoutResponse",
    "CCIdsDataFormatResponse",
    "IdsDataFormatPayload",
    "ManagementPort",
    "ManagementPortsResponse",
    "IRPSchemaListItem",
    "IRPSchemaListResponse",
    "CCDeviceAddResult",
    "CCBatchDeviceResponse",
    "IdsDownloadPayload",
    "IdsUploadPayload",
]
