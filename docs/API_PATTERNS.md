# API Patterns

**Last updated:** February 8, 2026

## FastAPI Endpoint Structure

All API endpoints follow consistent patterns for request/response handling, error handling, and authentication.

## Real Endpoint Examples

### Example 1: Simple GET with Authentication

**File**: [backend/app/routes/sapro.py:1163-1189](../backend/app/routes/sapro.py)

```python
@router.get("/simulators", response_model=List[SaproSimulatorResponse])
def list_simulators(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_sapro_access)
) -> List[SaproSimulatorResponse]:
    """List all simulators with role-based filtering.

    - Admin users see all simulators
    - Non-admin users only see CC simulators (is_cc_device=True)
    """
    try:
        if current_user.has_role("admin"):
            simulators = db.query(Simulator).all()
        else:
            simulators = db.query(Simulator).filter(
                Simulator.is_cc_device == True
            ).all()

        return [
            SaproSimulatorResponse(
                id=sim.id,
                ip_address=sim.ip_address,
                status=sim.status,
                created_at=sim.created_at.isoformat(),
                is_cc_device=sim.is_cc_device or False
            )
            for sim in simulators
        ]
    except SQLAlchemyError as e:
        logger.exception("Database error listing simulators")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
```

**Key Patterns**:
- Dependency injection for DB session (`Depends(get_db)`)
- Authentication dependency (`Depends(require_sapro_access)`)
- Role-based filtering in query logic
- SQLAlchemy error handling with HTTP 500 response
- Response model validation (`response_model=List[SaproSimulatorResponse]`)

### Example 2: POST with Request Validation

**File**: [backend/app/routes/user.py:78-118](../backend/app/routes/user.py)

```python
@router.post("/api/auth/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """Authenticate user and return JWT token.

    Request body:
        {
            "username": "admin",
            "password": "SecurePass123"
        }

    Response:
        {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": "admin",
                "roles": ["admin"]
            }
        }
    """
    # Query user by username
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Verify password (Argon2 or bcrypt)
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Generate JWT token
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )

    # Load user roles
    roles = [ur.role.name for ur in user.user_roles]

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            roles=roles
        )
    )
```

**Key Patterns**:
- Pydantic request model (`LoginRequest`) automatically validates JSON body
- Consistent error messages (don't leak user existence)
- HTTP 401 for authentication failures
- JWT token generation via utility function
- Pydantic response model ensures type safety

### Example 3: Streaming Response (Server-Sent Events)

**File**: [backend/app/routes/reporter.py:268-310](../backend/app/routes/reporter.py)

```python
@router.post("/reporter/send-snmp-traps")
async def send_snmp_traps(
    payload: ReporterSNMPPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_sapro_access)
):
    """Send SNMP traps with progress tracking via SSE.

    Request:
        {
            "map": "attack_map.xmf",
            "traps": [
                {
                    "attackCategory": "DDoS",
                    "attackName": "SYN Flood",
                    "policy": "DefaultPolicy",
                    "status": "Active",
                    "pause": 5
                }
            ]
        }

    Response: Initiates background task, use GET /reporter/snmp-progress for SSE stream
    """
    # Validate map exists and get simulator IPs
    simulators = db.query(Simulator).filter(Simulator.status == "running").all()

    if not simulators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No running simulators found"
        )

    # Start background SNMP sending task
    task_id = str(uuid.uuid4())
    snmp_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": len(payload.traps),
        "current_trap": None
    }

    background_tasks.add_task(
        _send_snmp_traps_task,
        task_id,
        simulators,
        payload.traps
    )

    return {"task_id": task_id, "message": "SNMP trap sending started"}


@router.get("/reporter/snmp-progress")
async def snmp_progress(task_id: str):
    """Stream SNMP trap sending progress via Server-Sent Events.

    SSE format:
        event: progress
        data: {"status": "running", "progress": 3, "total": 10, "current_trap": "..."}

        event: complete
        data: {"status": "completed", "message": "All traps sent successfully"}
    """
    async def event_generator():
        while True:
            if task_id not in snmp_tasks:
                yield f"event: error\\ndata: {json.dumps({'error': 'Task not found'})}\\n\\n"
                break

            task_data = snmp_tasks[task_id]

            if task_data["status"] == "completed":
                yield f"event: complete\\ndata: {json.dumps(task_data)}\\n\\n"
                break
            elif task_data["status"] == "error":
                yield f"event: error\\ndata: {json.dumps(task_data)}\\n\\n"
                break
            else:
                yield f"event: progress\\ndata: {json.dumps(task_data)}\\n\\n"

            await asyncio.sleep(0.5)  # Poll every 500ms

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

**Key Patterns**:
- Background tasks for long-running operations (`BackgroundTasks`)
- Task tracking with UUIDs in shared dict
- SSE streaming with `StreamingResponse`
- Event-based updates (progress, complete, error)
- Async generator for real-time updates

## Standard Request/Response Structure

### Request Bodies (Pydantic Models)

All POST/PUT requests use Pydantic models for validation:

**File**: [backend/app/schemas/reporter.py:16-45](../backend/app/schemas/reporter.py)

```python
class TrapConfig(BaseModel):
    """Single SNMP trap configuration."""
    # Required fields
    attackCategory: str
    attackName: str
    policy: str
    status: str

    # Optional fields (defaults handled by attack_traps.py)
    attackId: str | None = None
    srcIp: str | None = None
    dstIp: str | None = None
    pause: int | None = Field(None, ge=0, le=60, description="Pause in seconds")


class ReporterSNMPPayload(BaseModel):
    """SNMP trap configuration payload."""
    map: Union[str, Dict[str, str]]  # Support single map or per-simulator maps
    traps: List[TrapConfig]
```

**Validation Features**:
- Type checking (str, int, List, Dict, Union types)
- Field constraints (`ge=0, le=60` for pause field)
- Optional vs. required fields
- Nested models (List[TrapConfig])
- Union types for flexibility (str | Dict)

### Response Bodies

Consistent response structure across endpoints:

**Success Response**:
```python
{
    "success": true,
    "message": "Operation completed successfully",
    "data": {...}  # Optional payload
}
```

**Error Response** (HTTPException):
```python
{
    "detail": "Specific error message explaining what went wrong"
}
```

**Batch Operation Response**:
```python
{
    "success": true,
    "message": "Batch operation completed",
    "results": [
        {"ip": "192.168.1.10", "success": true, "message": "Created"},
        {"ip": "192.168.1.11", "success": false, "message": "Already exists"}
    ]
}
```

## Error Handling Patterns

### HTTP Status Codes

- **200 OK**: Successful GET/POST/PUT
- **201 Created**: Resource created successfully
- **400 Bad Request**: Validation error (Pydantic)
- **401 Unauthorized**: Missing/invalid authentication token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Resource already exists (e.g., duplicate simulator IP)
- **500 Internal Server Error**: Unexpected server error

### Exception Handling Pattern

**Consistent try-except blocks**:

```python
try:
    # Database operation
    result = db.query(Model).filter(...).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )

    # Business logic
    return process_result(result)

