# Coding Standards

**Last updated:** February 8, 2026

## Python Conventions

### PEP 8 Compliance

This project follows PEP 8 with the following specifics:

- **Line length**: 120 characters maximum (not the strict 79)
- **Indentation**: 4 spaces (no tabs)
- **Import ordering**: Standard library → Third-party → Local imports
- **Docstrings**: Google-style docstrings for functions/classes

### Naming Conventions

#### Variables and Functions
```python
# Snake case for variables and functions
user_count = 10
simulator_ip = "192.168.1.10"

def get_simulator_status(ip_address: str) -> str:
    """Fetch simulator status from Sapro."""
    return sapro_client.get_status(ip_address)
```

#### Classes
```python
# PascalCase for class names
class SaproClient:
    """Client for interfacing with Sapro simulator infrastructure."""
    pass

class ReporterSNMPPayload(BaseModel):
    """Pydantic model for SNMP trap request payload."""
    pass
```

#### Constants
```python
# UPPER_SNAKE_CASE for constants
DEFAULT_SNMP_PORT = 162
MAX_RETRY_ATTEMPTS = 3
SAPRO_MAP_DIRECTORY = "/opt/sapro/map/"
```

#### Private Members
```python
# Leading underscore for internal/private
def _serialize_object(obj: Any) -> Dict[str, Any]:
    """Internal helper for recursive serialization."""
    pass

class IrpFormatter:
    def __init__(self):
        self._buffer = bytearray()  # Private attribute
```

### Type Hints

**Always use type hints** for function signatures and return types.

**Example from [backend/app/modules/sapro/sapro_client.py](../backend/app/modules/sapro/sapro_client.py)**:

```python
from typing import Dict, List, Optional, Tuple, Any

def create_device(self, ip_address: str, device_type: str = "DefensePro") -> Tuple[bool, str]:
    """Create a new simulator device.

    Args:
        ip_address: IP address for the simulator (e.g., "192.168.1.10")
        device_type: Type of device to create (default: "DefensePro")

    Returns:
        Tuple of (success: bool, message: str)

    Raises:
        SaproException: If Sapro command fails
    """
    pass

def get_simulator_stats(self, ip_address: str) -> Optional[Dict[str, Any]]:
    """Retrieve statistics for a simulator.

    Args:
        ip_address: IP address of the simulator

    Returns:
        Dictionary of statistics, or None if not found
    """
    pass
```

**Union Types (Python 3.10+)**:
```python
# Use | syntax for union types (Python 3.10+)
from typing import Union

# Old style (still valid)
def process_map(map_name: Union[str, Dict[str, str]]) -> bool:
    pass

# New style (preferred)
def process_map(map_name: str | Dict[str, str]) -> bool:
    pass
```

### Import Organization

**Order**: Standard library → Third-party → Local imports

**Example from [backend/app/main.py](../backend/app/main.py)**:

```python
# Standard library imports
from __future__ import annotations
import logging
import os
import sys
import json
from datetime import datetime, timezone
from typing import List
from pathlib import Path
from contextlib import asynccontextmanager

# Third-party imports
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Local application imports
from backend.app.utils.config import settings
from backend.app.utils.database import Base, engine, SessionLocal
from backend.app.routes.sapro import router as sapro_router
from backend.app.routes.user import router as user_router
```

**Grouping**:
- Alphabetical within each group
- Blank line between groups
- Absolute imports only (no relative imports in routes/modules)

### Docstrings

**Use Google-style docstrings** for all public functions and classes.

**Function Docstring Example**:

```python
def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """Execute Sapro command via SSH to localhost or remote host.

    In production with network_mode: host, the backend shares the host's network
    (needed for binding simulator IPs for IRP), but executes Sapro commands via
    SSH to localhost to access the host's Sapro installation.

    Args:
        command: The command to execute on the Sapro system
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Tuple of (success: bool, output: str)

    Raises:
        subprocess.TimeoutExpired: If command execution exceeds timeout
        Exception: For SSH connection errors

    Example:
        >>> success, output = execute_sapro_command("sapcnsl -get_version")
        >>> if success:
        ...     print(f"Sapro version: {output}")
    """
```

**Class Docstring Example**:

