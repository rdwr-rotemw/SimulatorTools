# Polling Module - Current State Documentation

**Date:** February 4, 2026  
**Purpose:** Comprehensive reference of all polling-related code before refactoring

---

## Table of Contents

1. [Backend Pydantic Models](#backend-pydantic-models)
2. [Backend Services](#backend-services)
3. [Backend Routes](#backend-routes)
4. [Frontend Types](#frontend-types)
5. [Frontend Services](#frontend-services)
6. [Frontend Components](#frontend-components)
7. [Architecture Overview](#architecture-overview)

---

## Backend Pydantic Models

### File: `backend/app/models/polling.py`

**Purpose:** Defines all Pydantic models for polling endpoint configuration, template management, and API requests/responses.

**Key Concepts:**
- `FieldType`: Enum of all supported field types (STRING, NUMBER, BOOLEAN, NULL, TIMESTAMP, RANDOM, RANDOM_IPV4, RANDOM_FQDN, RANDOM_COMPOSITE, TEMPLATE, OBJECT, ARRAY)
- `FieldValue`: Recursive field configuration model
- `EndpointConfig`: User-facing configuration for an endpoint
- Template management models for CRUD operations

**Full Code:**

```python
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
    endpoint: EndpointConfig = Field(..., description="Endpoint configuration")


class PollingTemplateResponse(BaseModel):
    """Polling template response."""
    id: str = Field(..., description="MongoDB ObjectId as string")
    name: str
    description: str
    created_at: str = Field(..., description="ISO format datetime")
    endpoint: EndpointConfig


class PollingTemplateUpdate(BaseModel):
    """Update polling template request."""
    name: Optional[str] = None
    description: Optional[str] = None
    endpoint: Optional[EndpointConfig] = None


class PollingLoadRequest(BaseModel):
    """Load polling configuration to simulator request."""
    template_id: Optional[str] = Field(
        None,
        description="Template ID to load from MongoDB (mutually exclusive with endpoint_config)"
    )
    endpoint_config: Optional[EndpointConfig] = Field(
        None,
        description="Endpoint config to generate on-the-fly (mutually exclusive with template_id)"
    )


class PollingLoadResponse(BaseModel):
    """Load polling configuration response."""
    success: bool
    message: str
    simulator_ip: str
    map_name: str
```

---

## Backend Services

### File: `backend/app/modules/reporter/polling/xmf_generator.py`

**Purpose:** Converts endpoint configurations into TCL (XMF) scripts that the Sapro simulator can execute.

**Key Features:**
- Generates complete XMF (TCL) files with hardcoded data_source and transaction sections
- Supports all field types (STRING, NUMBER, RANDOM, TIMESTAMP, TEMPLATE, RANDOM_COMPOSITE, etc.)
- Handles arrays with repeat counts and nested objects
- Uses TCL functions for dynamic value generation (timestamps, random numbers, FQDNs)
- User's data_source and transaction are NOT part of user configuration - they're generated in TCL

**Key Methods:**
- `generate_xmf()`: Main entry point - returns complete XMF content
- `_generate_user_data_structure()`: Builds TCL for user's data section
- `_generate_field_value()`: Recursive function to generate TCL for each field
- `_generate_array_field()`: Handles array field generation with loop variables

**Full Code (334 lines):**

```python
"""XMF (TCL) generator for polling endpoint configurations."""

from backend.app.models.polling import EndpointConfig, FieldValue, FieldType


class XMFGenerator:
    """Generates XMF (TCL) files from endpoint configuration.

    Key behavior:
    - data_source and transaction are generated IN TCL at runtime
    - They use $myIP from SA_getmyip (simulator's own IP)
    - Timestamps are calculated dynamically using user's intervals
    - User only configures the data_structure part
    """

    def __init__(self, endpoint_config: EndpointConfig):
        """Initialize XMF generator.

        Args:
            endpoint_config: User's endpoint configuration
        """
        self.config = endpoint_config
        self.indent_level = 0

    def generate_xmf(self) -> str:
        """Generate complete XMF content.

        Returns:
            Complete XMF TCL script
        """
        xmf_parts = []
        xmf_parts.append(self._generate_init_section())
        xmf_parts.append(self._generate_http_action())

        return "\n\n".join(xmf_parts)

    def _generate_init_section(self) -> str:
        """Generate %xml_init_action section."""
        return """%xml_init_action
    set myIP [SA_getmyip]
    set count 0
    # SA_xml_debugflag 1
    # SA_xml_debugfile xml_$myIP.dbg"""

    def _generate_procedures(self) -> str:
        """Generate helper TCL procedures."""
        return """    proc random_int {min max} {
        return [expr {int(rand() * ($max - $min + 1)) + $min}]
    }

    proc random_ipv4 {} {
        return "[random_int 1 255].[random_int 0 255].[random_int 0 255].[random_int 0 255]"
    }

    proc random_fqdn {suffix} {
        set chars "abcdefghijklmnopqrstuvwxyz"
        set domain ""
        for {set i 0} {$i < [random_int 5 10]} {incr i} {
            append domain [string index $chars [random_int 0 [expr {[string length $chars] - 1}]]]
        }
        return "www.$domain$suffix"
    }

    proc get_timestamp_offset {seconds_ago} {
        set ctime [clock seconds]
        set target_time [expr {$ctime - $seconds_ago}]
        return [clock format $target_time -format {%Y-%m-%dT%H:%M:%SZ}]
    }
"""

    def _generate_timestamp_vars(self) -> str:
        """Generate TCL timestamp variables based on user's interval config."""
        interval = self.config.polling_interval_seconds

        return f"""    # Time variables (user configured: interval={interval}s)
    set myIP [SA_getmyip]
    set ctime [clock seconds]
    set next_request [expr {{$ctime + {interval}}}]
    set last_update [clock format $ctime -format {{%Y-%m-%dT%H:%M:%SZ}}]
    set next_request_time [clock format $next_request -format {{%Y-%m-%dT%H:%M:%SZ}}]
"""

    def _generate_http_action(self) -> str:
        """Generate %http_get_action section with TCL-based data_source/transaction."""
        tcl = f"%http_get_action {self.config.path}\n\n"

        # Generate helper procedures
        tcl += self._generate_procedures()

        # Generate timestamp variables based on user config
        tcl += self._generate_timestamp_vars()

        # Generate response builder with hardcoded data_source/transaction
        tcl += self._generate_response_builder()

        return tcl

    def _generate_response_builder(self) -> str:
        """Generate JSON response building code with hardcoded data_source/transaction."""
        tcl = '    SA_xml_sethttpcontenttype "application/json"\n'
        tcl += '    SA_xml_clear_plain_text\n\n'

        # Start JSON
        tcl += '    SA_xml_append_plain_text "{"\n'

        # HARDCODED: data_source (uses $myIP from TCL)
        tcl += '    SA_xml_append_plain_text "\\"data_source\\": {"\n'
        tcl += '    SA_xml_append_plain_text "\\"type\\": \\"defensepro\\","\n'
        tcl += '    SA_xml_append_plain_text "\\"ip\\": \\"$myIP\\","\n'
        tcl += '    SA_xml_append_plain_text "\\"version\\": \\"10.6.0.0\\""\n'
        tcl += '    SA_xml_append_plain_text "},"\n'

        # HARDCODED: transaction (uses dynamic timestamps from TCL)
        tcl += '    SA_xml_append_plain_text "\\"transaction\\": {"\n'
        tcl += f'    SA_xml_append_plain_text "\\"request_url\\": \\"https://$myIP:8790{self.config.path}\\","\n'
        tcl += '    SA_xml_append_plain_text "\\"response_type\\": \\"complete\\","\n'
        tcl += '    SA_xml_append_plain_text "\\"last_update\\": \\"$last_update\\","\n'
        tcl += '    SA_xml_append_plain_text "\\"next_request_time\\": \\"$next_request_time\\""\n'
        tcl += '    SA_xml_append_plain_text "},"\n'

        # USER'S DATA: Main data key with user-defined structure
        tcl += f'    SA_xml_append_plain_text "\\"{self.config.data_key}\\": {{"\n'

        # Generate user's data structure
        tcl += self._generate_user_data_structure()

        tcl += '    SA_xml_append_plain_text "}"\n'  # Close data_key
        tcl += '    SA_xml_append_plain_text "}"\n'  # Close root

        return tcl

    def _generate_user_data_structure(self) -> str:
        """Generate TCL code for user's data structure."""
        tcl = ""

        # Filter out empty arrays (repeat=0)
        non_empty_fields = []
        for key in self.config.data_structure.keys():
            field_value = self.config.data_structure[key]

            # Skip arrays with repeat=0
            if field_value.type == FieldType.ARRAY:
                if field_value.repeat == 0:
                    continue  # Skip this field
                if field_value.repeat is None and field_value.repeat_min == 0 and field_value.repeat_max == 0:
                    continue  # Skip this field

            non_empty_fields.append((key, field_value))

        # Generate TCL for non-empty fields only
        for i, (key, field_value) in enumerate(non_empty_fields):
            tcl += self._generate_field_value(key, field_value, indent=1)

            if i < len(non_empty_fields) - 1:
                tcl += '    SA_xml_append_plain_text ","\n'

        return tcl

    def _generate_field_value(
        self,
        field_name: str,
        field_value: FieldValue,
        indent: int = 0,
        array_index_var: str = None
    ) -> str:
        """Generate TCL code for a field value (recursive).

        Args:
            field_name: Name of the field
            field_value: FieldValue configuration
            indent: Current indentation level
            array_index_var: Variable name for array index (e.g., "i", "j")
        """
        ind = "    " * indent
        tcl = ""

        if field_value.type == FieldType.STRING:
            mode = getattr(field_value, 'mode', 'fixed')

            if mode == 'random':
                # Random string - treat as random IPv4 for now
                tcl += f'{ind}set ip [random_ipv4]\n'
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$ip\\""\n'
            else:
                # Fixed value
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"{field_value.value}\\""\n'

        elif field_value.type == FieldType.NUMBER:
            mode = getattr(field_value, 'mode', 'fixed')

            if mode == 'random':
                min_val = field_value.min or 0
                max_val = field_value.max or 100
                tcl += f'{ind}set val [random_int {min_val} {max_val}]\n'
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": $val"\n'
            else:
                # Fixed value
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": {field_value.value}"\n'

        elif field_value.type == FieldType.BOOLEAN:
            bool_str = "true" if field_value.value else "false"
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": {bool_str}"\n'

        elif field_value.type == FieldType.NULL:
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": null"\n'

        elif field_value.type == FieldType.TIMESTAMP:
            # Generate timestamp using helper function
            # User enters positive numbers (e.g., 120 for "120 seconds ago")
            offset = field_value.offset or 0

            if offset == 0:
                # Current time - use pre-generated variable
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$last_update\\""\n'
            else:
                # Use helper function: get_timestamp_offset 120 → current_time - 120
                tcl += f'{ind}set ts [get_timestamp_offset {offset}]\n'
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$ts\\""\n'

        elif field_value.type == FieldType.RANDOM:
            tcl += f'{ind}set val [random_int {field_value.min} {field_value.max}]\n'
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": $val"\n'

        elif field_value.type == FieldType.RANDOM_IPV4:
            tcl += f'{ind}set ip [random_ipv4]\n'
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$ip\\""\n'

        elif field_value.type == FieldType.RANDOM_FQDN:
            suffix = field_value.suffix or ".com"
            tcl += f'{ind}set fqdn [random_fqdn "{suffix}"]\n'
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$fqdn\\""\n'

        elif field_value.type == FieldType.TEMPLATE:
            # Replace {{INDEX}} with array index variable
            template = field_value.value
            if "{{INDEX}}" in template and array_index_var:
                # Use TCL variable substitution
                template_expr = template.replace("{{INDEX}}", f"${array_index_var}")
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"{template_expr}\\""\n'
            else:
                tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"{template}\\""\n'

        elif field_value.type == FieldType.RANDOM_COMPOSITE:
            # Generate composite value from parts
            tcl += f'{ind}set composite ""\n'
            for part in field_value.parts or []:
                if part["type"] == "random":
                    tcl += f'{ind}append composite [random_int {part["min"]} {part["max"]}]\n'
                elif part["type"] == "literal":
                    tcl += f'{ind}append composite "{part["value"]}"\n'
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": \\"$composite\\""\n'

        elif field_value.type == FieldType.OBJECT:
            tcl += f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": {{"\n'

            # Filter out empty arrays from properties
            props = field_value.properties or {}
            non_empty_props = []

            for prop_key, prop_value in props.items():
                # Skip arrays with repeat=0
                if prop_value.type == FieldType.ARRAY:
                    if prop_value.repeat == 0:
                        continue
                    if prop_value.repeat is None and prop_value.repeat_min == 0 and prop_value.repeat_max == 0:
                        continue
                non_empty_props.append((prop_key, prop_value))

            # Generate TCL for non-empty properties only
            for i, (prop_key, prop_value) in enumerate(non_empty_props):
                tcl += self._generate_field_value(prop_key, prop_value, indent + 1, array_index_var)

                if i < len(non_empty_props) - 1:
                    tcl += f'{ind}    SA_xml_append_plain_text ","\n'

            tcl += f'{ind}SA_xml_append_plain_text "}}"\n'

        elif field_value.type == FieldType.ARRAY:
            tcl += self._generate_array_field(field_name, field_value, indent)

        return tcl

    def _generate_array_field(
        self,
        field_name: str,
        field_value: FieldValue,
        indent: int
    ) -> str:
        """Generate TCL code for array field."""
        ind = "    " * indent
        tcl = f'{ind}SA_xml_append_plain_text "\\"\\"{field_name}\\": ["\n'

        # Determine repeat count
        if field_value.repeat:
            count_expr = str(field_value.repeat)
        else:
            count_expr = f'[random_int {field_value.repeat_min} {field_value.repeat_max}]'

        # Choose unique loop variable based on indent level
        loop_var = chr(ord('i') + indent)  # i, j, k, l, etc.

        tcl += f'{ind}set arr_count_{loop_var} {count_expr}\n'
        tcl += f'{ind}for {{set {loop_var} 0}} {{${loop_var} < $arr_count_{loop_var}}} {{incr {loop_var}}} {{\n'

        # Generate array item
        if field_value.item:
            if field_value.item.type == FieldType.OBJECT:
                # Array of objects
                tcl += f'{ind}    SA_xml_append_plain_text "{{"\n'

                props = field_value.item.properties or {}
                prop_keys = list(props.keys())
                for i, prop_key in enumerate(prop_keys):
                    prop_value = props[prop_key]
                    tcl += self._generate_field_value(prop_key, prop_value, indent + 2, loop_var)

                    if i < len(prop_keys) - 1:
                        tcl += f'{ind}        SA_xml_append_plain_text ","\n'

                tcl += f'{ind}    SA_xml_append_plain_text "}}"\n'
            else:
                # Array of primitives (not common but supported)
                tcl += self._generate_field_value("", field_value.item, indent + 1, loop_var)

        # Add comma between array items
        tcl += f'{ind}    if {{${loop_var} < [expr $arr_count_{loop_var} - 1]}} {{\n'
        tcl += f'{ind}        SA_xml_append_plain_text ","\n'
        tcl += f'{ind}    }}\n'
        tcl += f'{ind}}}\n'

        tcl += f'{ind}SA_xml_append_plain_text "]"\n'

        return tcl
```

---

### File: `backend/app/modules/reporter/polling/polling_service.py`

**Purpose:** Service layer for template management (CRUD) and XMF operations.

**Key Methods:**
- `create_template()`: Save template to MongoDB
- `get_template()`: Retrieve template by ID
- `list_templates()`: List all templates (lightweight)
- `delete_template()`: Delete template from MongoDB
- `generate_xmf_from_template()`: Generate XMF from saved template
- `generate_xmf_from_config()`: Generate XMF from endpoint config (without saving)
- `load_xmf_to_simulator()`: Full flow - write XMF, create DeviceMap, load to simulator

**Full Code (308 lines):**

```python
"""Polling service for template management and XMF loading."""

from datetime import datetime, timezone
from typing import Tuple
from bson import ObjectId

from backend.app.models.polling import PollingTemplateCreate, EndpointConfig
from backend.app.modules.reporter.polling.xmf_generator import XMFGenerator
from backend.app.utils.logger import logger
from backend.app.utils.sapro_ssh import get_sapro_ssh_client


class PollingService:
    """Service for polling template management and XMF operations."""

    def __init__(self, mongo_db, sapro_handler):
        """Initialize polling service.

        Args:
            mongo_db: MongoDB database instance
            sapro_handler: Sapro communication handler instance
        """
        self.mongo_db = mongo_db
        self.sapro_handler = sapro_handler

    async def create_template(self, template: PollingTemplateCreate) -> str:
        """Save template to MongoDB.

        Args:
            template: Template creation request

        Returns:
            MongoDB ObjectId as string

        Raises:
            ValueError: If template name already exists
        """
        collection = self.mongo_db["polling_templates"]

        # Check unique name
        existing = collection.find_one({"name": template.name})
        if existing:
            raise ValueError(f"Template name '{template.name}' already exists")

        now = datetime.now(timezone.utc)
        doc = {
            "name": template.name,
            "description": template.description,
            "endpoint": template.endpoint.model_dump(),
            "created_at": now,
            "updated_at": now,
        }

        result = collection.insert_one(doc)
        logger.info(f"Created polling template: {template.name} (ID: {result.inserted_id})")
        return str(result.inserted_id)

    async def get_template(self, template_id: str) -> dict:
        """Retrieve template from MongoDB.

        Args:
            template_id: MongoDB ObjectId as string

        Returns:
            Template document

        Raises:
            ValueError: If template not found
        """
        collection = self.mongo_db["polling_templates"]
        oid = ObjectId(template_id)
        doc = collection.find_one({"_id": oid})

        if not doc:
            raise ValueError(f"Template not found: {template_id}")

        return doc

    async def list_templates(self) -> list:
        """List all templates (lightweight - no full config).

        Returns:
            List of template summaries
        """
        collection = self.mongo_db["polling_templates"]
        cursor = collection.find({}, {"endpoint": 0})

        result = []
        for doc in cursor:
            result.append({
                "_id": str(doc["_id"]),
                "name": doc["name"],
                "description": doc.get("description"),
                "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None
            })

        return result

    async def delete_template(self, template_id: str) -> bool:
        """Delete template from MongoDB.

        Args:
            template_id: MongoDB ObjectId as string

        Returns:
            True if deleted, False if not found
        """
        collection = self.mongo_db["polling_templates"]
        oid = ObjectId(template_id)

        result = collection.delete_one({"_id": oid})

        if result.deleted_count > 0:
            logger.info(f"Deleted polling template: {template_id}")
            return True
        return False

    async def generate_xmf_from_template(
        self,
        template_id: str
    ) -> str:
        """Generate XMF content from saved template.

        NOTE: No simulator IP/version needed - they're generated in TCL!

        Args:
            template_id: MongoDB template ID

        Returns:
            Generated XMF TCL script
        """
        doc = await self.get_template(template_id)
        endpoint_config = EndpointConfig(**doc["endpoint"])

        generator = XMFGenerator(endpoint_config)
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from template: {template_id}")
        return xmf_content

    async def generate_xmf_from_config(
        self,
        endpoint_config: EndpointConfig
    ) -> str:
        """Generate XMF content from endpoint config (without saving).

        NOTE: No simulator IP/version needed - they're generated in TCL!

        Args:
            endpoint_config: Endpoint configuration

        Returns:
            Generated XMF TCL script
        """
        generator = XMFGenerator(endpoint_config)
        xmf_content = generator.generate_xmf()

        logger.info(f"Generated XMF from config: {endpoint_config.path}")
        return xmf_content

    def _write_xmf_to_filesystem(
        self,
        xmf_content: str,
        xmf_filename: str,
        workspace: str = "default"
    ) -> Tuple[bool, str]:
        """Write XMF content to filesystem via SSH.

        Args:
            xmf_content: Generated XMF TCL script
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            workspace: Workspace name

        Returns:
            (success, xmf_path or error_message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # Determine XMF directory based on workspace
            if workspace == "default":
                xmf_dir = "/opt/sapro/xml/"
            else:
                xmf_dir = f"/opt/sapro/projects/{workspace}/xml/"

            # Ensure directory exists
            mkdir_cmd = f"mkdir -p {xmf_dir}"
            ssh_client.execute_command(mkdir_cmd)

            xmf_path = f"{xmf_dir}{xmf_filename}"

            # Escape content for shell
            escaped_content = xmf_content.replace("'", "'\\''")
            write_cmd = f"echo '{escaped_content}' > {xmf_path}"

            success, output = ssh_client.execute_command(write_cmd)

            if not success:
                return False, f"Failed to write XMF file: {output}"

            logger.info(f"XMF file written to: {xmf_path}")
            return True, xmf_path

        except Exception as e:
            logger.error(f"Failed to write XMF to filesystem: {e}", exc_info=True)
            return False, str(e)

    def _create_device_map_xml(
        self,
        simulator_ip: str,
        xmf_filename: str
    ) -> str:
        """Create DeviceMap XML that references the XMF file.

        Args:
            simulator_ip: Simulator IP address
            xmf_filename: XMF filename (e.g., "50.50.180.1.xmf")

        Returns:
            DeviceMap XML string
        """
        return f'''<DeviceMap
    Release = "11.0"
    Description = ""
    UserData = ""
    SetupFile = ""
    Interface = ""
    Separator = ""
    StartInterfaceNum = "0"
    Username = "">
    <Device
        Name = "{simulator_ip}//161"
        Community = "public"
        Timeout = "3000"
        AuthPassword = ""
        PrivPassword = ""
        FileList = ""
        AgentFile = ""
        MibFile = "DefensePro_DP10_6_03.cmf"
        TelCmdFile = ""
        SoapFile = "{xmf_filename}"
        StartOnLoad = "No"
        Separator = ""
        Description = ""
        Location = ""
        Username = ""
        V1Enterprise = ""
        AuthUsername = ""
        PrivUsername = ""
        Context = ""
        MaxRepetitions = ""
        ActionFile = ""
        RemoteExtFile = ""
    />
</DeviceMap>'''

    async def load_xmf_to_simulator(
        self,
        simulator_ip: str,
        xmf_content: str,
        xmf_filename: str,
        map_name: str,
        workspace: str = "default"
    ) -> Tuple[bool, str]:
        """Load XMF onto simulator using update_device flow.

        Args:
            simulator_ip: Simulator IP address (for DeviceMap and routing)
            xmf_content: Generated XMF TCL script
            xmf_filename: User-provided XMF filename (e.g., 'attack_data.xmf')
            map_name: Map name where simulator is located
            workspace: Workspace name

        Returns:
            (success, message)
        """
        # Step 1: Write XMF to filesystem
        success, xmf_path_or_error = self._write_xmf_to_filesystem(
            xmf_content, xmf_filename, workspace
        )

        if not success:
            return False, f"Failed to write XMF file: {xmf_path_or_error}"

        logger.info(f"XMF file written: {xmf_path_or_error}")

        # Step 2: Create DeviceMap XML referencing the XMF
        device_xml = self._create_device_map_xml(simulator_ip, xmf_filename)

        # Step 3: Call sapro_handler.update_device()
        try:
            success, message = self.sapro_handler.update_device(
                device_ip=simulator_ip,
                raw_xml_content=device_xml,
                map_name=map_name,
                workspace=workspace
            )

            if not success:
                return False, f"Failed to update device on Sapro: {message}"

            logger.info(f"Polling configuration loaded successfully for {simulator_ip} with XMF: {xmf_filename}")
            return True, f"Polling configuration loaded successfully for {simulator_ip}"

        except Exception as e:
            logger.error(f"Failed to update device: {e}", exc_info=True)
            return False, f"Failed to update device: {e}"
```

---

### File: `backend/app/modules/reporter/polling/__init__.py`

**Purpose:** Module initialization - exports service classes.

**Full Code (25 lines):**

```python
"""
Polling module for DefensePro API endpoint simulation.

This module provides functionality to:
- Generate XMF (TCL) files that simulate DefensePro REST API endpoints
- Manage polling configuration templates in MongoDB
- Load polling configurations onto simulators via Sapro

Main components:
- PollingService: Template CRUD and XMF loading operations
- XMFGenerator: Converts endpoint configurations to XMF (TCL) scripts

The XMF files are executed by Sapro's embedded HTTP server to respond to
CyberController's polling requests with simulated attack data, traffic statistics,
and other DefensePro API responses.
"""

from .polling_service import PollingService
from .xmf_generator import XMFGenerator

__all__ = [
    "PollingService",
    "XMFGenerator",
]
```

---

## Backend Routes

### File: `backend/app/routes/reporter.py`

**Purpose:** REST API endpoints for polling operations.

**Key Endpoints:**

#### 1. POST `/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling`
- **Purpose:** Load polling configuration to simulator
- **Payload:** `PollingPayload` (template_id OR endpoint_config + xmf_filename)
- **Process:**
  1. Generate XMF from template or config
  2. Write XMF to Sapro filesystem
  3. Create DeviceMap XML
  4. Load to simulator via update_device
- **Returns:** ReporterResponse

#### 2. POST `/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling/save-xmf`
- **Purpose:** Save XMF file without loading to simulator
- **Payload:** Same as above
- **Process:** Write XMF to filesystem only
- **Returns:** ReporterResponse with file path

**Relevant Code Section (lines 217-315):**

```python
@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def set_polling_config(
        cc_ip: str,
        simulator_ip: str,
        payload: ReporterPollingPayload,
        _current_user: User = Depends(require_cc_access),
        sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
        db: Session = Depends(get_db),
        mongo_db=Depends(get_mongo_db),
) -> ReporterResponse:
    """Send polling configuration to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: Polling configuration (template_id or endpoint_config)
        _current_user: Authenticated user with cc_admin or admin role
        sapro_handler: Sapro communication handler instance
        db: SQLAlchemy database session
        mongo_db: MongoDB database instance

    Returns:
        ReporterResponse with success status and message
    """
    try:
        # Validate input - must provide either template_id or endpoint_config
        if not payload.template_id and not payload.endpoint_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either template_id or endpoint_config"
            )

        # Get simulator info from database
        simulator = db.get(Simulator, simulator_ip)
        if not simulator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Simulator not found: {simulator_ip}"
            )

        # Get map name
        map_name = simulator.map
        if not map_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Simulator {simulator_ip} has no map assigned"
            )

        # Get workspace from current user
        workspace = _current_user.workspace if _current_user.workspace else "default"

        # Create polling service
        service = PollingService(mongo_db, sapro_handler)

        # Generate XMF content
        if payload.template_id:
            logger.info(f"Generating XMF from template {payload.template_id} for {simulator_ip}")
            xmf_content = await service.generate_xmf_from_template(payload.template_id)
        else:
            logger.info(f"Generating XMF from config for {simulator_ip}")
            xmf_content = await service.generate_xmf_from_config(payload.endpoint_config)

        # Load to simulator
        success, message = await service.load_xmf_to_simulator(
            simulator_ip=simulator_ip,
            xmf_content=xmf_content,
            xmf_filename=payload.xmf_filename,
            map_name=map_name,
            workspace=workspace
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

        logger.info(f"Polling config loaded to {simulator_ip}: {message}")
        return ReporterResponse(success=True, message=message)

    except HTTPException:
        raise
    except ValueError as e:
        # Template not found or validation error
        logger.error(f"Validation error in polling config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Failed to set polling config for {simulator_ip}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set polling configuration: {str(e)}"
        )
```

---

## Frontend Types

### File: `frontend/src/types/polling.ts`

**Purpose:** TypeScript type definitions matching backend Pydantic models.

**Key Exports:**
- `FieldType` enum: All supported field types
- `RandomCompositePart` interface: Parts of composite values
- `FieldValue` interface: Recursive field configuration
- `EndpointConfig` interface: User endpoint configuration
- `PollingTemplate` interface: Full template with metadata
- `PollingTemplateSummary` interface: Lightweight template for lists
- `PollingPayload` interface: Request payload for endpoints
- `DATA_KEY_OPTIONS` constant: Pre-configured data key options

**Full Code (247 lines):**

```typescript
/**
 * TypeScript types for Polling API integration.
 *
 * Matches backend Pydantic models from backend/app/models/polling.py
 * Provides type-safe interfaces for polling template management and XMF generation.
 */

/**
 * Enum for all supported field types in polling data structure.
 *
 * Static types: STRING, NUMBER, BOOLEAN, NULL
 * Dynamic types: TIMESTAMP, RANDOM, RANDOM_IPV4, RANDOM_FQDN, RANDOM_COMPOSITE, TEMPLATE
 * Container types: OBJECT, ARRAY
 */
export enum FieldType {
  // Static types
  STRING = 'string',
  NUMBER = 'number',
  BOOLEAN = 'boolean',
  NULL = 'null',

  // Dynamic types
  TIMESTAMP = 'timestamp',
  RANDOM = 'random',
  RANDOM_IPV4 = 'random_ipv4',
  RANDOM_FQDN = 'random_fqdn',
  RANDOM_COMPOSITE = 'random_composite',
  TEMPLATE = 'template',

  // Container types
  OBJECT = 'object',
  ARRAY = 'array',
}

/**
 * Part of a random composite value (for building composite values like attack IDs).
 */
export interface RandomCompositePart {
  type: 'random' | 'literal';
  min?: number;
  max?: number;
  value?: string;
}

/**
 * Recursive field value configuration.
 * Represents a single field in the user's data structure with all possible configurations.
 *
 * - For static values (STRING, NUMBER, BOOLEAN, NULL): use 'value' field
 * - For random numbers (RANDOM): use 'min' and 'max'
 * - For random FQDN (RANDOM_FQDN): use 'suffix'
 * - For random composite (RANDOM_COMPOSITE): use 'parts' array
 * - For timestamp (TIMESTAMP): use 'offset' (seconds from current time)
 * - For template substitution (TEMPLATE): use 'value' with {{INDEX}} placeholder
 * - For object (OBJECT): use 'properties' map
 * - For array (ARRAY): use 'repeat' or 'repeat_min'/'repeat_max', and 'item'
 */
export interface FieldValue {
  type: FieldType;

  // For fields that support random/fixed modes
  mode?: 'random' | 'fixed'; // User chooses random or fixed

  // For static values (STRING, NUMBER, BOOLEAN, NULL)
  value?: string | number | boolean | null;

  // For random numbers (RANDOM)
  min?: number;
  max?: number;

  // For random FQDN (RANDOM_FQDN)
  suffix?: string;

  // For random composite (RANDOM_COMPOSITE)
  parts?: RandomCompositePart[];

  // For timestamp (TIMESTAMP) - offset in seconds from current time
  offset?: number;

  // For object (OBJECT) - nested fields
  properties?: Record<string, FieldValue>;

  // For array (ARRAY)
  repeat?: number; // Fixed count
  repeat_min?: number; // Min count for random
  repeat_max?: number; // Max count for random
  item?: FieldValue; // Array item structure (object or primitive)

  // Enum options (for dropdown fields like tcp-flag, protocol)
  options?: string[];
}

/**
 * Endpoint configuration - user configures only this part.
 *
 * The simulator uses this to:
 * - Respond at the specified endpoint path
 * - Use the polling intervals for XMF generation
 * - Build the user-defined data structure in responses
 */
export interface EndpointConfig {
  path: string; // e.g., '/v1/attack-data'
  method?: string; // default 'GET'
  data_key: string; // Main data key name in response (e.g., 'attack_data')
  polling_interval_seconds?: number; // default 60
  data_structure: Record<string, FieldValue>; // User-defined structure
}

/**
 * Full polling template with metadata and endpoint config.
 */
export interface PollingTemplate {
  _id: string; // MongoDB ObjectId as string
  name: string;
  description: string;
  created_at: string; // ISO format datetime
  endpoint: EndpointConfig;
}

/**
 * Lightweight template summary (without full config).
 * Used for list operations.
 */
export interface PollingTemplateSummary {
  _id: string;
  name: string;
  description?: string;
  created_at?: string;
}

/**
 * Request payload for creating a new polling template.
 */
export interface PollingTemplateCreate {
  name: string;
  description: string;
  endpoint: EndpointConfig;
}

/**
 * Payload for polling configuration endpoints.
 *
 * User provides either:
 * - template_id: to load and use a saved template
 * - endpoint_config: to generate on-the-fly without saving
 *
 * Always required:
 * - xmf_filename: user-provided XMF filename (e.g., 'attack_data.xmf')
 */
export interface PollingPayload {
  template_id?: string; // Load from saved template
  endpoint_config?: EndpointConfig; // Or generate on-the-fly
  xmf_filename: string; // User-provided filename (required)
}

/**
 * Generic polling API response.
 */
export interface PollingResponse {
  success: boolean;
  message: string;
}

/**
 * Response from list templates endpoint.
 */
export interface TemplateListResponse {
  success: boolean;
  templates: PollingTemplateSummary[];
}

/**
 * Response from get template detail endpoint.
 */
export interface TemplateDetailResponse {
  success: boolean;
  template: PollingTemplate;
}

/**
 * Response from create template endpoint.
 */
export interface TemplateCreateResponse {
  success: boolean;
  template_id: string; // MongoDB ObjectId as string
  message: string;
}

/**
 * Data key option for UI dropdown/selector.
 * Maps user-facing labels to technical values and documentation.
 */
export interface DataKeyOption {
  value: string; // e.g., 'attack_data'
  label: string; // e.g., 'Attack Data'
  endpoint: string; // e.g., '/v1/attack-data'
  description: string; // e.g., 'DNS-Protection and Behavioral-DoS attack data'
}

/**
 * Pre-configured data key options matching DefensePro API endpoints.
 */
export const DATA_KEY_OPTIONS: DataKeyOption[] = [
  {
    value: 'attack_data',
    label: 'Attack Data',
    endpoint: '/v1/attack-data',
    description: 'DNS-Protection and Behavioral-DoS attack data',
  },
  {
    value: 'application_traffic_v1',
    label: 'Application Traffic (v1)',
    endpoint: '/v1/traffic/application',
    description: 'TLS-Fingerprint application data - array structure',
  },
  {
    value: 'application_traffic_v2',
    label: 'Application Traffic (v2)',
    endpoint: '/v2/traffic/application',
    description: 'TLS-Fingerprint and DNS-Protection - nested object with categories',
  },
  {
    value: 'policy_traffic',
    label: 'Policy Traffic',
    endpoint: '/v1/traffic/policy',
    description: 'Policy-based traffic statistics',
  },
  {
    value: 'application_characteristics',
    label: 'Application Characteristics (Web DDoS Baseline)',
    endpoint: '/v1/traffic/application/characteristics',
    description: 'Web DDoS baseline and TLS fingerprint characteristics',
  },
];

/**
 * Helper type for UI field configuration.
 * Used to track field hierarchy and nesting in the UI builder.
 */
export interface FieldConfig {
  id: string; // Unique field identifier in the UI
  name: string; // Field name
  value: FieldValue; // Field configuration
  parentId?: string; // Parent field ID for nested fields
  level: number; // Nesting level (0 = root)
}
```

---

## Frontend Services

### File: `frontend/src/api/services/polling.service.ts`

**Purpose:** TypeScript API client functions for polling endpoints.

**Key Functions:**
- `saveXmfToSimulator()`: Write XMF to filesystem only
- `setPollingConfig()`: Full flow - generate, save, and load XMF
- `createTemplate()`: Save new template
- `listTemplates()`: List all templates
- `getTemplate()`: Get template details
- `deleteTemplate()`: Delete template

**Full Code (150 lines):**

```typescript
/**
 * Polling API client functions.
 *
 * Provides type-safe async functions for:
 * - Saving XMF files to Sapro filesystem
 * - Setting polling configuration on simulators
 * - Managing polling templates (CRUD operations)
 */

import axios from 'axios';
import {
  PollingPayload,
  PollingResponse,
  PollingTemplateCreate,
  TemplateListResponse,
  TemplateDetailResponse,
  TemplateCreateResponse,
} from '../../types/polling';

// API base URL - defaults to /api but can be configured via environment
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';

/**
 * Save XMF file to Sapro filesystem (does NOT load to simulator).
 *
 * Use this when you want to prepare an XMF configuration file
 * for later manual use or review.
 *
 * @param ccIp - CyberController IP address
 * @param simulatorIp - Target simulator IP address (for routing only)
 * @param payload - Polling payload with template_id or endpoint_config and xmf_filename
 * @returns Promise with success status and file path
 */
export const saveXmfToSimulator = async (
  ccIp: string,
  simulatorIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  const response = await axios.post<PollingResponse>(
    `${API_BASE_URL}/cc/${ccIp}/simulators/${simulatorIp}/reporter/polling/save-xmf`,
    payload
  );
  return response.data;
};

/**
 * Set polling configuration on simulator (saves XMF and loads to device).
 *
 * This is the full flow that:
 * 1. Generates XMF from template or config
 * 2. Saves XMF to Sapro filesystem
 * 3. Creates DeviceMap XML
 * 4. Loads to simulator via update_device()
 * 5. Simulator starts responding immediately
 *
 * @param ccIp - CyberController IP address
 * @param simulatorIp - Target simulator IP address
 * @param payload - Polling payload with template_id or endpoint_config and xmf_filename
 * @returns Promise with success status and message
 */
export const setPollingConfig = async (
  ccIp: string,
  simulatorIp: string,
  payload: PollingPayload
): Promise<PollingResponse> => {
  const response = await axios.post<PollingResponse>(
    `${API_BASE_URL}/cc/${ccIp}/simulators/${simulatorIp}/reporter/polling`,
    payload
  );
  return response.data;
};

/**
 * Create a new polling template.
 *
 * Templates are stored in MongoDB and can be reused across multiple simulators.
 *
 * @param ccIp - CyberController IP address
 * @param template - Template data (name, description, endpoint config)
 * @returns Promise with template ID and success message
 */
export const createTemplate = async (
  ccIp: string,
  template: PollingTemplateCreate
): Promise<TemplateCreateResponse> => {
  const response = await axios.post<TemplateCreateResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates`,
    template
  );
  return response.data;
};

/**
 * List all polling templates.
 *
 * Returns lightweight summaries without full endpoint configurations.
 * Use getTemplate() to fetch full details.
 *
 * @param ccIp - CyberController IP address
 * @returns Promise with array of template summaries
 */
export const listTemplates = async (
  ccIp: string
): Promise<TemplateListResponse> => {
  const response = await axios.get<TemplateListResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates`
  );
  return response.data;
};

/**
 * Get polling template details by ID.
 *
 * Returns the full template including endpoint configuration
 * and all field definitions.
 *
 * @param ccIp - CyberController IP address
 * @param templateId - MongoDB template ID
 * @returns Promise with full template details
 */
export const getTemplate = async (
  ccIp: string,
  templateId: string
): Promise<TemplateDetailResponse> => {
  const response = await axios.get<TemplateDetailResponse>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};

/**
 * Delete a polling template.
 *
 * Permanently removes the template from MongoDB.
 * This does not affect XMF files that were already generated from it.
 *
 * @param ccIp - CyberController IP address
 * @param templateId - MongoDB template ID
 * @returns Promise with success status
 */
export const deleteTemplate = async (
  ccIp: string,
  templateId: string
): Promise<{ success: boolean; message: string }> => {
  const response = await axios.delete<{ success: boolean; message: string }>(
    `${API_BASE_URL}/cc/${ccIp}/polling/templates/${templateId}`
  );
  return response.data;
};
```

---

## Frontend Components

### Found Components in `frontend/src/components/Reporter/Polling/`

#### 1. EndpointConfigPanel.tsx
**Purpose:** UI panel for configuring endpoint settings (data key, interval, path) and data structure definition.

#### 2. PollingDataForm.tsx
**Purpose:** IRP-style accordion form for building nested data structures with all field types.

#### 3. LoadTemplateDialog.tsx
**Purpose:** Dialog to load an existing polling template from MongoDB.

#### 4. SaveTemplateDialog.tsx
**Purpose:** Dialog to save the current configuration as a reusable template.

**Note:** Complete component code not included in this overview due to length (1000+ lines combined). Refer to actual files for full implementation details.

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND - User defines polling configuration                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  EndpointConfigPanel                                               │
│  ├─ Data Key Selector (e.g., attack_data)                         │
│  ├─ Polling Interval                                              │
│  └─ Path (auto-filled)                                            │
│                                                                     │
│  PollingDataForm                                                   │
│  └─ Recursive field builder                                       │
│     ├─ STRING, NUMBER, BOOLEAN, NULL                              │
│     ├─ RANDOM, RANDOM_IPV4, RANDOM_FQDN, RANDOM_COMPOSITE        │
│     ├─ TIMESTAMP, TEMPLATE                                        │
│     ├─ OBJECT (nested)                                            │
│     └─ ARRAY (with repeat counts)                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ API ENDPOINTS                                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ POST /api/cc/{cc}/simulators/{sim}/reporter/polling               │
│      └─ Payload: PollingPayload (template_id OR endpoint_config)  │
│      └─ Xmf_filename: user-provided filename                      │
│                                                                     │
│ POST /api/cc/{cc}/simulators/{sim}/reporter/polling/save-xmf      │
│      └─ Same payload but only saves to filesystem                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BACKEND - PollingService                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ 1. Validate Input                                                 │
│    ├─ Get simulator info from DB                                  │
│    └─ Get workspace from user                                     │
│                                                                     │
│ 2. Generate XMF                                                   │
│    ├─ If template_id: fetch from MongoDB                          │
│    └─ If endpoint_config: use as-is                               │
│                                                                     │
│ 3. XMFGenerator.generate_xmf()                                    │
│    ├─ Generate %xml_init_action                                   │
│    ├─ Generate TCL helper procedures                              │
│    ├─ Generate %http_get_action with:                             │
│    │  ├─ Hardcoded data_source (uses $myIP from TCL)             │
│    │  ├─ Hardcoded transaction (uses dynamic timestamps)         │
│    │  └─ User's data structure (with array loops, random gen)    │
│    └─ Return complete XMF TCL script                              │
│                                                                     │
│ 4. Load to Simulator                                              │
│    ├─ Write XMF to Sapro filesystem via SSH                       │
│    ├─ Create DeviceMap XML referencing XMF                        │
│    └─ Call sapro_handler.update_device()                          │
│       └─ Simulator loads and starts responding                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ SIMULATOR (Sapro)                                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ XMF Execution (%http_get_action)                                  │
│ ├─ Listen on configured endpoint path                             │
│ ├─ Respond with dynamically generated JSON:                       │
│ │  ├─ data_source (with simulator's IP via $myIP)               │
│ │  ├─ transaction (with current time and intervals)              │
│ │  └─ User's data structure (with random values, timestamps)    │
│ └─ CyberController polls and receives simulated data             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### MongoDB Collection: `polling_templates`

**Document Structure:**
```json
{
  "_id": ObjectId,
  "name": "attack_data_v1",
  "description": "ERT Feed and BDos attack data",
  "endpoint": {
    "path": "/v1/attack-data",
    "method": "GET",
    "data_key": "attack_data",
    "polling_interval_seconds": 60,
    "data_structure": { /* FieldValue recursive structure */ }
  },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Key Implementation Details

#### 1. User Configuration Separation
- **User Configures:** `data_structure` only
- **System Auto-Generates:** `data_source` and `transaction` (in TCL at runtime)
- **Benefit:** User focuses on content; system handles infrastructure

#### 2. TCL Timestamp Calculation
- User enters offset in seconds (e.g., `120` = 2 minutes ago)
- TCL uses `get_timestamp_offset` function to calculate actual timestamp
- `next_request_time` calculated from polling interval

#### 3. Template Substitution
- `TEMPLATE` type uses `{{INDEX}}` placeholder
- TCL replaces `{{INDEX}}` with loop variable (e.g., `$i`)
- Example: `pol{{INDEX}}` becomes `pol0`, `pol1`, `pol2` in loop

#### 4. Random Composite Values
- `RANDOM_COMPOSITE` builds values from parts
- Parts can be `random` (with min/max) or `literal` (fixed string)
- Example: `[10-9999]-[timestamp±1000]` for attack_id

#### 5. Array Handling
- Fixed repeat: `repeat: 3`
- Random repeat: `repeat_min: 1, repeat_max: 5`
- Skip arrays with `repeat: 0` during generation
- Unique loop variables per nesting level (`i`, `j`, `k`, etc.)

---

## Summary Table

| Component | Status | Purpose |
|-----------|--------|---------|
| `backend/app/models/polling.py` | ✅ EXISTS | Pydantic models for configuration |
| `backend/app/modules/reporter/polling/xmf_generator.py` | ✅ EXISTS | Converts config to TCL/XMF |
| `backend/app/modules/reporter/polling/polling_service.py` | ✅ EXISTS | Template management & loading |
| `backend/app/modules/reporter/polling/__init__.py` | ✅ EXISTS | Module initialization |
| `backend/app/routes/reporter.py` (polling endpoints) | ✅ EXISTS | REST API endpoints |
| `frontend/src/types/polling.ts` | ✅ EXISTS | TypeScript type definitions |
| `frontend/src/api/services/polling.service.ts` | ✅ EXISTS | API client functions |
| `frontend/src/components/Reporter/Polling/EndpointConfigPanel.tsx` | ✅ EXISTS | Endpoint settings UI |
| `frontend/src/components/Reporter/Polling/PollingDataForm.tsx` | ✅ EXISTS | Data structure builder |
| `frontend/src/components/Reporter/Polling/LoadTemplateDialog.tsx` | ✅ EXISTS | Template loading dialog |
| `frontend/src/components/Reporter/Polling/SaveTemplateDialog.tsx` | ✅ EXISTS | Template saving dialog |

---

## Notes for Refactoring

1. **All core infrastructure exists** - No missing files
2. **Recent TEMPLATE and RANDOM_COMPOSITE support added** - New field types
3. **TCL generation logic is comprehensive** - Handles all field types including nested arrays
4. **Frontend form components are complete** - Full UI for building configurations
5. **Template persistence via MongoDB** - CRUD operations implemented
6. **Simulator loading via Sapro** - Full integration with update_device flow

