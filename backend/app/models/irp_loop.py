"""
IRP Loop model for storing user loop configurations in MongoDB.
"""
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class IRPLoopConfig(BaseModel):
    """Configuration for IRP loop stored in MongoDB."""
    user_id: str = Field(..., description="User ID (username)")
    cc_ip: str = Field(..., description="CyberController IP address")
    is_active: bool = Field(default=False, description="Whether loop is currently running")
    loop_delay: int = Field(..., description="Delay between sends in seconds")
    loop_timeout: int = Field(..., description="Total loop duration in seconds")
    start_time: Optional[datetime] = Field(None, description="When loop started")
    batches_sent: int = Field(default=0, description="Number of batches sent so far")
    simulator: str = Field(..., description="Target simulator IP")
    destination_port: str = Field(..., description="Destination port IP")
    schema_id: str = Field(..., description="MongoDB ObjectId of IRP schema")
    messages: List[Dict[str, Any]] = Field(..., description="IRP message configurations")
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


class IRPLoopStatus(BaseModel):
    """Status response for IRP loop."""
    is_active: bool
    loop_delay: Optional[int] = None
    loop_timeout: Optional[int] = None
    start_time: Optional[datetime] = None
    batches_sent: int = 0
    elapsed_seconds: int = 0
    remaining_seconds: int = 0
    simulator: Optional[str] = None
    destination_port: Optional[str] = None


class IRPLoopStartRequest(BaseModel):
    """Request to start IRP loop."""
    cc_ip: str
    loop_delay: int = Field(..., ge=1, description="Delay between sends (minimum 1 second)")
    loop_timeout: int = Field(..., ge=1, description="Total loop duration (minimum 1 second)")
    simulator: str = Field(..., description="Target simulator IP")
    destination_port: str
    schema_id: str = Field(..., description="MongoDB ObjectId of IRP schema")
    messages: List[Dict[str, Any]] = Field(..., min_items=1)