```python
class ConvertXml:
    """Convert IdsDataFormat XML files to JSON-serializable Python structures.

    This class parses CyberController IdsDataFormat XML schemas and converts
    them into Python dictionaries suitable for MongoDB storage. It handles:
    - Message definitions
    - Type definitions (primitives, enums, structs)
    - Template definitions
    - Nested namespaces

    Attributes:
        xml_file_path: Path to the XML file being converted
        schema: Parsed schema object (available after convert_xml() call)

    Example:
        >>> converter = ConvertXml("/tmp/IdsDataFormat_9.15.xml")
        >>> converter.convert_xml()
        >>> schema_dict = _serialize_object(converter.schema)
        >>> mongo_db.irp_data_formats.insert_one(schema_dict)
    """
```

**Module Docstring Example** (at top of file):

```python
"""
Reporter module for SNMP trap and IRP message testing.

This module provides endpoints for:
- Sending SNMP traps to simulators
- Parsing and sending IRP messages to CyberController
- Configuring HTTP polling endpoints

All operations support real-time progress tracking via Server-Sent Events (SSE).
"""
from __future__ import annotations
```

### Error Handling

**Always use specific exception types**, not bare `except:`.

**Example from [backend/app/routes/sapro.py](../backend/app/routes/sapro.py)**:

```python
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

@router.post("/simulators", status_code=201)
def create_simulator(
    payload: SaproSimulatorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new simulator."""
    try:
        # Attempt to create simulator via Sapro
        success, message = sapro_client.create_device(payload.ip_address)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sapro error: {message}"
            )

        # Insert into database
        new_sim = Simulator(
            ip_address=payload.ip_address,
            status="created"
        )
        db.add(new_sim)
        db.commit()
        db.refresh(new_sim)

        return {"success": True, "simulator": new_sim}

    except IntegrityError:
        # Duplicate IP address
        db.rollback()
        logger.exception("Duplicate simulator IP: %s", payload.ip_address)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Simulator with IP {payload.ip_address} already exists"
        )

    except SQLAlchemyError as e:
        # Generic database error
        db.rollback()
        logger.exception("Database error creating simulator")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    except Exception as e:
        # Unexpected error
        logger.exception("Unexpected error creating simulator")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
```

**Error Logging**:
- Use `logger.exception()` for automatic stack trace capture
- Log before raising HTTPException
- Include context (user, resource ID, operation)

### Logging

**Use structured logging** with the configured logger.

**Setup** ([backend/app/main.py:87-145](../backend/app/main.py)):

```python
import logging

logger = logging.getLogger("sim-tools")
```

**Logging Levels**:
- `DEBUG`: Detailed diagnostic info (variable values, loop iterations)
- `INFO`: Confirmation that things are working as expected
- `WARNING`: Unexpected but handled situations
- `ERROR`: Serious problems (operation failed)
- `EXCEPTION`: Errors with full stack trace (use `logger.exception()`)

**Examples**:

```python
# INFO - successful operations
logger.info("Simulator %s created successfully", ip_address)
logger.info("SNMP trap sent: %s → %s", trap_type, simulator_ip)

# DEBUG - diagnostic details
logger.debug("Processing trap %d/%d: %s", current, total, trap_name)
logger.debug("SSH command output: %s", output[:200])

# WARNING - unexpected but handled
logger.warning("Simulator %s not found in database, skipping", ip_address)
logger.warning("XML schema version %s already exists, updating", version)

# ERROR - operation failed
logger.error("Failed to connect to Sapro: %s", str(e))
logger.error("SSH command timed out after %d seconds", timeout)

# EXCEPTION - error with full traceback
try:
    result = risky_operation()
except Exception as e:
    logger.exception("Unexpected error in risky_operation")
    raise
```

**Log Format** (Development):
```
2026-02-08T11:30:45 INFO sim-tools.sapro: Simulator 192.168.1.10 created successfully
```

**Log Format** (Production - JSON):
```json
{
  "timestamp": "2026-02-08T11:30:45.123Z",
  "level": "INFO",
  "logger": "sim-tools.sapro",
  "module": "sapro_client",
  "funcName": "create_device",
  "line": 145,
  "message": "Simulator 192.168.1.10 created successfully"
}
```

## Testing Approach

### Current State

- **Status**: No automated tests currently implemented
- **Future**: Plan to add pytest-based unit and integration tests

### Planned Testing Patterns

```python
# pytest structure (planned)
# tests/
#   conftest.py          # Fixtures (DB sessions, mock clients)
#   test_sapro_client.py # Sapro integration tests
#   test_auth.py         # Authentication tests
#   test_reporter.py     # SNMP/IRP endpoint tests

# Example test (planned pattern)
import pytest
from backend.app.modules.sapro.sapro_client import SaproClient

@pytest.fixture
def sapro_client():
    """Provide a test Sapro client."""
    return SaproClient(host="localhost", port=2100)

def test_create_simulator(sapro_client):
    """Test simulator creation."""
    success, message = sapro_client.create_device("192.168.1.100")
    assert success is True
    assert "created" in message.lower()
```

