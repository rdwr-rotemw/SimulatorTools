"""
Main FastAPI application entrypoint.

- FastAPI app initialization
- CORS middleware configured (uses settings.CORS_ORIGINS with localhost fallback)
- Registers routers from `app.routes.sapro`, `app.routes.cybercontroller`, and `app.routes.reporter`
- Placeholder startup/shutdown events for DB connections
- Health check endpoint GET /health
- Standard error handling for 404 and 500
"""
from __future__ import annotations

import logging
import os
import sys
import json
from datetime import datetime, timezone
from typing import List
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.utils.config import settings
from backend.app.utils.database import Base, engine, SessionLocal
from backend.app.db.seed_roles import seed_roles
from backend.app.db.seed_users import seed_test_user, seed_cc_admin_user
from backend.app.db.verify_setup import verify_setup
from backend.app.db.seed_templates import seed_device_templates


# Import route modules directly and mount under /api
from backend.app.routes.sapro import router as sapro_router
from backend.app.routes.cybercontroller import router as cc_router
from backend.app.routes.reporter import router as reporter_router
from backend.app.routes.user import router as user_router
from backend.app.routes.role import router as role_router
from backend.app.routes.permission import router as permission_router
from backend.app.routes import snmp_templates


# Remove simple basicConfig and replace with structured configurator

def _get_env_flag(name: str, default: str) -> str:
    return os.environ.get(name, default)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # returns a JSON string
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        # Include exception info if present
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# Simple colored text formatter for development
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\u001b[36m',
        'INFO': '\u001b[32m',
        'WARNING': '\u001b[33m',
        'ERROR': '\u001b[31m',
        'CRITICAL': '\u001b[35m',
    }
    RESET = '\u001b[0m'

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = self.COLORS.get(level, '')
        ts = datetime.fromtimestamp(record.created).isoformat()
        msg = record.getMessage()
        return f"{color}{ts} {level} {record.name}: {msg}{self.RESET}"


def configure_logging(settings_obj=None):
    """Configure structured logging for the application.

    Behavior:
      - In production (ENVIRONMENT == 'production') default to INFO and JSON/text output
      - In development default to DEBUG and colored text output
      - Respect environment overrides: LOG_LEVEL, LOG_FORMAT
    """
    # Determine environment
    env = (os.environ.get('ENVIRONMENT') or getattr(settings_obj, 'ENVIRONMENT', None) or os.environ.get('ENV') or 'development').lower()
    is_prod = env == 'production'

    # Defaults
    default_level = 'INFO' if is_prod else 'DEBUG'
    default_format = 'json' if is_prod else 'text'

    # Allow environment override
    level_name = _get_env_flag('LOG_LEVEL', getattr(settings_obj, 'LOG_LEVEL', default_level))
    log_format = _get_env_flag('LOG_FORMAT', default_format).lower()

    # Normalize level
    try:
        level = getattr(logging, level_name.upper())
    except Exception:
        level = logging.INFO

    # Remove any existing handlers attached to root to prevent duplicate logs
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    # Create stdout handler
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(level)

    if log_format == 'json':
        fmt = JSONFormatter()
    else:
        # text format; for development use colored formatter
        if not is_prod:
            fmt = ColoredFormatter()
        else:
            fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

    handler.setFormatter(fmt)

    # Attach handler to root logger
    root.setLevel(level)
    root.addHandler(handler)

    # Reduce noise from uvicorn and other noisy loggers in production
    if is_prod:
        logging.getLogger('uvicorn.access').setLevel(logging.INFO)
        logging.getLogger('uvicorn.error').setLevel(logging.INFO)


# Apply logging configuration early
configure_logging(settings)

logger = logging.getLogger("sim-tools")


