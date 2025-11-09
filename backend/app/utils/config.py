from __future__ import annotations

"""
Application configuration using Pydantic BaseSettings (pydantic-settings).

Loads values from environment variables and a local `.env` file. Provides
helpers to build SQLAlchemy/Postgres and MongoDB connection URLs, and
normalizes CORS origins.
"""
from functools import lru_cache
from typing import List, Optional, Union
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Environment
    ENV: str = Field("development", description="Runtime environment")
    DEBUG: bool = Field(False, description="Enable debug mode")

    # PostgreSQL settings
    PG_HOST: str = Field("localhost", description="Postgres host")
    PG_PORT: int = Field(5432, description="Postgres port")
    PG_DB: str = Field("simulators", description="Postgres database name")
    PG_USER: Optional[str] = Field(None, description="Postgres username")
    PG_PASSWORD: Optional[str] = Field(None, description="Postgres password")

    # MongoDB settings: prefer full URI if provided, otherwise build from parts
    MONGO_URI: Optional[str] = Field(None, description="Full MongoDB URI (optional)")
    MONGO_HOST: str = Field("localhost", description="MongoDB host")
    MONGO_PORT: int = Field(27017, description="MongoDB port")
    MONGO_DB: str = Field("simulators", description="MongoDB database name")
    MONGO_USER: Optional[str] = Field(None, description="MongoDB username")
    MONGO_PASSWORD: Optional[str] = Field(None, description="MongoDB password")

    # JWT / Auth
    JWT_SECRET_KEY: str = Field("CHANGE_ME_REPLACE_IN_PROD", description="JWT secret key")
    JWT_ALGORITHM: str = Field("HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, description="Access token expiry in minutes")

    # CORS origins: accept a comma-separated string or a list
    # Default includes localhost for dev and a placeholder for production
    CORS_ORIGINS: Union[str, List[str]] = Field(
        "http://localhost:3000,https://your.production.domain",
        description="Comma-separated list or JSON list of allowed CORS origins",
    )

    # API settings
    BACKEND_PORT: int = Field(8000, description="Backend port for local dev/routing")
    API_BASE_URL: str = Field("http://localhost:8000", description="Base URL of the API")

    # Logging
    LOG_LEVEL: str = Field("INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR)")

    # pydantic v2 settings: load from .env by default
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Validators
    @field_validator("CORS_ORIGINS", mode="before")
    def _parse_cors_origins(cls, v):
        """Normalize CORS_ORIGINS into a Python list of origins."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Allow both comma-separated and JSON-like list strings
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                if not inner:
                    return []
                return [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            return [x.strip() for x in v.split(",") if x.strip()]
        return []

    def sqlalchemy_database_url(self) -> str:
        """Return a SQLAlchemy-compatible Postgres URL using psycopg2.

        Examples:
          postgresql+psycopg2://user:pass@host:port/db
        """
        host = self.PG_HOST
        port = self.PG_PORT
        db = self.PG_DB
        user = self.PG_USER
        password = self.PG_PASSWORD

        if user and password:
            u = quote_plus(user)
            p = quote_plus(password)
            return f"postgresql+psycopg2://{u}:{p}@{host}:{port}/{db}"
        return f"postgresql+psycopg2://{host}:{port}/{db}"

    def mongodb_uri(self) -> str:
        """Return a MongoDB URI. If `MONGO_URI` is set, return it; otherwise build one."""
        if self.MONGO_URI:
            return self.MONGO_URI
        host = self.MONGO_HOST
        port = self.MONGO_PORT
        db = self.MONGO_DB
        user = self.MONGO_USER
        password = self.MONGO_PASSWORD

        if user and password:
            u = quote_plus(user)
            p = quote_plus(password)
            return f"mongodb://{u}:{p}@{host}:{port}/{db}"
        return f"mongodb://{host}:{port}/{db}"


# Cached accessor
@lru_cache()
def get_settings() -> Settings:
    """Return a cached `Settings` instance to be used across the app."""
    return Settings()


settings = get_settings()


__all__ = ["Settings", "get_settings", "settings"]
