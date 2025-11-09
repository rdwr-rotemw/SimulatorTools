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
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.utils.config import settings

# Import route modules directly and mount under /api
from backend.app.routes.sapro import router as sapro_router
from backend.app.routes.cybercontroller import router as cc_router
from backend.app.routes.reporter import router as reports_router
from backend.app.routes.user import router as user_router
from backend.app.routes.role import router as role_router
from backend.app.routes.permission import router as permission_router
from backend.app.routes.sapro import router as simulator_router  # simulator routes live in sapro.py
from backend.app.routes.cc_credentials import router as cc_credentials_router

# Import DB base and engine to create tables on startup
from backend.app.utils.database import Base, engine


logger = logging.getLogger("sim-tools")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Simulators Tools Backend")

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
app.include_router(sapro_router, prefix="/api")
app.include_router(cc_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
# Register user router (it already has prefix "/api" inside; include at root as requested)
app.include_router(user_router, prefix="", tags=["users"])
# Register new routers
app.include_router(role_router)
app.include_router(permission_router)
app.include_router(simulator_router)
app.include_router(cc_credentials_router)


@app.get("/health", tags=["meta"])
async def health():
    """Lightweight health check for orchestration and readiness probes."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    # Initialize DB tables and other startup tasks
    logger.info("Starting up Simulators Tools application")
    try:
        # Create SQL tables from ORM models if they do not exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (create_all executed)")
    except Exception as exc:
        logger.exception("Failed to create database tables on startup: %s", exc)
    # TODO: initialize other resources (HTTP clients, caches, telemetry)
    # Example placeholder:
    # app.state.db = create_db_engine(settings.sqlalchemy_database_url)
    # app.state.mongo = MongoClient(settings.mongodb_uri)
    pass


@app.on_event("shutdown")
async def on_shutdown():
    # TODO: gracefully close DB connections, HTTP clients, flush metrics
    logger.info("Shutting down Simulators Tools application")
    # Example placeholder:
    # if hasattr(app.state, 'db'):
    #     app.state.db.dispose()
    # if hasattr(app.state, 'mongo'):
    #     app.state.mongo.close()
    pass


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
