# Throughput Optimization — SNMP Traps & IRP Messages

Date: 2026-03-08

## Overview

Benchmarked and optimized the throughput of both SNMP trap sending (via SSH/Sapro)
and IRP message sending (via UDP) across 48 simulators (50.40.30.2–49) with 15-second
measurement windows.

---

## SNMP Trap Optimization

### Architecture

SNMP traps are sent via SSH to the Sapro server, which executes TCL scripts through
`sapcnsl`. Each TCL script can contain up to 10 traps (`_MAX_TRAPS_PER_BATCH = 10`).

**Path:** Backend → SSH → Sapro (`sapcnsl`) → TCL script → SNMP trap out

### Bottleneck Identified: SSH Singleton

The original code used a single SSH connection (`SaproSSHClient`) with an `RLock`,
serializing all 48 simulators through one connection. Each batch required 3 SSH
round-trips: write TCL file, execute `sapcnsl`, cleanup.

### Optimizations Applied

#### 1. SSH Connection Pool (8 → 24 connections)

**File:** `backend/app/utils/sapro_ssh.py`

Replaced the singleton SSH client with a round-robin pool of connections.

```python
_SSH_POOL_SIZE = 24
_sapro_ssh_pool: Optional[List[SaproSSHClient]] = None
_pool_index = 0
_pool_lock = threading.Lock()
```

Connections are staggered during initialization (0.1s delay) to avoid OpenSSH
`MaxStartups` rejection.

#### 2. Combined SSH Command (3 round-trips → 1)

**File:** `backend/app/modules/reporter/snmp/attack_traps.py`

Combined the write + execute + cleanup into a single SSH command:

```python
combined_command = (
    f"cat > {temp_tcl_path} << 'SAPRO_BATCH_EOF'\n"
    f"{tcl_content}"
    f"SAPRO_BATCH_EOF\n"
    f"/opt/sapro/bin/sapcnsl -m {device_map} -c tcl -d {device_ip} -f {temp_tcl_path}; "
    f"rm -f {temp_tcl_path}"
)
```

#### 3. Sapro sshd MaxStartups

The Sapro server uses SimpleSoft's modified sshd which reads config from
`/usr/local/etc/sshd_config` (NOT `/etc/ssh/sshd_config`).

Changed `MaxStartups` from `10:30:100` to `50:30:100` to allow more concurrent
unauthenticated SSH connections during pool initialization.

### Benchmark Results (10 traps/batch, 48 simulators, 15 seconds)

| Pool Size | Traps/15s | Traps/sec | Gain vs prev |
|-----------|-----------|-----------|--------------|
| 1 (old)   | 770       | 51        | baseline     |
| 8         | 11,840    | 756       | +15x (combined cmd) |
| 16        | 21,960    | 1,430     | +89%         |
| 24        | 29,800    | 1,942     | +36%         |
| 32        | 34,700    | 2,261     | +16%         |
| 48        | 35,270    | 2,297     | +2%          |

Diminishing returns after 24. The wall at ~2,300 traps/sec is Sapro's `sapcnsl`
processing limit.

### System Capacity Limit

Set **24,000 traps per 15 seconds** as the system-wide limit (20% headroom below
the ~30k measured throughput for manual sends and automation).

**UI max traps:** Changed from 1000 to **500** per user (`MAX_SNMP_TRAPS`).

### Capacity Check on Loop Start

**Files:**
- `backend/app/routes/reporter.py` — `start_snmp_loop` endpoint
- `frontend/src/pages/SNMPPage.tsx` — capacity warning dialog
- `frontend/src/api/services/snmpLoop.service.ts` — `CapacityInfo` types

When a user starts an SNMP loop, the backend:

1. Queries all active loops from MongoDB (`snmp_loops` collection, `is_active: True`)
2. Calculates each loop's throughput: `traps x simulators x ceil(15 / loop_delay)`
3. If adding the new loop exceeds 24,000:
   - Returns HTTP 409 with capacity details
   - Shows which users have active loops and when they finish
   - Calculates max traps the user can configure for their interval/simulators
   - User can confirm with reduced trap count or cancel

Formula:
```
traps_per_15s = num_traps × num_simulators × ceil(15 / loop_delay)
max_traps = available ÷ (num_simulators × ceil(15 / loop_delay))
```

### Benchmark Script

**File:** `backend/test_snmp_benchmark.py`

```bash
python -m backend.test_snmp_benchmark \
    --cc-ip 10.26.52.175 \
    --simulators "50.40.30.2-49" \
    --map /opt/sapro/projects/cc_scale/map/scale_dp.map \
    --duration 15 \
    --ssh-host localhost \
    --traps-per-batch 10 \
    --ssh-pool-size 24 \
    --strategies C,D
```

Strategies: A (serial), B (concurrent/single SSH), C (SSH pool), D (pool + combined cmd)

---

## IRP Message Optimization

### Architecture

IRP messages are sent as direct UDP packets from the backend container to port 2088
on the destination. No SSH, no Sapro — just binary UDP.

