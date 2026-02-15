"""Pydantic models for polling structure templates."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any
from datetime import datetime


class PollingStructure(BaseModel):
    """Structure template for a polling endpoint type.

    Defines ONLY the unique data_structure for this endpoint.
    data_source and transaction are NOT stored (always generated the same).
    NO user-specific data. NO hardcoded values (except validation constraints).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "structure_id": "attack_data",
                "name": "Attack Data",
                "description": "DNS-Protection and Behavioral-DoS attack data",
                "endpoint": "/v1/attack-data",
                "data_key": "attack_data",
                "polling_interval_seconds": 60,
                "data_structure": {
                    "attack_data": {
                        "_type": "object",
                        "_properties": {
                            "ErtFeed": {
                                "_type": "array",
                                "_item": {
                                    "_type": "object",
                                    "_properties": {
                                        "policy_name": {"_type": "string"},
                                        "attack_id": {"_type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    structure_id: str = Field(
        ...,
        description="Unique identifier (e.g., 'attack_data', 'application_traffic_v1')"
    )
    name: str = Field(..., description="Display name (e.g., 'Attack Data')")
    description: str = Field(..., description="Description of what this endpoint returns")
    endpoint: str = Field(..., description="API endpoint path (e.g., '/v1/attack-data')")
    data_key: str = Field(..., description="Main data key in JSON (e.g., 'attack_data')")
    polling_interval_seconds: int = Field(
        default=60,
        description="Default polling interval in seconds"
    )
    data_structure: Dict[str, Any] = Field(
        ...,
        description="Unique data structure with _type metadata (no hardcoded values)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
