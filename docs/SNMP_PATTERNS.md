# SNMP Patterns

**Last updated:** February 8, 2026

## Overview

The SNMP trap system sends test SNMP traps to DefensePro simulators via the Sapro infrastructure. This is used for testing attack detection, reporting, and CyberController integration.

## Architecture

```
┌─────────────┐
│  Frontend   │ POST /api/reporter/send-snmp-traps
│  (SNMPPage) │ ──────────────────┐
└─────────────┘                   │
                                  ▼
┌──────────────────────────────────────────────────┐
│ Backend (reporter.py)                            │
│                                                  │
│ 1. Validate payload                              │
│ 2. Query simulators from PostgreSQL              │
│ 3. Start background task (asyncio)              │
│ 4. Stream progress via SSE                       │
└────────────┬─────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│ Background Task (_send_snmp_traps_task)          │
│                                                  │
│ For each trap in sequence:                       │
│   ├─▶ Build SNMP command (attack_traps.py)      │
│   ├─▶ SSH to Sapro host (executor.py)           │
│   ├─▶ Execute sapcnsl command                    │
│   ├─▶ Update progress dict (SSE)                │
│   └─▶ Pause if configured (trap.pause)          │
└──────────────────────────────────────────────────┘
```

## SNMP Trap Sending Implementation

### Endpoint: Send SNMP Traps

**File**: [backend/app/routes/reporter.py:268-374](../backend/app/routes/reporter.py)

```python
@router.post("/reporter/send-snmp-traps")
async def send_snmp_traps(
    payload: ReporterSNMPPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_sapro_access)
):
    """Send SNMP traps to simulators with progress tracking.

    Request payload:
        {
            "map": "attack_map.xmf",  # or {"192.168.1.10": "map1.xmf", ...}
            "traps": [
                {
                    "attackCategory": "DDoS",
                    "attackName": "SYN Flood",
                    "policy": "DefaultPolicy",
                    "status": "Active",
                    "pause": 5  # Pause 5 seconds after this trap
                }
            ]
        }
    """
    # Parse map configuration (single map or per-simulator)
    if isinstance(payload.map, str):
        # Single map for all simulators
        simulator_map_dict = {sim.ip_address: payload.map for sim in simulators}
    else:
        # Per-simulator map configuration
        simulator_map_dict = payload.map

    # Query simulators from database
    simulators = db.query(Simulator).filter(
        Simulator.ip_address.in_(simulator_map_dict.keys())
    ).all()

    if not simulators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching simulators found"
        )

    # Create unique task ID for progress tracking
    task_id = str(uuid.uuid4())

    # Initialize progress tracking
    snmp_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": len(payload.traps) * len(simulators),
        "current_trap": None,
        "errors": []
    }

    # Start background task
    background_tasks.add_task(
        _send_snmp_traps_task,
        task_id,
        simulators,
        payload.traps,
        simulator_map_dict
    )

    return {
        "task_id": task_id,
        "message": f"Sending {len(payload.traps)} traps to {len(simulators)} simulators",
        "progress_url": f"/api/reporter/snmp-progress?task_id={task_id}"
    }
```

### Background Task Implementation

**File**: [backend/app/routes/reporter.py:376-450](../backend/app/routes/reporter.py)

