# SimulatorTools

A web application for managing and operating Sapro simulators — Sapro, CyberController, and Reporting systems.

## Features

- **Multi-Simulator Support**: Manage Sapro simulators and CyberController sessions
- **Reporter Modules**: SNMP trap generation, IRP binary message sending, and Polling XMF configuration
- **User Management**: Role-based access control with JWT authentication
- **Real-time Monitoring**: Track simulator status, loop progress, and session state
- **RESTful API**: FastAPI backend with interactive OpenAPI documentation
- **Docker Support**: Containerized deployment via GitHub Container Registry

## Architecture

- **Backend**: FastAPI (Python 3.11+)
  - SQLAlchemy ORM for PostgreSQL
  - PyMongo for MongoDB
  - JWT-based authentication
  - Async request handling

- **Frontend**: React (TypeScript)
  - Material-UI component library
  - Real-time progress and status updates

- **Databases**:
  - PostgreSQL — users, roles, permissions, audit logs (SQLAlchemy ORM)
  - MongoDB — templates, IRP schemas, polling configs, and session state (PyMongo)

- **Reverse Proxy**: Nginx with SSL/TLS

## Modules

### Sapro Integration
- Map and device management
- Device create / update / delete via Sapro commands (`adddev`, `deldev`)
- SSH connectivity and session handling

### CyberController
- Session and credential management
- Device management: delete / add single devices or IP ranges
- Device driver installation

### Reporter

#### SNMP
- Generate TCL scripts with `SA_sendtrap` / `SA_settrapmgrs` commands
- Batch trap sending with configurable varbinds

#### IRP
- Template generation from IdsDataFormat XML schemas
- Binary message building and UDP sending
- Round-trip validation: send → capture PCAP → extract bytes → parse with Java parser

#### Polling
- XMF (TCL) file generation for HTTP polling endpoints
- Configurable data structures with field types: random IP, timestamp, composite, arrays, objects
- Protocol-aware tcp-flag conditional generation

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (for users, roles, permissions)
- MongoDB (for templates, schemas, session data)
- Java JRE (for IRP parser — optional for non-IRP work)

### Backend

```bash
# From project root
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Start backend
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs available at: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm start
```

Frontend available at: http://localhost:3000

---

## Integration Tests

Integration tests validate the three core reporting modules **without requiring a live Sapro or CyberController connection**. They run against local fixtures and loopback UDP.

### What is tested

| Test file | What it covers |
|-----------|---------------|
| `test_snmp_script_generation.py` | TCL script structure, varbind field placement, `SA_sendtrap` syntax, samples consistency |
| `test_irp_message_validation.py` | Template generation for messages 1, 4, 7, 19, 20, 52 — full round-trip: UDP send → PCAP capture → byte extraction → Java parser (no errors) |
| `test_polling_xmf_generation.py` | XMF/TCL file generation — proc definitions, field types, array loops, protocol conditionals, JSON content |

### Requirements

| Requirement | Used by | Notes |
|-------------|---------|-------|
| Python 3.11+ | All tests | Standard |
| Java JRE | IRP tests | Needed to run `parser.jar` |
| `tclsh` | Polling TCL syntax tests | **Optional** — tests are skipped gracefully if not installed |

### Running locally (Windows dev)

```bash
# From project root, with virtualenv active
pytest backend/tests/integration/ -v --tb=short

# Run a single module
pytest backend/tests/integration/test_snmp_script_generation.py -v
pytest backend/tests/integration/test_irp_message_validation.py -v
pytest backend/tests/integration/test_polling_xmf_generation.py -v
```

> **Note**: `tclsh` is not typically installed on Windows. The 3 TCL syntax tests are automatically skipped — this is expected.

### Running in Docker (production image)

The backend Docker image includes Java and `tclsh`, so all tests run including TCL syntax validation:

```bash
# Build the image first (or pull from GHCR)
docker build -t simulator-backend ./backend

# Run integration tests inside the container
docker run --rm simulator-backend pytest backend/tests/integration/ -v --tb=short
```