**Path:** Backend → UDP socket (bind to simulator IP) → port 2088 on destination

### Bottlenecks Identified

1. **0.1s sleep between messages** — Artificial delay limiting to ~9 msgs/sec/simulator
2. **Message rebuilding per simulator** — Binary payload built from schema for every
   simulator, even though it's identical. Schema parsing takes ~62ms per message.
3. **Per-message DB writes** — MongoDB updated after every single message send.

### Optimizations Applied

#### 1. Pre-build Binary Payloads (build once, send to all simulators)

**File:** `backend/app/modules/reporter/irp/irp_module.py`

Added `build_irp_payloads()` — builds binary message data once from the schema:

```python
def build_irp_payloads(schema_obj, messages):
    formatter = IrpFormatter(schema_obj.schema, "0.0.0.0", "0.0.0.0")
    payloads = []
    for message in messages:
        name = message["message"]
        cleaned = {k: v for k, v in message.items() if k not in ("message", "pause")}
        message_id = formatter.message_resolver.resolve_message_identifier(name)
        binary_data = formatter.message_builder.build_message(message_id, cleaned)
        payloads.append((name, int(message_id), binary_data))
    return payloads
```

Added `send_irp_udp()` — sends pre-built payload with fresh timestamp:

```python
def send_irp_udp(from_ip, to_ip, message_id, binary_body):
    data_header = struct.pack('<BBIBBIB', 0x91, 4, int(time.time()), 2, 1, 100600, message_id)
    data = data_header + binary_body
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((from_ip, 0))
    sock.sendto(data, (to_ip, 2088))
    sock.close()
```

#### 2. Removed 0.1s Sleep

**File:** `backend/app/modules/reporter/irp/irp_loop_manager.py`

Removed `await asyncio.sleep(0.1)` between messages in `_send_batch`.

#### 3. Batch DB Update

Replaced per-message MongoDB writes with a single `$inc` update per batch.

### Benchmark Results (8 messages, 48 simulators, 15 seconds)

| Strategy | Msgs/15s | Msgs/sec | Avg time | Bottleneck |
|----------|----------|----------|----------|------------|
| B (production + 0.1s sleep) | 6,506 | 431 | 6.3ms | 0.1s sleep |
| C (no sleep) | 11,169 | 744 | 62.4ms | Message building |
| D (pre-built UDP) | 520,883 | 34,183 | 1.4ms | Socket syscalls |

### No Capacity Limit Needed

Unlike SNMP (which shares an SSH pool), IRP uses stateless UDP. Multiple users
don't compete for resources. The existing `MAX_IRP_MESSAGES = 200` is sufficient
as a UX guard.

### Benchmark Script

**File:** `backend/test_irp_benchmark.py`

```bash
python -m backend.test_irp_benchmark \
    --schema backend/app/modules/reporter/irp/data_formats/IdsDataFormat100600.xml \
    --simulators "50.40.30.2-49" \
    --destination 10.26.52.175 \
    --duration 15 \
    --strategies B,C,D
```

Strategies: A (serial), B (concurrent + sleep), C (no sleep), D (pre-built UDP)

---

## Commits

| Hash | Description |
|------|-------------|
| `cdd805d` | Add SNMP trap throughput benchmark script |
| `aeb85a3` | Add SSH pool + combined command strategies to benchmark |
| `7d13c3d` | Optimize SNMP trap throughput: SSH pool + combined command |
| `3cc3e29` | Increase SSH pool size from 8 to 24 |
| `92c80e4` | Add system-wide SNMP trap capacity check (24k/15s limit) |
| `75011a0` | Fix eslint warnings |
| `b9d4766` | Add IRP message throughput benchmark script |
| `c52246d` | Fix MessageResolver method name in IRP benchmark |
| `349ca34` | Optimize IRP loop: pre-build payloads + remove sleep |

## Key Files Modified

### SNMP
- `backend/app/utils/sapro_ssh.py` — SSH connection pool (24 connections)
- `backend/app/modules/reporter/snmp/attack_traps.py` — Combined SSH command
- `backend/app/routes/reporter.py` — Capacity check on loop start
- `frontend/src/pages/SNMPPage.tsx` — Capacity warning dialog
- `frontend/src/api/services/snmpLoop.service.ts` — CapacityInfo types

### IRP
- `backend/app/modules/reporter/irp/irp_module.py` — `build_irp_payloads()`, `send_irp_udp()`
- `backend/app/modules/reporter/irp/irp_loop_manager.py` — Optimized `_send_batch()`

### Benchmark Scripts
- `backend/test_snmp_benchmark.py`
- `backend/test_irp_benchmark.py`

## Server Configuration

Sapro sshd config (`/usr/local/etc/sshd_config`):
```
MaxStartups 50:30:100
```

Note: SimpleSoft's modified sshd reads from `/usr/local/etc/sshd_config`, NOT
`/etc/ssh/sshd_config`. The standard file is ignored.