```python
async def _send_snmp_traps_task(
    task_id: str,
    simulators: List[Simulator],
    traps: List[TrapConfig],
    simulator_map_dict: Dict[str, str]
):
    """Background task to send SNMP traps sequentially with pause support.

    Key features:
    - Sequential trap sending (respects order)
    - Per-trap pause configuration
    - Real-time progress updates
    - Error collection (continues on failure)
    """
    try:
        total_traps = len(traps)
        progress = 0

        for trap_idx, trap in enumerate(traps, start=1):
            # Update progress: current trap
            snmp_tasks[task_id]["current_trap"] = f"{trap.attackName} ({trap_idx}/{total_traps})"

            for sim in simulators:
                simulator_ip = sim.ip_address
                map_name = simulator_map_dict.get(simulator_ip)

                if not map_name:
                    logger.warning(f"No map configured for {simulator_ip}, skipping")
                    continue

                try:
                    # Build SNMP command
                    from backend.app.modules.reporter.snmp.attack_traps import build_snmp_command

                    command = build_snmp_command(
                        simulator_ip=simulator_ip,
                        map_name=map_name,
                        trap=trap
                    )

                    logger.info(f"Sending trap {trap_idx}/{total_traps} to {simulator_ip}: {trap.attackName}")

                    # Execute via SSH
                    from backend.app.modules.reporter.snmp.executor import execute_sapro_command

                    success, output = execute_sapro_command(command, timeout=30)

                    if not success:
                        error_msg = f"{simulator_ip}: {output}"
                        snmp_tasks[task_id]["errors"].append(error_msg)
                        logger.error(f"SNMP trap failed for {simulator_ip}: {output}")

                except Exception as e:
                    error_msg = f"{simulator_ip}: {str(e)}"
                    snmp_tasks[task_id]["errors"].append(error_msg)
                    logger.exception(f"Error sending trap to {simulator_ip}")

                # Update progress
                progress += 1
                snmp_tasks[task_id]["progress"] = progress

            # Pause after trap if configured (max 60 seconds)
            if trap.pause and trap.pause > 0:
                pause_seconds = min(trap.pause, 60)
                logger.info(f"Pausing {pause_seconds}s after trap: {trap.attackName}")
                await asyncio.sleep(pause_seconds)

        # Mark as completed
        snmp_tasks[task_id]["status"] = "completed"
        snmp_tasks[task_id]["message"] = f"Sent {total_traps} traps successfully"

    except Exception as e:
        logger.exception(f"SNMP task {task_id} failed")
        snmp_tasks[task_id]["status"] = "error"
        snmp_tasks[task_id]["message"] = str(e)
```

## SNMP Command Building

### Trap Configuration Schema

**File**: [backend/app/schemas/reporter.py:16-45](../backend/app/schemas/reporter.py)

```python
class TrapConfig(BaseModel):
    """SNMP trap configuration."""
    # Required fields
    attackCategory: str    # e.g., "DDoS", "Network", "Application"
    attackName: str        # e.g., "SYN Flood", "HTTP GET Flood"
    policy: str            # Policy name (e.g., "DefaultPolicy")
    status: str            # "Active", "Inactive", "Terminated"

    # Optional fields (defaults in attack_traps.py)
    attackId: str | None = None
    radwareId: str | None = None
    protocol: str | None = None
    srcIp: str | None = None
    srcPort: str | None = None
    dstIp: str | None = None
    dstPort: str | None = None
    physicalPort: str | None = None
    packetCount: str | None = None
    packetBandwidth: str | None = None
    samples: str | None = None
    risk: str | None = None
    action: str | None = None
    direction: str | None = None

    # Pause after sending this trap (0-60 seconds)
    pause: int | None = Field(None, ge=0, le=60)
```

### Command Builder

**File**: [backend/app/modules/reporter/snmp/attack_traps.py](../backend/app/modules/reporter/snmp/attack_traps.py)

