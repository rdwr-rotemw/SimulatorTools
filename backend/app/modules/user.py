"""
SQLAlchemy model for application users.

Fields:
- id: primary key
- username: unique username
- email: unique email
- password_hash: hashed password
- is_active: boolean
- created_at, updated_at: timestamps
- role: simple role string (admin/operator/viewer)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from backend.app.modules.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(50), default="viewer", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<User id={self.id} username={self.username} email={self.email}>"