## Java Conventions (Legacy Sapro Components)

### Naming
- **Classes**: PascalCase (`SaproSocket`, `DeviceInfo`)
- **Methods**: camelCase (`getDeviceStatus`, `sendCommand`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_PORT`, `MAX_RETRIES`)
- **Packages**: lowercase (`backend.app.modules.sapro.src`)

### Example from Java-ported Code

**File**: [backend/app/modules/sapro/src/saproSocket.py](../backend/app/modules/sapro/src/saproSocket.py)

```python
# Java naming convention preserved in ported Python code
class SaproSocket:
    """Socket communication with Sapro server (ported from Java)."""

    def sendCommand(self, command: str) -> str:
        """Send command to Sapro (camelCase preserved from Java)."""
        pass

    def receiveResponse(self) -> str:
        """Receive response from Sapro (camelCase preserved from Java)."""
        pass
```

**Note**: Legacy Java-ported code in `backend/app/modules/sapro/src/` retains camelCase naming for consistency with original implementation. New Python code uses snake_case.

## Frontend TypeScript Conventions

### Naming

**Files**: PascalCase for components, camelCase for utilities
```
PollingPage.tsx           # React component
polling.service.ts        # API service
structureParser.ts        # Utility
```

**Variables/Functions**: camelCase
```typescript
const simulatorIp = "192.168.1.10";
function fetchSimulatorList() { }
```

**Types/Interfaces**: PascalCase
```typescript
interface PollingTemplate {
    id: string;
    name: string;
}

type FieldType = "string" | "number" | "boolean";
```

**Constants**: UPPER_SNAKE_CASE
```typescript
const MAX_RETRY_ATTEMPTS = 3;
const API_BASE_URL = "http://localhost:8000";
```

### Type Definitions

**Example from [frontend/src/types/polling.ts](../frontend/src/types/polling.ts)**:

```typescript
export type FieldType =
    | "string"
    | "number"
    | "boolean"
    | "timestamp"
    | "random_ipv4"
    | "object"
    | "array";

export interface FieldValue {
    type: FieldType;
    value?: string | number | boolean | null;
    mode?: "fixed" | "random";
    min?: number;
    max?: number;
    properties?: Record<string, FieldValue>;  // For objects
    repeat?: number;                           // For arrays
    item?: FieldValue;                         // Array item definition
}

export interface EndpointConfig {
    path: string;
    method: string;
    data_key: string;
    polling_interval_seconds: number;
    data_structure: Record<string, FieldValue>;
}
```

### API Service Pattern

**File**: [frontend/src/api/services/polling.service.ts](../frontend/src/api/services/polling.service.ts)

```typescript
import axios from 'axios';
import { EndpointConfig, PollingTemplate } from '../../types/polling';

const API_BASE = '/api/reporter';

export const pollingService = {
    async loadPollingConfig(
        xmfFilename: string,
        endpoints: EndpointConfig[]
    ): Promise<{ success: boolean; message: string }> {
        const response = await axios.post(`${API_BASE}/configure-polling`, {
            xmf_filename: xmfFilename,
            endpoints: endpoints
        });
        return response.data;
    },

    async saveTemplate(
        name: string,
        description: string,
        endpoint: EndpointConfig
    ): Promise<PollingTemplate> {
        const response = await axios.post(`${API_BASE}/polling/templates`, {
            name,
            description,
            endpoint
        });
        return response.data;
    }
};
```

## Code Review Checklist

Before committing code, verify:

- [ ] Type hints on all function signatures
- [ ] Docstrings for public functions/classes
- [ ] Specific exception handling (no bare `except`)
- [ ] Logging at appropriate levels
- [ ] Imports organized (stdlib → 3rd party → local)
- [ ] Line length ≤ 120 characters
- [ ] No commented-out code blocks (delete or document why)
- [ ] Database sessions properly closed (use `Depends(get_db)`)
- [ ] Secrets not hardcoded (use environment variables)
- [ ] HTTPException with appropriate status codes

## Related Documentation

- [API Patterns](./API_PATTERNS.md) - FastAPI endpoint examples
- [Database Schema](./DATABASE_SCHEMA.md) - ORM model examples
- [Architecture](./ARCHITECTURE.md) - Code organization
