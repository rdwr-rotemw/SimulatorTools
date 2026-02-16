# Database Schema

**Last updated:** February 8, 2026

## Database Overview

Simulator Tools uses a dual-database architecture:
- **PostgreSQL**: Structured relational data (users, roles, simulators, sessions)
- **MongoDB**: Flexible document store (IRP schemas, device templates, polling configs)

## PostgreSQL Schema (SQLAlchemy ORM)

### Tables Overview

| Table | Purpose | Location |
|-------|---------|----------|
| `users` | User accounts and authentication | [models/user.py](../backend/app/models/user.py) |
| `roles` | Available system roles | [models/role.py](../backend/app/models/role.py) |
| `user_roles` | User-to-role assignments (M2M) | [models/user_role.py](../backend/app/models/user_role.py) |
| `permissions` | Granular permissions | [models/permission.py](../backend/app/models/permission.py) |
| `role_permissions` | Role-to-permission assignments (M2M) | [models/role_permission.py](../backend/app/models/role_permission.py) |
| `simulators` | DefensePro simulator instances | [models/simulator.py](../backend/app/models/simulator.py) |
| `cc_sessions` | CyberController SSH sessions | [models/cc_session.py](../backend/app/models/cc_session.py) |
| `audit_logs` | Audit trail for sensitive operations | [models/audit_log.py](../backend/app/models/audit_log.py) |

### 1. users Table

**File**: [backend/app/models/user.py](../backend/app/models/user.py)

```python
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    workspace = Column(String(100), nullable=True, default="*")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    roles = relationship("Role", secondary="user_roles", viewonly=True)

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(ur.role.role_name == role_name for ur in self.user_roles)
```

**Example Document**:
```json
{
    "user_id": 1,
    "username": "admin",
    "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
    "workspace": "*",
    "created_at": "2026-02-08T10:30:00Z"
}
```

**Indexes**:
- Primary key: `user_id`
- Unique index: `username`

**Relationships**:
- One-to-many: `user_roles` (via UserRole table)
- Many-to-many: `roles` (through user_roles)

### 2. roles Table

**File**: [backend/app/models/role.py](../backend/app/models/role.py)

```python
class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)

    # Relationships
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
```

**Example Rows**:
```sql
INSERT INTO roles (role_name, description) VALUES
    ('admin', 'Full system access'),
    ('sapro_user', 'Access to Sapro simulators'),
    ('cc_user', 'Access to CyberController features'),
    ('reporter_user', 'Access to SNMP/IRP reporting');
```

**Built-in Roles**:
- `admin`: Full access to all features
- `sapro_user`: Create/manage simulators
- `cc_user`: Manage CyberController sessions
- `reporter_user`: Send SNMP traps and IRP messages

### 3. user_roles Table (M2M)

**File**: [backend/app/models/user_role.py](../backend/app/models/user_role.py)

```python
class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
```

**Example Rows**:
```sql
INSERT INTO user_roles (user_id, role_id) VALUES
    (1, 1),  -- admin has admin role
    (2, 2),  -- user2 has sapro_user role
    (2, 4);  -- user2 also has reporter_user role
```

### 4. simulators Table

**File**: [backend/app/models/simulator.py](../backend/app/models/simulator.py)

```python
class Simulator(Base):
    __tablename__ = "simulators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="created")
    is_cc_device = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

**Example Document**:
```json
{
    "id": 1,
    "ip_address": "192.168.1.10",
    "status": "running",
    "is_cc_device": false,
    "created_at": "2026-02-08T10:00:00Z"
}
```

**Indexes**:
- Primary key: `id`
- Unique index: `ip_address`

**Status Values**:
- `created`: Simulator created but not started
- `running`: Actively running
- `stopped`: Manually stopped
- `error`: Failed state

### 5. cc_sessions Table

**File**: [backend/app/models/cc_session.py](../backend/app/models/cc_session.py)

```python
class CCSession(Base):
    __tablename__ = "cc_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(100), nullable=False, unique=True, index=True)
    cc_host = Column(String(255), nullable=False)
    cc_port = Column(Integer, nullable=False, default=22)
    cc_username = Column(String(100), nullable=False)
    cc_password = Column(String(255), nullable=False)  # Encrypted in production
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

