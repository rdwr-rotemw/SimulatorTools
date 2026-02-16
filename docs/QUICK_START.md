# Quick Start Guide for Claude Code

**Last updated:** February 8, 2026

## Purpose

This guide helps Claude Code (and developers) quickly understand the Simulator Tools codebase and implement features efficiently. Read this first before making changes.

## For Claude Code: Getting Started

When starting a new conversation or implementing a feature, follow this checklist:

### 1. Review Current State
- [ ] Read [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) - Understand what the project does
- [ ] Read [ARCHITECTURE.md](./ARCHITECTURE.md) - Understand system design and data flow
- [ ] Check [POLLING_CURRENT_STATE.md](../POLLING_CURRENT_STATE.md) if working on polling features

### 2. Understand the Codebase
- [ ] Backend structure: [backend/app/](../backend/app/)
  - Routes (API endpoints): [backend/app/routes/](../backend/app/routes/)
  - Business logic: [backend/app/modules/](../backend/app/modules/)
  - Database models: [backend/app/models/](../backend/app/models/)
- [ ] Frontend structure: [frontend/src/](../frontend/src/)
  - Pages: [frontend/src/pages/](../frontend/src/pages/)
  - Components: [frontend/src/components/](../frontend/src/components/)
  - API services: [frontend/src/api/services/](../frontend/src/api/services/)

### 3. Before Implementing

**For Backend Changes**:
- [ ] Read [API_PATTERNS.md](./API_PATTERNS.md) - Understand endpoint structure
- [ ] Read [CODING_STANDARDS.md](./CODING_STANDARDS.md) - Follow Python conventions
- [ ] Check existing similar endpoints for patterns

