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

Use pre-built Docker images from GitHub Container Registry. The `.github/workflows/docker-build-push.yml` workflow automatically builds and publishes images on push to main.

On your Rocky Linux 9 server, create these files in `/opt/simtools/`:

1. **docker-compose.yml** - Use `docker-compose.ghcr.yml` as template
2. **.env** - Configure your environment variables
3. **nginx.conf** - Reverse proxy configuration

Then run: `docker compose up -d`

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

