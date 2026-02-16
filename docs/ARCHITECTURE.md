# Architecture

**Last updated:** February 8, 2026

## Directory Structure

```
SimulatorTools/
├── backend/
│   ├── app/
│   │   ├── db/                      # Database seeding scripts
│   │   │   ├── seed_roles.py
│   │   │   ├── seed_users.py
│   │   │   └── verify_setup.py
│   │   ├── models/                  # SQLAlchemy ORM models (PostgreSQL)
│   │   │   ├── user.py
│   │   │   ├── role.py
│   │   │   ├── permission.py
│   │   │   ├── simulator.py
│   │   │   ├── cc_session.py
│   │   │   ├── polling.py           # Polling endpoint configs
│   │   │   └── audit_log.py
│   │   ├── modules/                 # Business logic modules
│   │   │   ├── sapro/              # Sapro integration
│   │   │   │   ├── sapro_client.py # Main Sapro client
│   │   │   │   ├── template_converter.py  # JSON→XML conversion
│   │   │   │   └── src/            # Legacy Java-ported Sapro protocol
│   │   │   ├── reporter/           # Testing infrastructure
│   │   │   │   ├── snmp/           # SNMP trap sending
│   │   │   │   │   ├── executor.py # SSH command execution
│   │   │   │   │   └── attack_traps.py
│   │   │   │   ├── irp/            # IRP message parsing/sending
│   │   │   │   │   ├── irp_module.py
│   │   │   │   │   ├── core/       # Core IRP functionality
│   │   │   │   │   └── tools/      # Utilities (parsers, converters)
│   │   │   │   └── polling/        # HTTP polling endpoints
│   │   │   │       ├── polling_service.py
│   │   │   │       └── xmf_generator.py  # TCL/XMF generation
│   │   │   ├── cc/                 # CyberController integration
│   │   │   └── mongo_models.py     # MongoDB schema definitions
│   │   ├── routes/                 # FastAPI endpoints (API layer)
│   │   │   ├── user.py             # User authentication/management
│   │   │   ├── role.py             # Role management
│   │   │   ├── permission.py       # Permission management
│   │   │   ├── sapro.py            # Simulator CRUD + templates
│   │   │   ├── cybercontroller.py  # CC session management
│   │   │   ├── reporter.py         # SNMP/IRP/Polling endpoints
│   │   │   ├── snmp_templates.py   # SNMP template CRUD
│   │   │   └── health.py           # Health check endpoint
│   │   ├── schemas/                # Pydantic request/response models
│   │   │   ├── reporter.py         # SNMP, IRP, Polling schemas
│   │   │   ├── sapro_simulator.py
│   │   │   └── common.py
│   │   ├── utils/                  # Shared utilities
│   │   │   ├── config.py           # Pydantic settings (env vars)
│   │   │   ├── database.py         # DB connection setup
│   │   │   ├── auth.py             # JWT authentication
│   │   │   ├── logger.py           # Logging configuration
│   │   │   └── sapro_ssh.py        # SSH client wrapper
│   │   └── main.py                 # FastAPI app entrypoint
│   ├── scripts/                    # Standalone scripts
│   │   └── seed_polling_structures.py
│   └── requirements.txt            # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── api/                    # Axios API client
│   │   │   └── services/           # API service modules
│   │   │       ├── polling.service.ts
│   │   │       └── ...
│   │   ├── components/             # Reusable React components
│   │   │   ├── Reporter/
│   │   │   │   ├── Polling/        # Polling UI builder
│   │   │   │   ├── SNMP/
│   │   │   │   └── IRP/
│   │   │   ├── Sapro/
│   │   │   └── Common/
│   │   ├── pages/                  # Top-level page components
│   │   │   ├── PollingPage.tsx
│   │   │   ├── SNMPPage.tsx
│   │   │   └── ...
│   │   ├── store/                  # Zustand state management
│   │   ├── types/                  # TypeScript type definitions
│   │   │   └── polling.ts
│   │   ├── utils/                  # Frontend utilities
│   │   │   └── structureParser.ts
│   │   ├── App.tsx                 # Main app component
│   │   └── index.tsx               # React entrypoint
│   └── package.json                # Node dependencies
│
├── docs/                           # Documentation (this folder)
└── .env                            # Environment configuration
```

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                          │
│  (Material-UI, Zustand, React Router, TypeScript)              │
│                                                                  │
│  Pages → Components → API Services → Axios HTTP Client          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST + SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                      │
│                                                                  │
│  ┌──────────┐      ┌──────────┐      ┌──────────────┐          │
│  │ Routes   │─────▶│ Modules  │─────▶│ External     │          │
│  │ (API)    │      │ (Logic)  │      │ Integrations │          │
│  └──────────┘      └──────────┘      └──────────────┘          │
│       │                  │                    │                  │
│       │                  │                    ├─▶ Sapro (TCP)   │
│       │                  │                    ├─▶ CC (SSH)      │
│       ▼                  ▼                    └─▶ SNMP (UDP)    │
│  ┌──────────┐      ┌──────────┐                                │
│  │ Schemas  │      │ Models   │                                │
│  │(Pydantic)│      │(ORM)     │                                │
│  └──────────┘      └──────────┘                                │
└───────┬──────────────────┬─────────────────────────────────────┘
        │                  │
        ▼                  ▼
┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │   MongoDB    │
│              │    │              │
│ - users      │    │ - irp_data_  │
│ - roles      │    │   formats    │
│ - simulators │    │ - device_    │
│ - sessions   │    │   templates  │
│ - audit_log  │    │ - polling_   │
│              │    │   templates  │
└──────────────┘    └──────────────┘
```

## Component Interaction Flow

### 1. User Authentication Flow

```
User Login Request (Frontend)
    │
    ▼
POST /api/auth/login (user.py router)
    │
    ├─▶ Validate credentials (bcrypt/Argon2)
    │
    ├─▶ Query PostgreSQL for user + roles
    │
    ├─▶ Generate JWT token (python-jose)
    │
    └─▶ Return token + user info
        │
        ▼
Frontend stores token in Zustand store
    │
    ▼
Subsequent requests include Authorization: Bearer <token>
    │
    ▼
Dependency: require_auth/require_admin validates token
```

**Implementation**: [backend/app/utils/auth.py](../backend/app/utils/auth.py)

### 2. SNMP Trap Sending Flow

```
User configures traps in UI (SNMPPage.tsx)
    │
    ▼
POST /api/reporter/send-snmp-traps
    │
    ├─▶ Validate payload (ReporterSNMPPayload schema)
    │
    ├─▶ Query PostgreSQL for simulator IPs
    │
    ├─▶ Start background task (asyncio)
    │   │
    │   ├─▶ For each trap in sequence:
    │   │   ├─▶ SSH to Sapro host (executor.py)
    │   │   ├─▶ Execute sapcnsl SNMP send command
    │   │   ├─▶ Emit progress via SSE
    │   │   └─▶ Pause if configured (pause field)
    │   │
    │   └─▶ Return completion status
    │
    └─▶ Stream progress to frontend via SSE (/api/reporter/snmp-progress)
        │
        ▼
Frontend displays real-time progress bar
```

**Implementation**:
- Route: [backend/app/routes/reporter.py:268-374](../backend/app/routes/reporter.py)
- Executor: [backend/app/modules/reporter/snmp/executor.py](../backend/app/modules/reporter/snmp/executor.py)

### 3. IRP Message Parsing Flow

```
User uploads IdsDataFormat XML file
    │
    ▼
POST /api/cybercontroller/upload-irp-xml
    │
    ├─▶ Save XML to temp file
    │
    ├─▶ convert_xml(xml_path) → ConvertXml class
    │   │
    │   ├─▶ Parse XML with xml.etree.ElementTree
    │   │
    │   ├─▶ Build schema object:
    │   │   ├─▶ messages (id → {name, data})
    │   │   ├─▶ types (primitives, enums, namespaces)
    │   │   └─▶ templates (structs, fields)
    │   │
    │   └─▶ Recursively serialize to JSON-compatible dict
    │       │
    │       └─▶ Handle nested objects with _serialize_object()
    │
    ├─▶ Calculate XML checksum (hashlib.sha256)
    │
    ├─▶ Store in MongoDB (irp_data_formats collection)
    │   │
    │   └─▶ Indexed by (IdsDataFormat_version, xml_checksum)
    │
    └─▶ Return success response with document ID
```

**Implementation**:
- Parser: [backend/app/modules/reporter/irp/irp_module.py](../backend/app/modules/reporter/irp/irp_module.py)
- Converter: [backend/app/modules/reporter/irp/tools/convert_xml.py](../backend/app/modules/reporter/irp/tools/convert_xml.py)

### 4. Simulator Creation Flow

```
User creates simulator(s) via UI
    │
    ▼
POST /api/simulators (sapro.py router)
    │
    ├─▶ Validate request (SaproSimulatorCreate schema)
    │
    ├─▶ Parse IP range if batch creation (ip_utils.parse_ip_range)
    │
    ├─▶ For each IP in range:
    │   │
    │   ├─▶ sapro_client.create_device(ip)
    │   │   │
    │   │   ├─▶ Connect to Sapro TCP socket (port 2100)
    │   │   │
    │   │   ├─▶ Send "CREATE_DEVICE <ip>" command
    │   │   │
    │   │   └─▶ Parse response
    │   │
    │   ├─▶ Insert into PostgreSQL (simulators table)
    │   │
    │   └─▶ Collect result (success/failure)
    │
    └─▶ Return batch response with per-IP status