**For Database Changes**:
- [ ] Read [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Understand data models
- [ ] Decide: PostgreSQL (structured) or MongoDB (flexible)?

**For SNMP Features**:
- [ ] Read [SNMP_PATTERNS.md](./SNMP_PATTERNS.md) - Understand SNMP implementation

**For IRP Features**:
- [ ] Read [IRP_MESSAGE_PATTERNS.md](./IRP_MESSAGE_PATTERNS.md) - Understand IRP parsing

## Technology Stack Overview

### Backend (Python FastAPI)
- **Framework**: FastAPI with Pydantic for validation
- **ORM**: SQLAlchemy for PostgreSQL
- **MongoDB**: PyMongo for document storage
- **Authentication**: JWT tokens (python-jose)
- **Password Hashing**: Argon2 (argon2-cffi)
- **SSH**: Paramiko for Sapro integration
- **SNMP**: pysnmp for trap sending
- **Async**: asyncio for background tasks

### Frontend (React TypeScript)
- **UI Framework**: Material-UI (MUI)
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Routing**: React Router v6
- **Form Handling**: React Hook Form
- **Drag & Drop**: @dnd-kit (for polling builder)

### Databases
- **PostgreSQL**: Users, roles, simulators, sessions
- **MongoDB**: IRP schemas, device templates, polling configs

## Common Development Workflows

### Adding a New API Endpoint

**Example: Add endpoint to list all active simulators**

**1. Define Response Schema** ([backend/app/schemas/sapro_simulator.py](../backend/app/schemas/sapro_simulator.py)):

```python
class ActiveSimulatorsResponse(BaseModel):
    """Response for listing active simulators."""
    simulators: List[SaproSimulatorResponse]
    count: int
```

**2. Create Endpoint** ([backend/app/routes/sapro.py](../backend/app/routes/sapro.py)):

```python
@router.get("/simulators/active", response_model=ActiveSimulatorsResponse)
def list_active_simulators(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_sapro_access)
) -> ActiveSimulatorsResponse:
    """List all active simulators.

    Returns:
        List of simulators with status='running'
    """
    try:
        simulators = db.query(Simulator).filter(
            Simulator.status == "running"
        ).all()

        return ActiveSimulatorsResponse(
            simulators=[
                SaproSimulatorResponse(
                    ip_address=sim.ip_address,
                    status=sim.status,
                    created_at=sim.created_at.isoformat()
                )
                for sim in simulators
            ],
            count=len(simulators)
        )
    except SQLAlchemyError as e:
        logger.exception("Error listing active simulators")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
```

**3. Add Frontend Service** ([frontend/src/api/services/sapro.service.ts](../frontend/src/api/services/sapro.service.ts)):

```typescript
export const saproService = {
    async listActiveSimulators(): Promise<ActiveSimulatorsResponse> {
        const response = await axios.get('/api/simulators/active');
        return response.data;
    }
};
```

**4. Test**:
- Start backend: `uvicorn backend.app.main:app --reload`
- Visit Swagger: `http://localhost:8000/docs`
- Test endpoint directly in Swagger UI

### Adding a New Database Model

**Example: Add a `SimulatorLog` table for tracking simulator events**

**1. Create Model** ([backend/app/models/simulator_log.py](../backend/app/models/simulator_log.py)):

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.utils.database import Base

class SimulatorLog(Base):
    __tablename__ = "simulator_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulator_ip = Column(String(45), ForeignKey("simulators.ip_address"), nullable=False)
    event_type = Column(String(50), nullable=False)  # e.g., "started", "stopped", "error"
    message = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    simulator = relationship("Simulator", backref="logs")
```

**2. Create Schema** ([backend/app/schemas/sapro_simulator.py](../backend/app/schemas/sapro_simulator.py)):

```python
class SimulatorLogResponse(BaseModel):
    id: int
    simulator_ip: str
    event_type: str
    message: str | None
    created_at: str
```

**3. Auto-create Table**:

Tables are created automatically on startup via:

```python
# In backend/app/main.py
Base.metadata.create_all(bind=engine)
```

**4. Use in Endpoint**:

```python
@router.post("/simulators/{ip}/logs")
def add_simulator_log(
    ip: str,
    event_type: str,
    message: str | None = None,
    db: Session = Depends(get_db)
):
    """Add a log entry for a simulator."""
    log = SimulatorLog(
        simulator_ip=ip,
        event_type=event_type,
        message=message
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"success": True, "log_id": log.id}
```

### Adding a New React Component

**Example: Create a SimulatorStatusBadge component**

**1. Create Component** ([frontend/src/components/Sapro/SimulatorStatusBadge.tsx](../frontend/src/components/Sapro/SimulatorStatusBadge.tsx)):

```typescript
import React from 'react';
import { Chip } from '@mui/material';

interface SimulatorStatusBadgeProps {
    status: string;
}

const STATUS_COLORS: Record<string, "success" | "error" | "warning" | "default"> = {
    running: "success",
    stopped: "error",
    created: "warning",
    error: "error"
};

export const SimulatorStatusBadge: React.FC<SimulatorStatusBadgeProps> = ({ status }) => {
    return (
        <Chip
            label={status.toUpperCase()}
            color={STATUS_COLORS[status] || "default"}
            size="small"
        />
    );
};
```

**2. Use in Page**:

```typescript
import { SimulatorStatusBadge } from '../components/Sapro/SimulatorStatusBadge';

function SimulatorList() {
    return (
        <TableCell>
            <SimulatorStatusBadge status={simulator.status} />
        </TableCell>
    );
}
```

### Adding Background Task with Progress Tracking

**Example: Long-running simulator initialization**

**1. Define Progress Storage**:

```python
# In-memory task tracking (replace with Redis in production)
init_tasks: Dict[str, Dict[str, Any]] = {}
```

**2. Create Background Task**:

```python
async def _initialize_simulator_task(task_id: str, simulator_ip: str):
    """Background task to initialize simulator."""
    try:
        init_tasks[task_id]["status"] = "running"
        init_tasks[task_id]["progress"] = 0

        # Step 1: Create device
        init_tasks[task_id]["current_step"] = "Creating device"
        sapro_client.create_device(simulator_ip)
        init_tasks[task_id]["progress"] = 33

        # Step 2: Load configuration
        init_tasks[task_id]["current_step"] = "Loading configuration"
        sapro_client.load_map(simulator_ip, "default.xmf")
        init_tasks[task_id]["progress"] = 66

        # Step 3: Start simulator
        init_tasks[task_id]["current_step"] = "Starting simulator"
        sapro_client.start_device(simulator_ip)
        init_tasks[task_id]["progress"] = 100

        init_tasks[task_id]["status"] = "completed"
        init_tasks[task_id]["message"] = "Initialization completed"

    except Exception as e:
        init_tasks[task_id]["status"] = "error"
        init_tasks[task_id]["message"] = str(e)
```

**3. Create Endpoint to Start Task**:

```python
@router.post("/simulators/{ip}/initialize")
async def initialize_simulator(
    ip: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Initialize simulator in background."""
    task_id = str(uuid.uuid4())

    init_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "current_step": None
    }

    background_tasks.add_task(_initialize_simulator_task, task_id, ip)

    return {
        "task_id": task_id,
        "progress_url": f"/api/simulators/init-progress?task_id={task_id}"
    }
```

**4. Create SSE Progress Endpoint**:

```python
@router.get("/simulators/init-progress")
async def init_progress(task_id: str):
    """Stream initialization progress via SSE."""
    async def event_generator():
        while True:
            if task_id not in init_tasks:
                yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            task_data = init_tasks[task_id]

            if task_data["status"] == "completed":
                yield f"event: complete\ndata: {json.dumps(task_data)}\n\n"
                break
            elif task_data["status"] == "error":
                yield f"event: error\ndata: {json.dumps(task_data)}\n\n"
                break

            yield f"event: progress\ndata: {json.dumps(task_data)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )
```

## Current Focus Areas (February 2026)

### 1. SNMP Trap System
- **Status**: Implemented, testing pause/resume
- **Location**: [backend/app/modules/reporter/snmp/](../backend/app/modules/reporter/snmp/)
- **Next Steps**: Add resume functionality, improve error handling

### 2. IRP Message Parsing
- **Status**: XML→JSON conversion complete
- **Location**: [backend/app/modules/reporter/irp/](../backend/app/modules/reporter/irp/)
- **Next Steps**: Implement binary message generation, UDP sending

### 3. Polling Endpoint Builder
- **Status**: Multi-endpoint support in progress
- **Location**: [backend/app/modules/reporter/polling/](../backend/app/modules/reporter/polling/)
- **Next Steps**: Template management, TCL optimization

### 4. User Management
- **Status**: Basic RBAC implemented
- **Location**: [backend/app/routes/user.py](../backend/app/routes/user.py)
- **Next Steps**: Fine-grained permissions, workspace isolation

## Common Patterns to Follow

### Error Handling
- Always catch specific exceptions (IntegrityError, SQLAlchemyError)
- Log errors with `logger.exception()`
- Return appropriate HTTP status codes
- Don't leak sensitive info in error messages

### Database Operations
- Use `Depends(get_db)` for session injection
- Always commit explicitly: `db.commit()`
- Rollback on errors: `db.rollback()`
- Refresh after insert: `db.refresh(obj)`

### Authentication
- Use `Depends(require_auth)` for authenticated endpoints
- Use `Depends(require_admin)` for admin-only endpoints
- Use `Depends(require_sapro_access)` for Sapro features

### Type Hints
- All functions must have type hints
- Use Pydantic models for request/response
- Use `Optional[T]` for nullable values
- Use `List[T]`, `Dict[K, V]` for collections

## Testing Checklist

Before committing code:

- [ ] Run backend: `uvicorn backend.app.main:app --reload`
- [ ] Test in Swagger UI: `http://localhost:8000/docs`
- [ ] Run frontend: `npm start`
- [ ] Test in browser: `http://localhost:3000`
- [ ] Check console for errors (frontend and backend)
- [ ] Verify database changes (if applicable)
- [ ] Test with different user roles (admin, sapro_user, etc.)

## Key Files to Know

### Backend

| File | Purpose |
|------|---------|
| [backend/app/main.py](../backend/app/main.py) | FastAPI app initialization, CORS, router registration |
| [backend/app/utils/config.py](../backend/app/utils/config.py) | Environment variables, settings |
| [backend/app/utils/database.py](../backend/app/utils/database.py) | Database connections (PostgreSQL, MongoDB) |
| [backend/app/utils/auth.py](../backend/app/utils/auth.py) | JWT authentication, password hashing |
| [backend/app/routes/sapro.py](../backend/app/routes/sapro.py) | Simulator management endpoints |
| [backend/app/routes/reporter.py](../backend/app/routes/reporter.py) | SNMP/IRP/Polling endpoints |
| [backend/app/modules/sapro/sapro_client.py](../backend/app/modules/sapro/sapro_client.py) | Sapro TCP protocol client |

### Frontend

| File | Purpose |
|------|---------|
| [frontend/src/App.tsx](../frontend/src/App.tsx) | Main app component, routing |
| [frontend/src/pages/PollingPage.tsx](../frontend/src/pages/PollingPage.tsx) | Polling configuration UI |
| [frontend/src/api/services/polling.service.ts](../frontend/src/api/services/polling.service.ts) | Polling API service |
| [frontend/src/types/polling.ts](../frontend/src/types/polling.ts) | TypeScript type definitions |
| [frontend/src/store/](../frontend/src/store/) | Zustand state management |

## Resources

### API Documentation
- **Swagger UI**: `http://localhost:8000/docs` (interactive testing)
- **ReDoc**: `http://localhost:8000/redoc` (clean documentation)

### Database Tools
- **PostgreSQL**: pgAdmin, DBeaver
- **MongoDB**: MongoDB Compass, Studio 3T

### Development Tools
- **VS Code Extensions**:
  - Python (ms-python.python)
  - Pylance (ms-python.vscode-pylance)
  - ESLint (dbaeumer.vscode-eslint)
  - TypeScript (ms-vscode.vscode-typescript-next)
- **Claude Code**: For AI-assisted development

## Getting Help

### Documentation Files
1. [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) - What the project does
2. [ARCHITECTURE.md](./ARCHITECTURE.md) - How it's structured
3. [API_PATTERNS.md](./API_PATTERNS.md) - How to build endpoints
4. [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Data models
5. [CODING_STANDARDS.md](./CODING_STANDARDS.md) - Code conventions
6. [SNMP_PATTERNS.md](./SNMP_PATTERNS.md) - SNMP implementation
7. [IRP_MESSAGE_PATTERNS.md](./IRP_MESSAGE_PATTERNS.md) - IRP parsing
8. [SETUP.md](./SETUP.md) - Environment setup
9. **This file** - Quick workflows and patterns

### When Starting a New Feature

1. **Research Phase**:
   - Read relevant documentation files above
   - Search codebase for similar features (`grep`, `Glob` tools)
   - Check existing endpoints/components for patterns

2. **Planning Phase**:
   - Identify which files need changes (routes, models, schemas)
   - Determine if new database tables/collections needed
   - Plan frontend components if UI changes required

3. **Implementation Phase**:
   - Follow coding standards
   - Add type hints and docstrings
   - Handle errors properly
   - Log important events

4. **Testing Phase**:
   - Test in Swagger UI (backend)
   - Test in browser (frontend)
   - Verify database changes
   - Check error handling

## Final Notes

- **Read before writing**: Always check if similar code exists
- **Follow patterns**: Consistency is more important than cleverness
- **Document as you go**: Update docstrings and comments
- **Test thoroughly**: Use Swagger UI and browser testing
- **Ask questions**: Reference these docs or ask for clarification

Good luck building features for Simulator Tools!
