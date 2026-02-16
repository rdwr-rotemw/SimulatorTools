# IRP Message Patterns

**Last updated:** February 8, 2026

## Overview

The IRP (Internal Reporting Protocol) system parses IdsDataFormat XML schemas from CyberController and converts them to JSON for MongoDB storage. It also generates binary IRP messages from templates and sends them via UDP.

## What is IRP?

**IRP** is CyberController's internal protocol for receiving attack reports and security events from DefensePro devices. The protocol structure is defined in XML schema files (`IdsDataFormat_<version>.xml`) that describe:
- Message types (attack start, stop, ongoing, etc.)
- Data types (primitives, enums, structs)
- Field layouts and encoding rules

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ CyberController                                               │
│   └─▶ /home/radware/cc/conf/IdsDataFormat_9.15.0.0.xml      │
└────────────────┬─────────────────────────────────────────────┘
                 │ SSH Download
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend: IRP Parser                                          │
│                                                              │
│  1. Download XML via SSH (cc routes)                         │
│  2. Parse XML → Python objects (ConvertXml)                  │
│  3. Serialize to JSON (irp_module.py)                        │
│  4. Calculate checksum (SHA256)                              │
│  5. Store in MongoDB (irp_data_formats collection)           │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ MongoDB: irp_data_formats collection                         │
│                                                              │
│  {                                                           │
│    "IdsDataFormat_version": "9.15.0.0",                      │
│    "xml_checksum": "a3f5e8...",                              │
│    "schema": {                                               │
│      "messages": {...},                                      │
│      "types": {...},                                         │
│      "templates": {...}                                      │
│    }                                                         │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
```

## XML to JSON Conversion

### Entry Point

**File**: [backend/app/modules/reporter/irp/irp_module.py:16-48](../backend/app/modules/reporter/irp/irp_module.py)

```python
def convert_xml(xml_file_path: str) -> Dict[str, Any]:
    """Convert IdsDataFormat XML file to complete JSON dict for storage.

    Process:
    1. Parse XML with ConvertXml class
    2. Extract schema (messages, types, templates)
    3. Recursively serialize to JSON-compatible dict
    4. Handle nested structures, namespaces, and custom types

    Args:
        xml_file_path: Path to downloaded XML file

    Returns:
        Dict containing complete parsed schema

    Raises:
        RuntimeError: If XML conversion fails
    """
    try:
        # Create ConvertXml instance and parse
        converter = ConvertXml(xml_file_path)
        converter.convert_xml()

        if not getattr(converter, "schema", None):
            return {}

        schema = converter.schema

        # Serialize entire schema to dict
        schema_dict: Dict[str, Any] = {
            "messages": _serialize_messages(getattr(schema, "messages", None)),
            "types": _serialize_types(getattr(schema, "types", None)),
            "templates": _serialize_templates(getattr(schema, "templates", None)),
        }

        # Recursively serialize all objects to JSON-compatible structures
        return _serialize_object(schema_dict)

    except Exception as e:
        logger.exception("XML conversion error: %s", e)
        raise RuntimeError(f"XML conversion error: {e}")
```

### Message Serialization

**File**: [backend/app/modules/reporter/irp/irp_module.py:50-70](../backend/app/modules/reporter/irp/irp_module.py)

```python
def _serialize_messages(messages: Optional[Dict[Any, Any]]) -> Dict[str, Any]:
    """Serialize messages to dict.

    Messages structure:
        messages = {
            1: Message(name="ATTACK_START", data=<struct>),
            2: Message(name="ATTACK_STOP", data=<struct>),
            ...
        }

    Output:
        {
            "1": {
                "name": "ATTACK_START",
                "data": {
                    "type": "struct",
                    "fields": {
                        "alarm_code": {"type": "uint32"},
                        "severity": {"type": "enum", "enum_name": "SeverityLevel"}
                    }
                }
            },
            ...
        }
    """
    if not messages:
        return {}

    out: Dict[str, Any] = {}
    for msg_id, msg in messages.items():
        try:
            name = getattr(msg, "name", None)
            data = getattr(msg, "data", None)
            out[str(msg_id)] = {
                "name": name,
                "data": _serialize_object(data)  # Recursive serialization
            }
        except Exception:
            out[str(msg_id)] = {"name": None, "data": None}
    return out
```

### Type Serialization

**File**: [backend/app/modules/reporter/irp/irp_module.py:73-119](../backend/app/modules/reporter/irp/irp_module.py)

```python
def _serialize_types(types_obj: Optional[Any]) -> Dict[str, Any]:
    """Serialize types to dict.

    Types include:
    - primitives: uint8, uint16, uint32, ipv4, ipv6, string, etc.
    - enums: Named integer constants
    - namespaces: Scoped type definitions
    - fixed_strings: Strings with fixed length
    - bitmaps: Bit field definitions

    Example output:
        {
            "primitives": {
                "uint32": {"size": 4, "signed": false},
                "ipv4": {"size": 4, "format": "ip_address"}
            },
            "enums": {
                "SeverityLevel": {
                    "type": "uint8",
                    "values": {
                        "INFO": 1,
                        "LOW": 2,
                        "MEDIUM": 3,
                        "HIGH": 4,
                        "CRITICAL": 5
                    }
                }
            },
            "namespaces": {
                "attack": {
                    "AttackInfo": {
                        "type": "struct",
                        "fields": {...}
                    }
                }
            }
        }
    """
    if not types_obj:
        return {}

    # Extract primitives
    primitives = getattr(types_obj, "primitives", None) or {}
    fixed_strings = getattr(types_obj, "fixed_strings", None) or {}
    ip_addresses = getattr(types_obj, "ip_address", None) or {}

    # Serialize enums
    enums_raw = getattr(types_obj, "enums", None) or {}
    enums: Dict[str, Any] = {}
    for name, enum in enums_raw.items():
        try:
            enums[name] = {
                "type": getattr(enum, "type", None),
                "values": getattr(enum, "values", None)
            }
        except Exception:
            enums[name] = {"type": None, "values": None}

    # Serialize namespaces (CRITICAL: handles nested structures)
    namespaces_raw = getattr(types_obj, "namespaces", None) or {}
    namespaces: Dict[str, Any] = {}
    for ns_name, ns_dict in namespaces_raw.items():
        try:
            serialized_ns: Dict[str, Any] = {}
            for key, value in ns_dict.items():
                serialized_ns[key] = _serialize_object(value)  # Recursive
            namespaces[ns_name] = serialized_ns
        except Exception:
            namespaces[ns_name] = {}

    return {
        "primitives": primitives,
        "fixed_strings": fixed_strings,
        "ip_addresses": ip_addresses,
        "enums": enums,
        "namespaces": namespaces,
    }
```

### Recursive Serialization Helper

**File**: [backend/app/modules/reporter/irp/irp_module.py:154-253](../backend/app/modules/reporter/irp/irp_module.py)

```python
def _serialize_object(obj: Any) -> Any:
    """Recursively serialize custom objects to JSON-compatible structures.

    Handles:
    - Custom classes with __dict__
    - Nested dictionaries
    - Lists with nested objects
    - Primitives (str, int, float, bool, None)

    This is critical for handling deeply nested IRP schema structures
    like namespaces containing structs containing arrays of enums.

    Example:
        Input: CustomClass(field1="value", field2=NestedClass(x=10))
        Output: {"field1": "value", "field2": {"x": 10}}
    """
    # Handle None
    if obj is None:
        return None

    # Handle primitives
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle lists (recursively serialize items)
    if isinstance(obj, list):
        return [_serialize_object(item) for item in obj]

    # Handle dicts (recursively serialize values)
    if isinstance(obj, dict):
        return {k: _serialize_object(v) for k, v in obj.items()}

    # Handle objects with __dict__ (custom classes)
    if hasattr(obj, "__dict__"):
        serialized = {}
        for key, value in obj.__dict__.items():
            # Skip private attributes
            if not key.startswith("_"):
                serialized[key] = _serialize_object(value)
        return serialized

    # Fallback: convert to string
    return str(obj)
```

## Nested Structure Handling

### Challenge: Deeply Nested XML

IdsDataFormat XML files contain deeply nested structures like:

```xml
<IdsDataFormat>
  <Messages>
    <Message id="1" name="ATTACK_START">
      <Data type="struct">
        <Field name="header" type="CommonHeader"/>
        <Field name="attack_info" type="attack:AttackInfo"/>
        <Field name="source_ips" type="array">
          <ArrayInfo count="dynamic" max="100">
            <Item type="ipv4"/>
          </ArrayInfo>
        </Field>
      </Data>
    </Message>
  </Messages>

  <Types>
    <Namespace name="attack">
      <Struct name="AttackInfo">
        <Field name="severity" type="SeverityEnum"/>
        <Field name="details" type="AttackDetails"/>
      </Struct>
      <Struct name="AttackDetails">
        <Field name="packet_count" type="uint32"/>
        <Field name="protocol" type="ProtocolEnum"/>
      </Struct>
    </Namespace>
  </Types>
</IdsDataFormat>
```

### Solution: Recursive Serialization

The `_serialize_object()` function handles this by:
1. Detecting custom classes via `hasattr(obj, "__dict__")`
2. Recursively serializing each attribute
3. Preserving structure (dicts, lists, nested objects)

**Example Flow**:
```
Message object
  ├─▶ name: "ATTACK_START" (str) → "ATTACK_START"
  └─▶ data: StructData object
        ├─▶ type: "struct" (str) → "struct"
        └─▶ fields: dict
              ├─▶ "header": FieldDef object
              │     ├─▶ name: "header" → "header"
              │     └─▶ type: "CommonHeader" → "CommonHeader"
              └─▶ "attack_info": FieldDef object
                    ├─▶ name: "attack_info" → "attack_info"
                    └─▶ type: NamespaceRef object
                          ├─▶ namespace: "attack" → "attack"
                          └─▶ struct_name: "AttackInfo" → "AttackInfo"
```

**Result** (JSON):
```json
{
    "name": "ATTACK_START",
    "data": {
        "type": "struct",
        "fields": {
            "header": {
                "name": "header",
                "type": "CommonHeader"
            },
            "attack_info": {
                "name": "attack_info",
                "type": {
                    "namespace": "attack",
                    "struct_name": "AttackInfo"
                }
            }
        }
    }
}
```

## Edge Cases and Solutions

### 1. Missing Attributes

**Problem**: Some XML schemas omit optional attributes

**Solution**: Use `getattr()` with default values
```python
name = getattr(msg, "name", None)  # Returns None if missing
data = getattr(msg, "data", None)
```

### 2. Circular References

**Problem**: Schema could contain circular type references

**Solution**: Currently not handled (schemas don't have circularity), but could add visited set:
```python
def _serialize_object(obj: Any, visited: Optional[set] = None) -> Any:
    if visited is None:
        visited = set()

    obj_id = id(obj)
    if obj_id in visited:
        return "<circular reference>"

    visited.add(obj_id)
    # ... serialization logic ...
```

### 3. Namespace Type References

**Problem**: Types can reference other types via namespaces (e.g., `attack:AttackInfo`)

**Solution**: Store namespace as structured object, not string:
```python
# Input: "attack:AttackInfo"
# Output:
{
    "namespace": "attack",
    "struct_name": "AttackInfo"
}
```

This allows lookup during message generation.

### 4. XML Checksum for Deduplication

**Problem**: Same XML uploaded multiple times wastes storage

**Solution**: Calculate SHA256 checksum before storage
```python
import hashlib

def calculate_xml_checksum(xml_path: str) -> str:
    """Calculate SHA256 checksum of XML file."""
    with open(xml_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

# Check if already exists
existing = mongo_db.irp_data_formats.find_one({
    "IdsDataFormat_version": version,
    "xml_checksum": checksum
})

if existing:
    return {"message": "Schema already exists", "id": str(existing["_id"])}
```

## IRP Message Generation (Future)

### Planned Flow

```
1. User selects message type (e.g., "ATTACK_START")
2. Frontend fetches schema from MongoDB
3. User fills in field values via form
4. Backend generates binary IRP message
5. Send via UDP to CyberController
```

### Message Builder Pattern (Planned)

**File**: [backend/app/modules/reporter/irp/tools/message_builder.py](../backend/app/modules/reporter/irp/tools/message_builder.py)

```python
class MessageBuilder:
    """Build binary IRP messages from schema and field values.

    Example:
        >>> schema = mongo_db.irp_data_formats.find_one({"IdsDataFormat_version": "9.15.0.0"})
        >>> builder = MessageBuilder(schema)
        >>> message_bytes = builder.build_message(
        ...     message_id=1,
        ...     fields={
        ...         "alarm_code": 12345,
        ...         "severity": "HIGH",
        ...         "source_ip": "192.168.1.10"
        ...     }
        ... )
        >>> # Send via UDP
        >>> sock.sendto(message_bytes, (cc_ip, irp_port))
    """

    def build_message(self, message_id: int, fields: Dict[str, Any]) -> bytes:
        """Build binary message from field values."""
        # 1. Lookup message schema
        # 2. For each field, encode according to type
        # 3. Pack into binary format (struct.pack)
        # 4. Return bytes
        pass
```

## Storage in MongoDB

### Document Structure

**Collection**: `irp_data_formats`

**Example Document**:
```json
{
    "_id": ObjectId("65b4f3e2a1b2c3d4e5f60001"),
    "IdsDataFormat_version": "9.15.0.0",
    "xml_checksum": "a3f5e8b2c1d9f4e7a6b5c8d2e1f3a4b7c9d0e1f2",
    "created_at": "2026-02-08T10:30:00Z",
    "schema": {
        "messages": {
            "1": {
                "name": "ATTACK_START",
                "data": {
                    "type": "struct",
                    "fields": {
                        "alarm_code": {"type": "uint32"},
                        "severity": {
                            "type": "enum",
                            "enum_name": "SeverityLevel"
                        }
                    }
                }
            }
        },
        "types": {
            "primitives": {...},
            "enums": {...},
            "namespaces": {...}
        },
        "templates": {...}
    }
}
```

### Indexes

**File**: [backend/app/utils/database.py:133-181](../backend/app/utils/database.py)

```python
# Compound index for version + checksum lookups (prevents duplicates)
db.irp_data_formats.create_index([
    ("IdsDataFormat_version", ASCENDING),
    ("xml_checksum", ASCENDING)
], name="version_checksum_idx", sparse=True)

# Version-only index (list all versions)
db.irp_data_formats.create_index([
    ("IdsDataFormat_version", ASCENDING)
], name="version_idx")

# Timestamp index (find recent uploads)
db.irp_data_formats.create_index([
    ("created_at", ASCENDING)
], name="created_at_idx")
```

## IRP Sending (UDP)

### Current Implementation

**File**: [backend/app/modules/reporter/irp/core/irp_formatter.py](../backend/app/modules/reporter/irp/core/irp_formatter.py)

```python
import socket

def send_irp_message(
    message_bytes: bytes,
    cc_ip: str,
    cc_port: int = 4739
) -> bool:
    """Send IRP message via UDP to CyberController.

    Args:
        message_bytes: Binary IRP message
        cc_ip: CyberController IP address
        cc_port: IRP port (default: 4739)

    Returns:
        True if sent successfully

    Note:
        Requires backend to run with network_mode: host to bind
        simulator source IP for realistic IRP reporting.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message_bytes, (cc_ip, cc_port))
        sock.close()
        return True
    except Exception as e:
        logger.exception(f"Failed to send IRP message: {e}")
        return False
```

## Related Documentation

- [Architecture](./ARCHITECTURE.md) - IRP flow in system architecture
- [Database Schema](./DATABASE_SCHEMA.md) - MongoDB irp_data_formats collection
- [Coding Standards](./CODING_STANDARDS.md) - Error handling and logging
- [API Patterns](./API_PATTERNS.md) - IRP upload endpoint implementation
