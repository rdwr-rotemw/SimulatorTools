from sqlalchemy.orm import declarative_base

# Shared declarative base for SQLAlchemy models in this package
Base = declarative_base()

__all__ = ["Base"]

