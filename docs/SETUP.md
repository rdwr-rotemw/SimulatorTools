# Setup Guide

**Last updated:** February 8, 2026

## Prerequisites

### Required Software

- **Python**: 3.10+ (tested with 3.11)
- **Node.js**: 16+ (for frontend)
- **PostgreSQL**: 12+ (relational database)
- **MongoDB**: 4.4+ (document store)
- **Git**: For version control
- **SSH Client**: For Sapro integration

### Optional
- **Docker**: For containerized deployment
- **VS Code**: Recommended IDE with Claude Code extension

## Environment Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd SimulatorTools
```

### 2. Create Virtual Environment (Python)

```bash
# Create venv
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Key Dependencies** ([requirements.txt](../backend/requirements.txt)):
- `fastapi==0.121.0` - Web framework
- `uvicorn==0.38.0` - ASGI server
- `sqlalchemy==2.0.44` - PostgreSQL ORM
- `pymongo==4.15.3` - MongoDB driver
- `pysnmp==4.4.12` - SNMP protocol
- `paramiko==4.0.0` - SSH client
- `pydantic-settings==2.11.0` - Config management

### 4. Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

**Key Dependencies** ([package.json](../frontend/package.json)):
- `react@19.2.0` - UI framework
- `@mui/material@7.3.5` - Material-UI components
- `axios@1.13.2` - HTTP client
- `zustand@5.0.8` - State management
- `react-router-dom@7.9.6` - Routing

## Database Setup

### PostgreSQL Setup

**1. Install PostgreSQL**

```bash
# Windows: Download installer from postgresql.org
# Linux (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

**2. Create Database**

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE sim_tools;

-- Create user (optional)
CREATE USER sim_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE sim_tools TO sim_user;
```

**3. Verify Connection**

```bash
psql -U sim_user -d sim_tools -h localhost
```

### MongoDB Setup

**1. Install MongoDB**

```bash
# Windows: Download installer from mongodb.com
# Linux (Ubuntu)
sudo apt-get install mongodb

# macOS
brew tap mongodb/brew
brew install mongodb-community
```

**2. Start MongoDB Service**

```bash
# Windows
net start MongoDB

# Linux
sudo systemctl start mongod

# macOS
brew services start mongodb-community
```

**3. Create Database and User**

```javascript
// Connect to MongoDB shell
mongosh

// Switch to sim_tools database
use sim_tools

// Create admin user
db.createUser({
    user: "sim_user",
    pwd: "secure_password",
    roles: [
        { role: "readWrite", db: "sim_tools" }
    ]
})
```

## Environment Variables

### Create .env File

Copy the example and fill in your values:

```bash
# In project root
cp .env.example .env
```

### Environment Variables Reference

**File**: `.env` (in project root)

```env
# Environment
ENVIRONMENT=development  # or 'production'
DEBUG=true
LOG_LEVEL=DEBUG

# Database Type
DATABASE_TYPE=postgresql

# PostgreSQL Configuration
PG_HOST=localhost
PG_PORT=5432
PG_DB=sim_tools
PG_USER=sim_user
PG_PASSWORD=secure_password

# MongoDB Configuration
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB=sim_tools
MONGO_USER=sim_user
MONGO_PASSWORD=secure_password

# JWT Authentication
JWT_SECRET_KEY=your_secret_key_here_replace_in_production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours for dev

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Backend Configuration
BACKEND_PORT=8000
API_BASE_URL=http://localhost:8000

# Sapro Integration
SAPRO_IP=172.17.166.10
SAPRO_PORT=2100
SAPRO_MAP_DIR=/opt/sapro/map/
SAPRO_SSH_HOST=172.17.166.10
SAPRO_SSH_USER=root
SAPRO_SSH_PASSWORD=sapro_password

# IRP/IdsDataFormat Download Path
DOWNLOAD_PATH=/tmp/irp_files

# User Seeding
SKIP_TEST_SEEDS=false  # Set to true in production
CREATE_ADMIN_ON_STARTUP=false
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123  # Only for dev - use ADMIN_PASSWORD_HASH in prod
```

### Generate Secure JWT Secret

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Node.js
node -e "console.log(require('crypto').randomBytes(64).toString('base64'))"
```

## Running the Application

### Development Mode

**1. Start Backend**

```bash
# Activate venv
cd backend
source ../.venv/bin/activate  # or .venv\Scripts\activate on Windows

# Run with uvicorn
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the main.py run guard
python -m backend.app.main
```

**Backend will be available at**: `http://localhost:8000`

**API Docs**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

**2. Start Frontend**

```bash
# In new terminal
cd frontend
npm start
```

**Frontend will be available at**: `http://localhost:3000`

### Production Deployment

**1. Build Frontend**

```bash
cd frontend
npm run build
```

This creates optimized static files in `frontend/build/`.

**2. Run Backend (Production)**