```python
def build_snmp_command(
    simulator_ip: str,
    map_name: str,
    trap: TrapConfig
) -> str:
    """Build sapcnsl SNMP trap command.

    Command format:
        sapcnsl -ip <simulator_ip> -map <map_name> \\
                -send_snmp_trap_msg <field1>=<value1>,<field2>=<value2>,...

    Example output:
        sapcnsl -ip 192.168.1.10 -map attack_map.xmf \\
                -send_snmp_trap_msg attackCategory=DDoS,attackName=SYN Flood,...
    """
    # Apply defaults for optional fields
    trap_data = {
        "attackCategory": trap.attackCategory,
        "attackName": trap.attackName,
        "policy": trap.policy,
        "status": trap.status,
        "attackId": trap.attackId or "0",
        "radwareId": trap.radwareId or "0",
        "protocol": trap.protocol or "TCP",
        "srcIp": trap.srcIp or "0.0.0.0",
        "srcPort": trap.srcPort or "0",
        "dstIp": trap.dstIp or "0.0.0.0",
        "dstPort": trap.dstPort or "0",
        "physicalPort": trap.physicalPort or "0",
        "packetCount": trap.packetCount or "0",
        "packetBandwidth": trap.packetBandwidth or "0",
        "samples": trap.samples or "0",
        "risk": trap.risk or "Low",
        "action": trap.action or "Drop",
        "direction": trap.direction or "Inbound"
    }

    # Build key=value pairs
    trap_params = ",".join([f"{k}={v}" for k, v in trap_data.items()])

    # Construct sapcnsl command
    command = (
        f'sapcnsl -ip {simulator_ip} -map {map_name} '
        f'-send_snmp_trap_msg {trap_params}'
    )

    return command
```

**Example Generated Command**:
```bash
sapcnsl -ip 192.168.1.10 -map attack_map.xmf \
        -send_snmp_trap_msg attackCategory=DDoS,attackName=SYN Flood,policy=DefaultPolicy,status=Active,attackId=0,radwareId=0,protocol=TCP,srcIp=192.168.50.1,srcPort=12345,dstIp=192.168.60.1,dstPort=80,physicalPort=0,packetCount=1000,packetBandwidth=500,samples=10,risk=High,action=Drop,direction=Inbound
```

## SSH Execution

### Executor Implementation

**File**: [backend/app/modules/reporter/snmp/executor.py](../backend/app/modules/reporter/snmp/executor.py)

```python
def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """Execute Sapro command via SSH.

    In production (network_mode: host):
    - Backend binds simulator IPs for UDP IRP messages
    - Executes Sapro CLI commands via SSH to localhost

    In development:
    - SSH to remote Sapro host (configured via SAPRO_SSH_HOST)

    Args:
        command: sapcnsl command to execute
        timeout: Execution timeout in seconds

    Returns:
        Tuple of (success: bool, output: str)

    Example:
        >>> success, output = execute_sapro_command(
        ...     "sapcnsl -ip 192.168.1.10 -get_version",
        ...     timeout=10
        ... )
        >>> if success:
        ...     print(f"Version: {output}")
    """
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    ssh_client = get_sapro_ssh_client()

    try:
        logger.info(f"Executing: {command[:100]}")

        # Use centralized SSH client with connection pooling
        success, output = ssh_client.execute_command(
            command,
            timeout=timeout,
            check_stderr=False
        )

        if success:
            logger.info(f"Command succeeded: {len(output)} chars output")
        else:
            logger.warning(f"Command failed: {output[:200]}")

        return success, output

    except Exception as e:
        logger.exception("SSH execution error")
        return False, str(e)
```

## Pause/Resume Mechanism

### How Pause Works

The `pause` field in TrapConfig specifies how many seconds to wait after sending a trap before proceeding to the next trap.

**Use Cases**:
1. **Rate limiting**: Prevent overwhelming the target system
2. **Attack simulation**: Simulate realistic attack timing
3. **Observation**: Allow time to observe trap effects before next trap

**Implementation**:
```python
# In background task loop (see above)
if trap.pause and trap.pause > 0:
    pause_seconds = min(trap.pause, 60)  # Max 60 seconds
    logger.info(f"Pausing {pause_seconds}s after trap: {trap.attackName}")
    await asyncio.sleep(pause_seconds)  # Non-blocking async sleep
```

**Constraints**:
- Minimum: 0 seconds (no pause)
- Maximum: 60 seconds (enforced by Pydantic validation)
- Applied per trap (not per simulator)