```

**Implementation**:
- Route: [backend/app/routes/sapro.py:228-329](../backend/app/routes/sapro.py)
- Client: [backend/app/modules/sapro/sapro_client.py](../backend/app/modules/sapro/sapro_client.py)

### 5. Polling Endpoint Configuration Flow

```
User builds polling config in UI (PollingPage.tsx)
    │
    ├─▶ Drag-and-drop field builder (Material-UI + @dnd-kit)
    │
    ├─▶ Configure field types, values, random generation
    │
    └─▶ Submit configuration
        │
        ▼
POST /api/reporter/configure-polling
    │
    ├─▶ Validate payload (ReporterPollingPayload)
    │
    ├─▶ Generate TCL code (xmf_generator.py)
    │   │
    │   ├─▶ Convert FieldValue tree → TCL dict/list syntax
    │   │
    │   ├─▶ Add data_source (SA_getmyip)
    │   │
    │   ├─▶ Add transaction (timestamps, next_request_time)
    │   │
    │   └─▶ Wrap in TCL proc structure
    │
    ├─▶ Create XMF file structure (XML + embedded TCL)
    │
    ├─▶ SSH to Sapro host
    │   │
    │   └─▶ SCP upload XMF to /opt/sapro/map/
    │
    ├─▶ Load XMF to simulator (sapro_client.load_map)
    │
    └─▶ Return success response
```

**Implementation**:
- Route: [backend/app/routes/reporter.py:470-560](../backend/app/routes/reporter.py)
- Generator: [backend/app/modules/reporter/polling/xmf_generator.py](../backend/app/modules/reporter/polling/xmf_generator.py)

## Database Connections

### PostgreSQL Connection (SQLAlchemy)

**Configuration**: [backend/app/utils/database.py](../backend/app/utils/database.py)

```python
# Connection URL built from environment variables
SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url()
# Example: postgresql+psycopg2://user:pass@172.17.166.10:5432/sim_tools

# Engine with connection pooling
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    future=True,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# FastAPI dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### MongoDB Connection (PyMongo)

**Configuration**: [backend/app/utils/database.py:70-80](../backend/app/utils/database.py)

```python
# Connection URI built from environment variables
MONGO_URI = settings.mongodb_uri()
# Example: mongodb://user:pass@172.17.166.10:27017/sim_tools

# Client (reused across requests)
mongo_client = MongoClient(MONGO_URI)

# Database accessor
def get_mongo_db() -> "pymongo.database.Database":
    db_name = settings.MONGO_DB
    return mongo_client[db_name]
```

## Key Architectural Decisions

### 1. Dual Database Strategy
- **PostgreSQL**: Relational data with strict schemas (users, permissions, simulators)
- **MongoDB**: Flexible schemas that evolve (IRP formats, templates)
- **Rationale**: IRP schemas change frequently with CC versions; storing as JSON avoids migration hell

### 2. SSH-based Sapro Integration
- Backend runs in Docker with `network_mode: host` to bind simulator IPs
- Sapro commands executed via SSH to localhost/remote host
- **Rationale**: Sapro tools (sapcnsl) only available on Sapro host; network_mode: host needed for UDP IRP sends

### 3. Server-Sent Events (SSE) for Progress
- Long-running operations (SNMP trap sequences) stream progress via SSE
- Alternative to WebSockets for one-way server→client updates
- **Rationale**: Simpler than WebSockets, works with standard HTTP

### 4. Pydantic for All Schemas
- Request validation (FastAPI routes)
- Response serialization
- Configuration management (pydantic-settings)
- **Rationale**: Single source of truth for data structures with automatic validation

### 5. Zustand over Redux
- Lightweight state management
- No boilerplate (actions, reducers, middleware)
- **Rationale**: Application complexity doesn't justify Redux overhead

## Environment-Specific Behavior

### Development
- CORS allows `http://localhost:3000`
- Structured logging with colors
- Test users seeded on startup
- Frontend proxies API to `http://localhost:8000`

### Production
- CORS requires explicit domain configuration
- JSON-structured logging
- JWT secret validation enforced
- Admin user created from environment variables
- Static frontend served from `/frontend/build`

## Related Documentation

- [API Patterns](./API_PATTERNS.md) - FastAPI endpoint structure
- [Database Schema](./DATABASE_SCHEMA.md) - Table/collection details
- [SNMP Patterns](./SNMP_PATTERNS.md) - SNMP implementation details
- [IRP Patterns](./IRP_MESSAGE_PATTERNS.md) - IRP parsing and sending