except IntegrityError as e:
    logger.exception("Database integrity error")
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Resource already exists"
    )
except SQLAlchemyError as e:
    logger.exception("Database error")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Database error: {str(e)}"
    )
except Exception as e:
    logger.exception("Unexpected error")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )
```

**Error Logging**:
- Use `logger.exception()` for automatic traceback capture
- Always log before raising HTTPException
- Include context in log messages (operation, user, resource ID)

## Authentication & Authorization

### JWT Token Flow

**Token Structure**:
```python
# Payload
{
    "sub": "admin",           # Subject (username)
    "user_id": 1,             # User ID for quick lookup
    "exp": 1706825600         # Expiration (Unix timestamp)
}

# Header
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Authentication Dependencies

**File**: [backend/app/utils/auth.py](../backend/app/utils/auth.py)

```python
def require_auth(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Validate JWT token and return current user."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(User).filter(User.username == username).first()

        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_admin(current_user: User = Depends(require_auth)) -> User:
    """Require admin role."""
    if not current_user.has_role("admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_sapro_access(current_user: User = Depends(require_auth)) -> User:
    """Require sapro_user or admin role."""
    if not (current_user.has_role("admin") or current_user.has_role("sapro_user")):
        raise HTTPException(status_code=403, detail="Sapro access required")
    return current_user
```

**Usage in Routes**:
```python
@router.get("/admin/users")
def list_users(
    current_user: User = Depends(require_admin),  # Only admins
    db: Session = Depends(get_db)
):
    return db.query(User).all()
```

## FastAPI Dependencies Pattern

### Database Session Injection

```python
def get_db() -> Generator[Session, None, None]:
    """Provide database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Usage
@router.get("/simulators")
def list_simulators(db: Session = Depends(get_db)):
    return db.query(Simulator).all()
```

### MongoDB Injection

```python
from backend.app.utils.database import get_mongo_db

@router.get("/irp-formats")
def list_irp_formats(mongo_db = Depends(get_mongo_db)):
    collection = mongo_db.irp_data_formats
    return list(collection.find({}, {"_id": 0}))
```

### Dependency Chain

```python
# Chain dependencies for complex auth logic
def get_current_active_admin(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)  # Available if needed
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

## Router Organization

### Router Definition Pattern

**File**: [backend/app/routes/sapro.py:47](../backend/app/routes/sapro.py)

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["sapro"])

# Then define endpoints
@router.get("/simulators")
def list_simulators():
    pass

@router.post("/simulators")
def create_simulator():
    pass
```

### Registration in main.py

**File**: [backend/app/main.py:252-261](../backend/app/main.py)

```python
from backend.app.routes.sapro import router as sapro_router
from backend.app.routes.reporter import router as reporter_router
from backend.app.routes.user import router as user_router

app.include_router(sapro_router)
app.include_router(reporter_router)
app.include_router(user_router, prefix="", tags=["users"])
```

## API Documentation

FastAPI automatically generates OpenAPI/Swagger docs at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Docstring Best Practices

```python
@router.post("/simulators", response_model=SaproSimulatorResponse, status_code=201)
def create_simulator(
    payload: SaproSimulatorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> SaproSimulatorResponse:
    """Create a new DefensePro simulator.

    Requires admin role.

    Request body example:
        {
            "ip_address": "192.168.1.10",
            "is_cc_device": false
        }

    Returns:
        201: Simulator created successfully
        409: IP address already exists
        401: Unauthorized
        403: Forbidden (requires admin)

    Raises:
        HTTPException: On validation or database errors
    """
```

## Related Documentation

- [Architecture](./ARCHITECTURE.md) - System design and data flow
- [Coding Standards](./CODING_STANDARDS.md) - Python conventions
- [Database Schema](./DATABASE_SCHEMA.md) - Data models