**Example Document**:
```json
{
    "id": 1,
    "session_name": "cc-production",
    "cc_host": "172.17.166.20",
    "cc_port": 22,
    "cc_username": "radware",
    "cc_password": "encrypted_password_hash",
    "created_at": "2026-02-08T09:00:00Z"
}
```

### 6. permissions Table

**File**: [backend/app/models/permission.py](../backend/app/models/permission.py)

```python
class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    permission_name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission")
```

**Example Permissions**:
```sql
INSERT INTO permissions (permission_name, description) VALUES
    ('create_simulator', 'Create new simulators'),
    ('delete_simulator', 'Delete existing simulators'),
    ('send_snmp_trap', 'Send SNMP traps'),
    ('manage_users', 'Create/update/delete users');
```

### 7. audit_logs Table

**File**: [backend/app/models/audit_log.py](../backend/app/models/audit_log.py)

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
```

**Example Document**:
```json
{
    "id": 42,
    "user_id": 1,
    "action": "create_simulator",
    "resource_type": "simulator",
    "resource_id": "192.168.1.10",
    "details": "{\"ip\": \"192.168.1.10\", \"status\": \"created\"}",
    "timestamp": "2026-02-08T11:15:30Z"
}
```

## MongoDB Collections

### Collection: irp_data_formats

**Purpose**: Store parsed IdsDataFormat XML schemas from CyberController

**Indexes**:
```python
# Compound index for version + checksum lookups
db.irp_data_formats.create_index([
    ("IdsDataFormat_version", ASCENDING),
    ("xml_checksum", ASCENDING)
], name="version_checksum_idx", sparse=True)