# Define lifespan context manager for startup/shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up Simulators Tools application")
    try:
        # Create SQL tables from ORM models if they do not exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (create_all executed)")

        # Seed roles and users
        try:
            db = SessionLocal()
            try:
                seed_roles(db)
                logger.info("Role seeding completed on startup")

                if not settings.SKIP_TEST_SEEDS:
                    try:
                        seed_test_user(db)
                        logger.info("Test user seeding completed on startup")
                    except Exception:
                        logger.exception("Failed to seed test user on startup")

                    try:
                        seed_cc_admin_user(db)
                        logger.info("CC admin user seeding completed on startup")
                    except Exception:
                        logger.exception("Failed to seed CC admin user on startup")

                if settings.CREATE_ADMIN_ON_STARTUP:
                    try:
                        from backend.app.db.seed_users import seed_admin_user

                        username = settings.ADMIN_USERNAME
                        phash = settings.ADMIN_PASSWORD_HASH
                        pclear = settings.ADMIN_PASSWORD
                        if not username:
                            logger.error("CREATE_ADMIN_ON_STARTUP is true but ADMIN_USERNAME is not set; skipping admin creation")
                        else:
                            seed_admin_user(db, username=username, password=pclear, password_hash=phash)
                            logger.info("Admin user seeding attempted on startup")
                    except Exception:
                        logger.exception("Failed to seed admin user on startup")

                try:
                    verify_setup(db)
                    logger.info("Startup verification completed")
                except Exception:
                    logger.exception("Failed to verify setup on startup")

            finally:
                db.close()
        except Exception as exc:
            logger.exception("Failed to seed roles on startup: %s", exc)
    except Exception as exc:
        logger.exception("Failed to create database tables on startup: %s", exc)

    # Ensure MongoDB IRP indexes if configured
    from backend.app.utils.database import create_irp_indexes, get_mongo_db
    try:
        create_irp_indexes()
        logger.info("Ensured MongoDB indexes for irp_data_formats")
    except Exception:
        logger.exception("Failed to create/ensure MongoDB indexes on startup")

    # Seed device templates into MongoDB
    try:
        mongo_db = get_mongo_db()
        seed_device_templates(mongo_db)
        logger.info("Device templates seeding completed")
    except Exception as exc:
        logger.exception("Failed to seed device templates: %s", exc)

    # Initialize SNMP Loop Manager
    try:
        from backend.app.modules.reporter.snmp.snmp_loop_manager import initialize_loop_manager
        mongo_db = get_mongo_db()
        await initialize_loop_manager(mongo_db)
        logger.info("SNMP Loop Manager initialized successfully")
    except Exception as exc:
        logger.exception("Failed to initialize SNMP Loop Manager: %s", exc)

    yield

    # Shutdown logic
    logger.info("Shutting down Simulators Tools application")

    # Shutdown SNMP Loop Manager
    try:
        from backend.app.modules.reporter.snmp.snmp_loop_manager import shutdown_loop_manager
        await shutdown_loop_manager()
        logger.info("SNMP Loop Manager shutdown completed")
    except Exception as exc:
        logger.exception("Failed to shutdown SNMP Loop Manager: %s", exc)


# Create FastAPI app with lifespan handler
app = FastAPI(title="Simulators Tools Backend", lifespan=lifespan)


# Build CORS origins list: prefer configured origins, always include localhost:3000 for local dev
_origins: List[str] = []
try:
    _origins = list(settings.CORS_ORIGINS or [])
except Exception:
    _origins = ["http://localhost:3000"]

if "http://localhost:3000" not in _origins:
    _origins.insert(0, "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api prefix
app.include_router(sapro_router)
app.include_router(cc_router)
app.include_router(reporter_router)
# Register user router (it already has prefix "/api" inside; include at root as requested)
app.include_router(user_router, prefix="", tags=["users"])
# Register new routers
app.include_router(role_router)
app.include_router(permission_router)
app.include_router(snmp_templates.router)

# Mount static files (React build) - serve frontend build at root if present
BUILD_DIR = Path(__file__).parent.parent.parent / "frontend" / "build"
if BUILD_DIR.exists():
    app.mount("/", StaticFiles(directory=str(BUILD_DIR), html=True), name="static")


@app.get("/health", tags=["meta"])
async def health():
    """Lightweight health check for orchestration and readiness probes."""
    return {"status": "ok"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Provide a standard JSON response for HTTP exceptions (including 404)
    content = {"detail": exc.detail if exc.detail else "Not Found"}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    # Generic handler for unexpected server errors
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# Minimal run guard for local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
