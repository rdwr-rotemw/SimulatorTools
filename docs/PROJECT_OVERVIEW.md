# Project Overview

**Last updated:** February 8, 2026

## What is Simulator Tools?

Simulator Tools is a full-stack web application designed to manage DefensePro simulators and their integration with network security testing infrastructure, specifically CyberController and SNMP-based reporting systems.

## Purpose

The application provides a centralized interface for:
- **Simulator Management**: Create, configure, and manage DefensePro simulators via Sapro integration
- **SNMP Trap Testing**: Send configurable SNMP traps to test attack detection and reporting workflows
- **IRP Message Testing**: Parse, send, and validate IRP (Internal Reporting Protocol) messages to CyberController
- **Polling Endpoint Configuration**: Configure and deploy dynamic HTTP polling endpoints for data collection
- **User & Role Management**: Control access to simulators and features through role-based permissions

## Main Components

### Backend (FastAPI + Python)
- **Framework**: FastAPI 0.121.0
- **Language**: Python 3.x
- **Key Libraries**:
  - SQLAlchemy 2.0.44 (PostgreSQL ORM)
  - pymongo 4.15.3 (MongoDB driver)
  - pysnmp 4.4.12 (SNMP protocol)
  - paramiko 4.0.0 (SSH client for Sapro)
  - uvicorn 0.38.0 (ASGI server)
- **Location**: [backend/](../backend/)

### Frontend (React + TypeScript)
- **Framework**: React 19.2.0
- **Language**: TypeScript 4.9.5
- **UI Library**: Material-UI 7.3.5
- **State Management**: Zustand 5.0.8
- **Key Libraries**:
  - axios 1.13.2 (HTTP client)
  - react-router-dom 7.9.6 (routing)
  - @dnd-kit (drag-and-drop for UI builders)
- **Location**: [frontend/src/](../frontend/src/)

### Databases

#### PostgreSQL (Primary Database)
- **Purpose**: Structured data, user accounts, roles, simulators, sessions
- **ORM**: SQLAlchemy with psycopg2-binary
- **Models Location**: [backend/app/models/](../backend/app/models/)

#### MongoDB (Document Store)
- **Purpose**: Flexible schemas for IRP data formats, device templates, polling templates
- **Collections**:
  - `irp_data_formats`: Parsed IRP message schemas from XML
  - `device_templates`: Device configuration templates (JSON)
  - `polling_templates`: HTTP polling endpoint configurations
- **Location**: [backend/app/modules/mongo_models.py](../backend/app/modules/mongo_models.py)

## Key Integrations

### Sapro Integration
- **Purpose**: Interface with DefensePro simulator infrastructure
- **Protocol**: Custom TCP socket protocol (port 2100) + SSH for file operations
- **Capabilities**:
  - Create/delete/start/stop simulators
  - Load XML configuration maps
  - Monitor simulator statistics
  - File transfer via SSH/SCP
- **Implementation**: [backend/app/modules/sapro/](../backend/app/modules/sapro/)
- **Client**: [sapro_client.py](../backend/app/modules/sapro/sapro_client.py)

### CyberController Integration
- **Purpose**: Manage CyberController sessions and IRP message communication
- **Protocol**: SSH (Paramiko) for session management and file operations
- **Capabilities**:
  - Create/delete CC sessions
  - Download IdsDataFormat XML schemas
  - Parse and send IRP messages via UDP
  - Convert XML schemas to JSON for storage
- **Implementation**: [backend/app/routes/cybercontroller.py](../backend/app/routes/cybercontroller.py)

### SNMP Trap System
- **Purpose**: Send test SNMP traps to simulators for attack detection testing
- **Protocol**: SNMP v2c (pysnmp)
- **Features**:
  - Configurable trap parameters (attack category, policy, severity, etc.)
  - Pause/resume functionality during multi-trap sequences
  - Per-simulator trap customization
  - Real-time progress tracking via Server-Sent Events (SSE)
- **Implementation**: [backend/app/modules/reporter/snmp/](../backend/app/modules/reporter/snmp/)

### IRP Message Parsing
- **Purpose**: Parse IdsDataFormat XML schemas and generate IRP binary messages
- **Process**:
  1. Download XML from CyberController
  2. Parse complex nested structures with custom type resolution
  3. Store as JSON in MongoDB
  4. Generate binary IRP messages from templates
  5. Send via UDP to CyberController
- **Implementation**: [backend/app/modules/reporter/irp/](../backend/app/modules/reporter/irp/)

## Technology Choices

### Why FastAPI?
- Automatic OpenAPI/Swagger documentation
- Built-in async/await support for concurrent operations
- Type validation via Pydantic
- High performance ASGI server
- Clean dependency injection system

### Why React + TypeScript?
- Type safety for large-scale frontend development
- Component-based architecture for reusability
- Rich ecosystem (Material-UI, React Hook Form)
- Excellent dev tools and debugging

### Why PostgreSQL + MongoDB?
- **PostgreSQL**: ACID compliance for critical data (users, permissions, simulator state)
- **MongoDB**: Flexible schema for evolving data formats (IRP schemas, templates)
- Each database serves its purpose - structured vs. document data

### Why Zustand?
- Lightweight state management (minimal boilerplate vs. Redux)
- Simple API with hooks
- No context provider wrapping needed
- TypeScript-first design

## Major Modules/Systems

### User Management System
- **Location**: [backend/app/routes/user.py](../backend/app/routes/user.py)
- **Features**: JWT authentication, role-based access control, password hashing (Argon2)
- **Database**: PostgreSQL (users, roles, permissions tables)

### Sapro Simulator Management
- **Location**: [backend/app/routes/sapro.py](../backend/app/routes/sapro.py)
- **Features**: CRUD operations, batch simulator creation, template loading, SSH integration

### Reporter Module (SNMP/IRP/Polling)
- **Location**: [backend/app/routes/reporter.py](../backend/app/routes/reporter.py)
- **Features**: Multi-protocol testing infrastructure with progress tracking

### CyberController Session Management
- **Location**: [backend/app/routes/cybercontroller.py](../backend/app/routes/cybercontroller.py)
- **Features**: Session CRUD, IRP schema management, file downloads

### Polling Endpoint Builder
- **Location**: [backend/app/modules/reporter/polling/](../backend/app/modules/reporter/polling/)
- **Features**: Dynamic HTTP endpoint configuration, TCL code generation, XMF file creation

## Development Environment

- **Primary IDE**: VS Code with Claude Code extension
- **Languages**: Python (backend), TypeScript/React (frontend), Java (legacy Sapro client components)
- **Version Control**: Git
- **Deployment**: Docker-ready with network_mode: host for simulator IP binding

## Current Focus Areas

1. **SNMP Trap System**: Pause/resume, per-trap delays, SSE progress tracking
2. **IRP Message Testing**: XML-to-JSON conversion, nested structure handling, message validation
3. **Polling System**: Multi-endpoint support, template management, TCL code generation
4. **User Experience**: Real-time feedback, error handling, intuitive UIs for complex configurations

## Related Documentation

- [Architecture](./ARCHITECTURE.md) - System architecture and data flow
- [API Patterns](./API_PATTERNS.md) - FastAPI endpoint examples and conventions
- [Database Schema](./DATABASE_SCHEMA.md) - PostgreSQL and MongoDB schemas
- [Setup Guide](./SETUP.md) - Local development setup instructions