### Resume Functionality

**Current State**: Not yet implemented

**Planned Design**:
- Store task state in database (not in-memory dict)
- Add `resume_task` endpoint
- Track last completed trap index
- Skip already-sent traps on resume

## Progress Tracking (Server-Sent Events)

### SSE Endpoint

**File**: [backend/app/routes/reporter.py:452-490](../backend/app/routes/reporter.py)

```python
@router.get("/reporter/snmp-progress")
async def snmp_progress(task_id: str):
    """Stream SNMP trap sending progress via SSE.

    SSE Events:
    - progress: Regular updates (every 500ms)
    - complete: Task finished successfully
    - error: Task failed

    Example SSE stream:
        event: progress
        data: {"status": "running", "progress": 5, "total": 20, "current_trap": "SYN Flood (3/10)"}

        event: progress
        data: {"status": "running", "progress": 10, "total": 20, "current_trap": "HTTP Flood (5/10)"}

        event: complete
        data: {"status": "completed", "message": "Sent 10 traps successfully"}
    """
    async def event_generator():
        while True:
            # Check if task exists
            if task_id not in snmp_tasks:
                yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            task_data = snmp_tasks[task_id]

            # Terminal states
            if task_data["status"] == "completed":
                yield f"event: complete\ndata: {json.dumps(task_data)}\n\n"
                break
            elif task_data["status"] == "error":
                yield f"event: error\ndata: {json.dumps(task_data)}\n\n"
                break

            # Progress update
            yield f"event: progress\ndata: {json.dumps(task_data)}\n\n"

            # Poll every 500ms
            await asyncio.sleep(0.5)

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

### Frontend SSE Consumption

**Example Pattern** (React):
```typescript
const eventSource = new EventSource(`/api/reporter/snmp-progress?task_id=${taskId}`);

eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    setProgress(data.progress);
    setTotal(data.total);
    setCurrentTrap(data.current_trap);
});

eventSource.addEventListener('complete', (event) => {
    const data = JSON.parse(event.data);
    console.log('Completed:', data.message);
    eventSource.close();
});

eventSource.addEventListener('error', (event) => {
    const data = JSON.parse(event.data);
    console.error('Error:', data.error);
    eventSource.close();
});
```

## Edge Cases and Solutions

### 1. Simulator Not Found
**Problem**: Map configured for simulator IP that doesn't exist in database

**Solution**: Skip simulator with warning, continue with others
```python
if not map_name:
    logger.warning(f"No map configured for {simulator_ip}, skipping")
    continue
```

### 2. SSH Timeout
**Problem**: `sapcnsl` command hangs or takes too long

**Solution**: Configurable timeout (default 30s), collect error and continue
```python
success, output = execute_sapro_command(command, timeout=30)
if not success:
    snmp_tasks[task_id]["errors"].append(f"{simulator_ip}: timeout")
```

### 3. Invalid Trap Parameters
**Problem**: User provides invalid attack category or missing required fields

**Solution**: Pydantic validation catches this at API boundary
```python
# In ReporterSNMPPayload model
traps: List[TrapConfig]  # Validates each trap on request
```

### 4. Task State Cleanup
**Problem**: In-memory `snmp_tasks` dict grows indefinitely

**Solution**: Implement TTL-based cleanup (planned)
```python
# Planned: Periodic cleanup of old tasks
async def cleanup_old_tasks():
    cutoff = datetime.now() - timedelta(hours=1)
    for task_id, task_data in list(snmp_tasks.items()):
        if task_data.get("completed_at", datetime.now()) < cutoff:
            del snmp_tasks[task_id]
```

## Related Documentation

- [API Patterns](./API_PATTERNS.md) - SSE implementation details
- [Architecture](./ARCHITECTURE.md) - SNMP flow in system architecture
- [Coding Standards](./CODING_STANDARDS.md) - Error handling patterns
