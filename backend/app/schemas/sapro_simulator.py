from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict
import ipaddress
from pydantic import BaseModel, Field, field_validator


class SaproSimulatorCreate(BaseModel):
    """Schema for creating a Sapro-managed simulator.

    New shape:
      - ip_address: str
      - map: str
      - template_id: str
    """
    ip_address: str = Field(..., description="Simulator IP address (primary key)")
    map: str = Field(..., description="Map/profile name to assign")
    template_id: str = Field(..., description="MongoDB _id of the device template to use")

    model_config = {"from_attributes": True}


class SaproSimulatorUpdate(BaseModel):
    """Schema for updating a Sapro-managed simulator."""
    type: Optional[str] = Field(None, description="Updated simulator device type")
    version: Optional[str] = Field(None, description="Updated simulator device version")
    map: Optional[str] = Field(None, description="Updated map/profile name")
    status: Optional[str] = Field(None, description="Updated simulator status")
    template_id: Optional[str] = Field(None, description="MongoDB _id of the device template to use for update")

    model_config = {"from_attributes": True}


class SaproSimulatorRangeCreate(BaseModel):
    """Schema for creating multiple simulators from an IP range."""
    start_ip: str = Field(..., description="Starting IP address (inclusive)")
    end_ip: str = Field(..., description="Ending IP address (inclusive)")
    template_id: str = Field(..., description="MongoDB _id of the device template to use")
    map: str = Field(..., description="Map/profile name to assign")

    @field_validator('start_ip', 'end_ip')
    @classmethod
    def validate_ip_format(cls, v: str) -> str:
        try:
            ipaddress.IPv4Address(v)
            return v
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid IPv4 address: {v}")

    model_config = {"from_attributes": True}


class SaproSimulatorResponse(BaseModel):
    """Response schema returned for Sapro simulator operations."""
    ip_address: str = Field(..., description="Simulator IP address (primary key)")
    type: Optional[str] = Field(None, description="Simulator device type/name (None if SNMP query failed)")
    version: Optional[str] = Field(None, description="Simulator device version (None if SNMP query failed)")
    map: Optional[str] = Field(None, description="Assigned map/profile name")
    status: str = Field(..., description="Current status of the simulator (running/stopped/unknown)")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


class SaproSimulatorAddResult(BaseModel):
    """Represents the result of adding a single simulator."""
    ip_address: str = Field(..., description="Simulator IP address")
    success: bool = Field(..., description="Whether simulator was added successfully")
    error_message: Optional[str] = Field(None, description="Error message if addition failed")


class SaproSimulatorBatchResponse(BaseModel):
    """Represents the batch addition response for simulators."""
    total: int = Field(..., description="Total number of simulators in batch")
    successful: int = Field(..., description="Number of successfully added simulators")
    failed: int = Field(..., description="Number of failed simulator additions")
    results: List[SaproSimulatorAddResult] = Field(..., description="Individual results for each simulator")


class DeviceField(str, Enum):
    """Enum of editable device fields from the <Device> section of the map file."""
    # General section
    MULTI_HOME = "MultiHome"
    DHCP = "DHCP"
    SUBNET_MASK = "SubnetMask"
    MAC_ADDRESS = "MacAddress"
    INTERFACE = "Interface"
    USER_DATA = "UserData"
    TOPOLOGY_DATA = "TopologyData"
    DISPLAY_TAG = "DisplayTag"
    MODELING_FILE = "ModelingFile"
    COMMON_DATA_FILE = "CommonDataFile"
    # SNMP section
    READ_COMMUNITY = "ReadCommunity"
    WRITE_COMMUNITY = "WriteCommunity"
    MIB_FILE = "MibFile"
    AGENT_FILE = "AgentFile"
    TRAP_MGR = "TrapMgr"
    SNMP_STR = "SnmpStr"
    RESPONSE_DELAY = "ResponseDelay"
    MTU_SIZE = "MtuSize"
    SNMP_PORT = "SnmpPort"
    SECURITY_LEVEL = "SecurityLevel"
    USER_NAME = "UserName"
    # SSH section
    SSH_USER_NAME = "SSHUserName"
    SSH_PASSWORD = "SSHPassword"
    SSH_SCP_BASE_DIR = "SSHSCPBaseDir"
    SSH_VERSION = "SSHVersion"
    SSH_FILE = "SSHFile"
    # SOAP section
    SOAP_HTTP_PORT = "SoapHttpPort"
    SOAP_HTTPS_PORT = "SoapHttpsPort"
    XML_HTTPS_TYPE = "XmlHttpsType"
    SOAP_MOD_FILE = "SoapModFile"
    SOAP_CONTENT_TYPE = "SoapContentType"


class DeviceFieldsUpdateRequest(BaseModel):
    """Request schema for updating specific device fields in the map file."""
    fields: Dict[DeviceField, str] = Field(..., description="Map of field name to new value")


class DeviceFieldsUpdateResult(BaseModel):
    """Result for a single simulator in a device fields update operation."""
    ip_address: str = Field(..., description="Simulator IP address")
    success: bool = Field(..., description="Whether the update succeeded")
    message: str = Field(..., description="Result message")


