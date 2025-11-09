"""
Database connection infrastructure for the backend.

This module creates a SQLAlchemy Engine and SessionLocal using the
Postgres URL provided by `settings.sqlalchemy_database_url()`, and a
MongoDB client using `settings.mongodb_uri()`. It exposes FastAPI
dependency helpers for obtaining DB sessions and the MongoDB database
object, as well as simple connection verification helpers.

Notes:
- No models or tables are created here; this is purely connection
  infrastructure.
- The engine and clients are created at import time; in production you
  may prefer to initialize them in the application's startup event and
  close them on shutdown.
"""
from __future__ import annotations

import logging
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from pymongo import MongoClient, errors as pymongo_errors

from backend.app.utils.config import settings

# Add declarative base for ORM models
from sqlalchemy.orm import declarative_base
Base = declarative_base()

logger = logging.getLogger("sim-tools.db")

# --- SQLAlchemy setup -----------------------------------------------------
# Build SQLAlchemy engine using the Postgres URL from settings
SQLALCHEMY_DATABASE_URL = settings.sqlalchemy_database_url()

# Create engine with connection pooling parameters
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    future=True,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy Session and closes it
    after use.

    Usage:
        def endpoint(db: Session = Depends(get_db)):
            # use db
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- MongoDB setup -------------------------------------------------------
MONGO_URI = settings.mongodb_uri()
mongo_client = MongoClient(MONGO_URI)

def get_mongo_db() -> "pymongo.database.Database":
    """Return the configured MongoDB database instance.

    Uses `settings.MONGO_DB` as the database name.
    """
    db_name = getattr(settings, "MONGO_DB", None) or "admin"
    return mongo_client[db_name]


# --- Connection verification / health checks -----------------------------
def verify_postgres_connection(timeout_seconds: int = 5) -> bool:
    """Try a simple SELECT 1 query to validate Postgres connectivity.

    Returns True when the DB responds, or raises the underlying exception
    for the caller to handle/log.
    """
    try:
        with engine.connect() as conn:
            # Use a lightweight text query
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.exception("Postgres connection verification failed: %s", exc)
        raise


def verify_mongo_connection() -> bool:
    """Ping the MongoDB server to verify connectivity.

    Returns True on success or raises the underlying exception.
    """
    try:
        # The `admin.command('ping')` call will raise on failure
        mongo_client.admin.command("ping")
        return True
    except pymongo_errors.PyMongoError as exc:
        logger.exception("MongoDB connection verification failed: %s", exc)
        raise


def check_databases() -> dict:
    """Perform lightweight checks for both Postgres and MongoDB and return
    a summary dict with boolean statuses. Exceptions from individual
    checks will be captured and returned as error messages.
    """
    result: dict = {"postgres": None, "mongodb": None}

    try:
        result["postgres"] = verify_postgres_connection()
    except Exception as e:  # pragma: no cover - runtime environment dependent
        result["postgres"] = str(e)

    try:
        result["mongodb"] = verify_mongo_connection()
    except Exception as e:  # pragma: no cover - runtime environment dependent
        result["mongodb"] = str(e)

    return result


__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "mongo_client",
    "get_mongo_db",
    "verify_postgres_connection",
    "verify_mongo_connection",
    "check_databases",
    "Base",
]