### CI/CD — GitHub Actions

Integration tests run automatically on every push to `main` or `dev` and on pull requests to `main`. The Docker build is **gated** — images are only built and pushed to GHCR if all integration tests pass.

Pipeline: `.github/workflows/docker-build-push.yml`

```
push / PR
  └─► integration-tests (ubuntu-latest)
        ├── Install Java + tclsh
        ├── pip install -r backend/requirements.txt
        └── pytest backend/tests/integration/
              └─► (pass) ─► build-and-push (Docker images to GHCR)
              └─► (fail) ─► build blocked
```

---

## Deployment

### Production — Pre-Built Images (Recommended)

GitHub Actions automatically builds and publishes Docker images to GHCR on every push. No manual builds needed on the server.

**On your server:**

```bash
cd /opt/simtools

# One-time setup:
# 1. docker-compose.yml  (copy from docker-compose.ghcr.yml in repo)
# 2. .env                (use .env.production.example as template)
# 3. nginx.conf          (copy from nginx.conf.example)
# 4. ssl/                (directory with SSL certificates)

# Authenticate with GHCR (one-time):
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Deploy / update:
docker compose pull
docker compose up -d
```

### Updating

```bash
cd /opt/simtools
docker compose pull && docker compose up -d
```

No `git pull`, no rebuilds — GitHub Actions handles everything.

### Initial Server Setup

1. **Install Docker** — see `scripts/install-docker-rocky.sh`

2. **Create directories:**
   ```bash
   mkdir -p /opt/simtools/{ssl,logs}
   cd /opt/simtools
   ```

3. **Configure `.env`** — copy `.env.production.example` and set:
   - `PG_PASSWORD` — `openssl rand -base64 32`
   - `MONGO_PASSWORD` — `openssl rand -base64 32`
   - `JWT_SECRET_KEY`
   - `CORS_ORIGINS` — `https://YOUR_SERVER_IP`

4. **SSL certificates:**
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ssl/privkey.pem \
     -out ssl/fullchain.pem \
     -subj "/C=US/ST=State/L=City/O=Org/CN=YOUR_SERVER_IP"
   ```

5. **Deploy:**
   ```bash
   docker compose pull
   docker compose up -d
   ```

---

## Project Structure

```
SimulatorTools/
├── backend/
│   ├── app/
│   │   ├── models/                  # Pydantic models
│   │   ├── modules/
│   │   │   └── reporter/
│   │   │       ├── snmp/            # SNMP trap generation (TCL)
│   │   │       ├── irp/             # IRP binary message building + validation
│   │   │       └── polling/         # XMF/TCL file generation
│   │   ├── routes/                  # API route handlers
│   │   └── utils/                   # Auth, config, database helpers
│   ├── tests/
│   │   └── integration/             # Integration test suite
│   │       ├── test_snmp_script_generation.py
│   │       ├── test_irp_message_validation.py
│   │       └── test_polling_xmf_generation.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── Reporter/            # SNMP, IRP, Polling UI components
│   │   ├── pages/
│   │   └── api/services/
│   ├── Dockerfile
│   └── package.json
├── .github/
│   └── workflows/
│       └── docker-build-push.yml    # CI/CD pipeline
├── docker-compose.yml               # Local development
└── docker-compose.ghcr.yml          # Production (GHCR images)
```

---

## Management Commands

### Development

```bash
# Backend logs
docker compose logs -f backend

# Restart backend only
docker compose restart backend

# Stop all services
docker compose down
```

### Production

```bash
docker compose ps                        # Status
docker compose logs -f                   # All logs
docker compose logs -f backend           # Backend logs
docker compose pull && docker compose up -d  # Update
```

---

## Security

- JWT-based authentication with role-based access control
- Argon2 password hashing
- SSL/TLS via Nginx reverse proxy
- Environment-based secrets (never hardcoded)

---

**Last Updated**: February 2026