# Single field indexes
db.irp_data_formats.create_index([("IdsDataFormat_version", ASCENDING)])
db.irp_data_formats.create_index([("created_at", ASCENDING)])
```

**Example Document**:
```json
{
    "_id": ObjectId("65b4f3e2a1b2c3d4e5f60001"),
    "IdsDataFormat_version": "9.15.0.0",
    "xml_checksum": "a3f5e8b2c1d9f4e7a6b5c8d2e1f3a4b7",
    "created_at": "2026-02-08T10:30:00Z",
    "schema": {
        "messages": {
            "1": {
                "name": "ATTACK_START",
                "data": {
                    "type": "struct",
                    "fields": {
                        "alarm_code": {"type": "uint32"},
                        "severity": {"type": "enum", "enum_name": "SeverityLevel"},
                        "source_ip": {"type": "ipv4"}
                    }
                }
            },
            "2": {
                "name": "ATTACK_STOP",
                "data": {...}
            }
        },
        "types": {
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
        },
        "templates": {
            "structs": {
                "CommonHeader": {
                    "fields": {
                        "message_id": {"type": "uint16"},
                        "timestamp": {"type": "uint64"}
                    }
                }
            }
        }
    }
}
```

**Document Structure**:
- `_id`: MongoDB ObjectId
- `IdsDataFormat_version`: CC version (e.g., "9.15.0.0")
- `xml_checksum`: SHA256 hash of original XML
- `created_at`: ISO 8601 timestamp
- `schema`: Parsed XML structure with:
  - `messages`: Message type definitions (id → {name, data})
  - `types`: Type definitions (primitives, enums, namespaces)
  - `templates`: Reusable struct templates

### Collection: device_templates

**Purpose**: Store device configuration templates (JSON-to-XML conversion for Sapro)

**Example Document**:
```json
{
    "_id": ObjectId("65b4f3e2a1b2c3d4e5f60002"),
    "template_name": "http_server",
    "description": "HTTP server with configurable responses",
    "created_at": "2026-02-08T09:00:00Z",
    "template": {
        "Device": {
            "@attributes": {
                "Type": "HTTP_SERVER",
                "IP": "<ip>"
            },
            "Parameters": {
                "Port": "80",
                "ResponseCode": "200",
                "ResponseBody": "OK",
                "Delay": "0"
            }
        }
    }
}
```

**Field Notes**:
- `<ip>` placeholder replaced with actual simulator IP during loading
- `@attributes` key used for XML attributes during JSON→XML conversion
- Nested structure mirrors XML hierarchy

### Collection: polling_templates

**Purpose**: Store saved polling endpoint configurations for reuse

**Example Document**:
```json
{
    "_id": ObjectId("65b4f3e2a1b2c3d4e5f60003"),
    "name": "attack_data_endpoint",
    "description": "Attack data polling endpoint with randomized IPs",
    "created_at": "2026-02-08T11:00:00Z",
    "endpoint": {
        "path": "/v1/attack-data",
        "method": "GET",
        "data_key": "attack_data",
        "polling_interval_seconds": 60,
        "data_structure": {
            "attack_id": {
                "type": "template",
                "value": "atk{{INDEX}}"
            },
            "source_ip": {
                "type": "random_ipv4",
                "mode": "random"
            },
            "destination_ip": {
                "type": "random_ipv4",
                "mode": "random"
            },
            "severity": {
                "type": "number",
                "mode": "random",
                "min": 1,
                "max": 5
            },
            "timestamp": {
                "type": "timestamp",
                "offset": 0
            },
            "details": {
                "type": "object",
                "properties": {
                    "packet_count": {
                        "type": "number",
                        "mode": "random",
                        "min": 100,
                        "max": 10000
                    },
                    "protocol": {
                        "type": "string",
                        "value": "TCP"
                    }
                }
            },
            "related_attacks": {
                "type": "array",
                "repeat_min": 1,
                "repeat_max": 5,
                "item": {
                    "type": "template",
                    "value": "rel{{INDEX}}"
                }
            }
        }
    }
}
```

**Field Type Reference** ([models/polling.py](../backend/app/models/polling.py)):
- `string`: Static or random string
- `number`: Static or random number (with min/max)
- `boolean`: True/false
- `timestamp`: Unix timestamp with offset
- `random_ipv4`: Random IPv4 address
- `random_fqdn`: Random domain name with suffix
- `template`: Template string with {{INDEX}} placeholder
- `object`: Nested object with properties
- `array`: Repeating array with min/max count

## Relationships

### User → Roles (Many-to-Many)
```
users (1) ←→ (M) user_roles (M) ←→ (1) roles
```

**Query Example**:
```python
# Get user with roles
user = db.query(User).filter(User.username == "admin").first()
role_names = [ur.role.role_name for ur in user.user_roles]
# Output: ['admin', 'sapro_user']
```

### Role → Permissions (Many-to-Many)
```
roles (1) ←→ (M) role_permissions (M) ←→ (1) permissions
```

### Audit Logs → Users (Many-to-One)
```
audit_logs (M) → (1) users
```

## Migration Strategy

### PostgreSQL
- **ORM**: SQLAlchemy with Alembic for migrations (not currently configured)
- **Current**: Tables created via `Base.metadata.create_all()` on startup
- **Production**: Implement Alembic migrations for schema changes

### MongoDB
- **Schema**: Flexible, no strict schema enforcement
- **Indexes**: Created on startup via `create_irp_indexes()`
- **Validation**: Pydantic models validate data before insertion

## Database Connection Configuration

**Environment Variables** (.env):
```env
# PostgreSQL
PG_HOST=172.17.166.10
PG_PORT=5432
PG_DB=sim_tools
PG_USER=postgres
PG_PASSWORD=securepass

# MongoDB
MONGO_HOST=172.17.166.10
MONGO_PORT=27017
MONGO_DB=sim_tools
MONGO_USER=admin
MONGO_PASSWORD=securepass
```

**Connection Strings**:
```python
# PostgreSQL (SQLAlchemy)
postgresql+psycopg2://postgres:securepass@172.17.166.10:5432/sim_tools

# MongoDB (PyMongo)
mongodb://admin:securepass@172.17.166.10:27017/sim_tools?authSource=admin
```

## Related Documentation

- [Architecture](./ARCHITECTURE.md) - Database interaction patterns
- [API Patterns](./API_PATTERNS.md) - Database query examples in endpoints
- [Coding Standards](./CODING_STANDARDS.md) - ORM best practices
