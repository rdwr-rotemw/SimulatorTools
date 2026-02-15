"""
Pydantic models for polling endpoint configuration.

User configures:
- Endpoint path (e.g., /v1/attack-data)
- Main data key name (e.g., attack_data)
- Polling interval (polling_interval_seconds)
- Data structure (flexible, recursive field configuration)

NOT configured by user (auto-generated in TCL):
- data_source (uses $myIP from SA_getmyip and version)
- transaction (uses dynamic timestamps and endpoint path)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Field value types for polling endpoint data structure."""
    # Static types
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"

    # Dynamic types
    TIMESTAMP = "timestamp"
    RANDOM = "random"
    RANDOM_IPV4 = "random_ipv4"
    RANDOM_FQDN = "random_fqdn"
    RANDOM_COMPOSITE = "random_composite"
    TEMPLATE = "template"

    # Container types
    OBJECT = "object"
    ARRAY = "array"


class FieldValue(BaseModel):
    """Represents a field value configuration - recursive structure."""
    type: FieldType

    # For static values (string, number, boolean, null)
    value: Optional[Union[str, int, float, bool, None]] = None
    mode: Optional[str] = Field(
        default="fixed",
        description="Mode for string/number generation: 'fixed' or 'random'"
    )

    # For random numbers
    min: Optional[int] = None
    max: Optional[int] = None

    # For random_fqdn
    suffix: Optional[str] = None

    # For random_composite
    parts: Optional[List[Dict[str, Any]]] = None

    # For timestamp (seconds offset from NOW)
    offset: Optional[int] = None

    # For template (value field contains template string like "pol{{INDEX}}")
    # Uses value field

    # For object (dict of field_name → FieldValue)
    properties: Optional[Dict[str, 'FieldValue']] = None

    # For array
    repeat: Optional[int] = None
    repeat_min: Optional[int] = None
    repeat_max: Optional[int] = None
    item: Optional['FieldValue'] = None


# Enable forward reference for recursive structure
FieldValue.model_rebuild()


class EndpointConfig(BaseModel):
    """Endpoint configuration - user configures only this."""
    path: str = Field(..., description="Endpoint path (e.g., /v1/attack-data)")
    method: str = Field(default="GET", description="HTTP method")
    data_key: str = Field(..., description="Main data key name (e.g., attack_data)")
    polling_interval_seconds: int = Field(
        default=60,
        description="Polling interval in seconds (affects next_request_time in transaction)"
    )
    data_structure: Dict[str, FieldValue] = Field(
        ...,
        description="User-defined data structure (only this part, not data_source/transaction)"
    )


class PollingTemplateCreate(BaseModel):
    """Create polling template request."""
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    endpoints: List[EndpointConfig] = Field(..., description="List of endpoint configurations")


class PollingTemplateResponse(BaseModel):
    """Polling template response."""
    id: str = Field(..., description="MongoDB ObjectId as string")
    name: str
    description: str
    created_at: str = Field(..., description="ISO format datetime")
    endpoints: List[EndpointConfig]


class PollingTemplateUpdate(BaseModel):
    """Update polling template request."""
    name: Optional[str] = None
    description: Optional[str] = None
    endpoints: Optional[List[EndpointConfig]] = None


class PollingLoadRequest(BaseModel):
    """Load polling configuration to simulator request."""
    xmf_filename: str = Field(
        ...,
        description="XMF filename (without .xmf extension)"
    )
    endpoints: List[EndpointConfig] = Field(
        ...,
        description="List of endpoint configurations to include in this XMF"
    )


class PollingLoadResponse(BaseModel):
    """Load polling configuration response."""
    success: bool
    message: str
    simulator_ip: str
    map_name: str