```bash
# Set production environment variables
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=INFO
export SKIP_TEST_SEEDS=true
export JWT_SECRET_KEY=<your-secure-key>

# Run with production server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**3. Serve Frontend**

The backend automatically serves the frontend build at `/` if `frontend/build/` exists:

**File**: [backend/app/main.py:264-266](../backend/app/main.py)

```python
BUILD_DIR = Path(__file__).parent.parent.parent / "frontend" / "build"
if BUILD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(BUILD_DIR), html=True), name="static")
```

## Docker Deployment (Optional)

### Dockerfile (Backend)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ ./backend/
COPY frontend/build/ ./frontend/build/

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  backend:
    build: .
    network_mode: host  # Required for simulator IP binding
    environment:
      - ENVIRONMENT=production
      - PG_HOST=localhost
      - MONGO_HOST=localhost
    volumes:
      - ./backend:/app/backend
    depends_on:
      - postgres
      - mongodb

  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: sim_tools
      POSTGRES_USER: sim_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  mongodb:
    image: mongo:6
    environment:
      MONGO_INITDB_DATABASE: sim_tools
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: secure_password
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"

volumes:
  postgres_data:
  mongo_data:
```

### Run with Docker Compose

```bash
docker-compose up -d
```

## Database Initialization

### Automatic on Startup

The application automatically:
1. Creates PostgreSQL tables (via SQLAlchemy)
2. Seeds roles (`admin`, `sapro_user`, `cc_user`, `reporter_user`)
3. Seeds test users (if `SKIP_TEST_SEEDS=false`)
4. Creates MongoDB indexes

**File**: [backend/app/main.py:151-223](../backend/app/main.py)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up Simulators Tools application")

    # Create SQL tables
    Base.metadata.create_all(bind=engine)

    # Seed roles and users
    db = SessionLocal()
    try:
        seed_roles(db)
        if not settings.SKIP_TEST_SEEDS:
            seed_test_user(db)
            seed_cc_admin_user(db)
    finally:
        db.close()

    # Create MongoDB indexes
    create_irp_indexes()

    yield

    # Shutdown logic
    logger.info("Shutting down")
```

### Manual Seeding

**Seed Roles**:
```bash
python -c "
from backend.app.utils.database import SessionLocal
from backend.app.db.seed_roles import seed_roles
db = SessionLocal()
seed_roles(db)
db.close()
"
```

**Seed Test User**:
```bash
python -c "
from backend.app.utils.database import SessionLocal
from backend.app.db.seed_users import seed_test_user
db = SessionLocal()
seed_test_user(db)
db.close()
"
```

## Troubleshooting

### Common Issues

**1. Database Connection Errors**

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**:
- Verify PostgreSQL is running: `pg_isready`
- Check connection details in `.env`
- Test connection: `psql -U sim_user -d sim_tools -h localhost`

**2. MongoDB Connection Errors**

```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017
```

**Solution**:
- Verify MongoDB is running: `mongosh --eval "db.adminCommand('ping')"`
- Check MONGO_HOST and MONGO_PORT in `.env`

**3. Frontend Proxy Errors**

```
[HPM] Error occurred while trying to proxy request
```

**Solution**:
- Ensure backend is running on port 8000
- Check `proxy` setting in `frontend/package.json`:
  ```json
  "proxy": "http://localhost:8000"
  ```

**4. CORS Errors**

```
Access to XMLHttpRequest blocked by CORS policy
```

**Solution**:
- Add frontend origin to CORS_ORIGINS in `.env`:
  ```env
  CORS_ORIGINS=http://localhost:3000
  ```

**5. SSH Connection to Sapro Fails**

```
paramiko.ssh_exception.AuthenticationException
```

**Solution**:
- Verify SAPRO_SSH_HOST, SAPRO_SSH_USER, SAPRO_SSH_PASSWORD
- Test SSH manually: `ssh root@172.17.166.10`
- Check firewall rules

## Development vs. Production Differences

| Aspect | Development | Production |
|--------|-------------|------------|
| Environment | `ENVIRONMENT=development` | `ENVIRONMENT=production` |
| Logging | Colored text, DEBUG level | JSON structured, INFO level |
| JWT Secret | Can use default (warning) | Must set secure key (validated) |
| Test Users | Seeded automatically | Disabled (SKIP_TEST_SEEDS=true) |
| CORS | localhost:3000 allowed | Must configure explicitly |
| Frontend | React dev server (port 3000) | Static files served by backend |
| Reload | Auto-reload on changes | Fixed deployment |
| Workers | 1 (uvicorn --reload) | 4+ (uvicorn --workers 4) |

## Next Steps

1. Review [Quick Start Guide](./QUICK_START.md) for common workflows
2. Explore [API Documentation](http://localhost:8000/docs) (Swagger UI)
3. Check [Architecture](./ARCHITECTURE.md) for system design
4. Read [Coding Standards](./CODING_STANDARDS.md) before contributing

## Related Documentation

- [Quick Start](./QUICK_START.md) - Common development workflows
- [Architecture](./ARCHITECTURE.md) - System design and components
- [API Patterns](./API_PATTERNS.md) - Endpoint examples
- [Database Schema](./DATABASE_SCHEMA.md) - Data models
