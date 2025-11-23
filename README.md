# SimulatorTools

A comprehensive web application for managing and monitoring network security simulators, including Sapro, CyberController, and IRP Reporter systems.


## Features

- **Multi-Simulator Support**: Manage Sapro, CyberController, and IRP Reporter systems
- **User Management**: Role-based access control with authentication
- **Real-time Monitoring**: Track simulator status and sessions
- **RESTful API**: FastAPI-based backend with OpenAPI documentation
- **Database Support**: PostgreSQL for relational data, MongoDB for document storage
- **Docker Support**: Fully containerized deployment

## Architecture

- **Backend**: FastAPI (Python 3.11+)
  - SQLAlchemy ORM for PostgreSQL
  - PyMongo for MongoDB
  - JWT-based authentication
  - Async request handling
  
- **Frontend**: Modern web interface
  - Responsive design
  - Real-time updates
  
- **Databases**:
  - PostgreSQL 15 for user data, roles, permissions
  - MongoDB 7 for session data and logs

- **Reverse Proxy**: Nginx with SSL/TLS support

## Documentation

- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project

## Deployment

### Option 1: Using Pre-Built Images from GitHub (After First Push)

After you push to GitHub, the `.github/workflows/docker-build-push.yml` workflow automatically builds and publishes images.

**Prerequisites:**
- GitHub Actions has run and built images
- Authenticate to GHCR: `echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin`

**On server:**
```bash
# Use docker-compose.ghcr.yml
cp docker-compose.ghcr.yml docker-compose.yml
docker compose up -d
```

### Option 2: Build Images Locally on Server (First Deployment)

If you haven't pushed to GitHub yet, or want to build locally:

**On server:**
```bash
# Clone repository to server
git clone <your-repo-url> /opt/simtools
cd /opt/simtools

# Use local build compose file
cp docker-compose.local-build.yml docker-compose.yml

# Build and start
docker compose up -d
```

### Configuration Files Needed

On your Rocky Linux 9 server, create these files in `/opt/simtools/`:

### 1. `.env` - Environment Configuration
Use `.env.production.example` as a template. **Critical settings to change**:

- `GITHUB_REPO_OWNER` - Your GitHub username/org (only for GHCR method)
- `PG_PASSWORD` - Generate: `openssl rand -base64 32`
- `MONGO_PASSWORD` - Generate: `openssl rand -base64 32`
- `JWT_SECRET_KEY` - Already set in example: `EWAR0aCjk_v2V9SLCFiA5-_NlrTxAI6BZ95uk52rfLAyT7nU2HaSAjx1ZgUQ6HQC3hQqbgFpNoAo3nY_aYRSXA`
- `CORS_ORIGINS` - Your server with HTTPS, e.g., `https://192.168.1.100` or `https://radware.sapro`
- `API_BASE_URL` - Your API URL with HTTPS, e.g., `https://192.168.1.100/api`

**Database users are created automatically** on first container start - just set the passwords.

**SAPRO SSH settings** are only used in development. In production, the app uses subprocess directly (no SSH).

Then: `chmod 600 /opt/simtools/.env`

### 2. `nginx.conf`
Copy from `nginx.conf.example` - **HTTPS only** with HTTP→HTTPS redirect

### 3. SSL Certificates (Required)
Create self-signed certificates:
```bash
mkdir -p /opt/simtools/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /opt/simtools/ssl/privkey.pem \
  -out /opt/simtools/ssl/fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=Org/CN=192.168.1.100"
```


## Quick Start (Development)

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SimulatorTools
   ```

2. **Set up Python environment**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Create development environment file**
   ```bash
   # Create .env file with your settings
   nano .env
   ```

4. **Run with Docker Compose**
   ```bash
   docker compose up -d
   ```

5. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs


## API Documentation

Once running, interactive API documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
SimulatorTools/
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── modules/        # Business logic modules
│   │   ├── routes/         # API route handlers
│   │   ├── schemas/        # Pydantic schemas
│   │   └── utils/          # Utilities (auth, config, database)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Frontend application
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── scripts/                # Helper scripts
│   ├── check_imports.py   # Import validation
│   └── compile_backend.py # Backend compilation check
├── docker-compose.yml      # Local development
└── docker-compose.ghcr.yml # Production with GHCR images
```

## Modules

### Sapro Integration
- Map management
- Device configuration
- SSH connectivity

### CyberController
- Session management
- Credentials handling
- IRP message processing

### Reporter (IRP)
- Template generation
- Message parsing
- Data format handling

## Management Commands

### Local Development

```bash
# View logs
docker compose logs -f

# View logs (specific service)
docker compose logs -f backend

# Restart services
docker compose restart

# Stop services
docker compose down
```

### Production (on server)

```bash
# View status
docker compose ps

# View logs
docker compose logs -f

# Restart
docker compose restart

# Update images
docker compose pull && docker compose up -d
```

## Security

- JWT-based authentication
- Role-based access control (RBAC)
- Secure password hashing (bcrypt)
- SSL/TLS encryption
- Environment-based configuration
- Docker security best practices

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Quality

```bash
# Check imports
python scripts/check_imports.py

# Compile backend
python scripts/compile_backend.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and contribution process.

## License

[Specify your license here]

## Support

For deployment, see `docker-compose.ghcr.yml` and `.github/workflows/docker-build-push.yml`. For issues and questions, open an issue on GitHub.

## Acknowledgments

- FastAPI framework
- SQLAlchemy ORM
- Docker containerization
- Rocky Linux community

---

**Version**: 1.0  
**Last Updated**: November 23, 2025

