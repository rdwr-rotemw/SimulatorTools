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

### Production Deployment Using Pre-Built Images (Recommended)

This project uses GitHub Actions to automatically build Docker images and publish them to GitHub Container Registry (GHCR). You don't need to build images manually on the server.

**Workflow:**
1. Push code to GitHub → GitHub Actions builds images → Images published to GHCR
2. On server: Pull images and deploy with `docker compose pull && docker compose up -d`

**On your Rocky Linux 9 server:**

```bash
cd /opt/simtools

# One-time setup: Create these files
# 1. docker-compose.yml (copy from docker-compose.ghcr.yml in repo)
# 2. .env (use .env.production.example as template)
# 3. nginx.conf (copy from nginx.conf.example)
# 4. ssl/ directory with certificates

# Deploy/Update workflow:
docker compose pull    # Pull latest images from GHCR
docker compose up -d   # Start/update containers

# That's it! No git pull, no builds!
```

### Initial Server Setup

1. **Install Docker** (see `scripts/install-docker-rocky.sh`)

2. **Create project directory:**
   ```bash
   mkdir -p /opt/simtools/{ssl,logs}
   cd /opt/simtools
   ```

3. **Create configuration files:**

   **a) `docker-compose.yml`** - Copy from `docker-compose.ghcr.yml`:
   ```bash
   curl -o docker-compose.yml https://raw.githubusercontent.com/YOUR_USERNAME/SimulatorTools/dev/docker-compose.ghcr.yml
   ```

   **b) `.env`** - Use `.env.production.example` as template:
   ```bash
   nano .env
   ```
   Update these critical values:
   - `GITHUB_REPO_OWNER` - Your GitHub username/org
   - `PG_PASSWORD` - Generate: `openssl rand -base64 32`
   - `MONGO_PASSWORD` - Generate: `openssl rand -base64 32`
   - `JWT_SECRET_KEY` - Already set in example
   - `CORS_ORIGINS` - `https://YOUR_SERVER_IP`
   - `API_BASE_URL` - `https://YOUR_SERVER_IP/api`

   Then: `chmod 600 .env`

   **c) `nginx.conf`** - Copy from `nginx.conf.example`:
   ```bash
   curl -o nginx.conf https://raw.githubusercontent.com/YOUR_USERNAME/SimulatorTools/dev/nginx.conf.example
   ```

   **d) SSL Certificates:**
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout ssl/privkey.pem \
     -out ssl/fullchain.pem \
     -subj "/C=US/ST=State/L=City/O=Org/CN=YOUR_SERVER_IP"
   ```

4. **Login to GitHub Container Registry:**
   ```bash
   echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
   ```

5. **Deploy:**
   ```bash
   docker compose pull
   docker compose up -d
   ```

### Updating the Application

When you push new code to GitHub:

```bash
# On server - just pull new images and restart
cd /opt/simtools
docker compose pull
docker compose up -d
```

**No git pull, no rebuilds needed!** GitHub Actions handles everything.

### Development vs Production

- **Development** (your machine): Use `docker-compose.yml` - builds locally
- **Production** (server): Use `docker-compose.ghcr.yml` - pulls pre-built images from GHCR


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

