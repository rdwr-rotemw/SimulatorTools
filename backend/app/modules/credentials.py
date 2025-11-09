"""
SQLAlchemy model for CyberController credentials.

Fields:
- id: primary key
- cc_ip: IP of CyberController (unique)
- cc_host: host (optional)
- cc_port: integer
- username: login
- encrypted_password: encrypted or hashed storage (note: encryption recommended)
- created_at, updated_at
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from backend.app.modules.base import Base


class Credentials(Base):
    __tablename__ = "cc_credentials"

    id = Column(Integer, primary_key=True, index=True)
    cc_ip = Column(String(45), unique=True, nullable=False, index=True)
    cc_host = Column(String(200), nullable=True)
    cc_port = Column(Integer, default=443, nullable=False)

    username = Column(String(200), nullable=False)
    # Store encrypted password or an identifier to a secrets manager
    encrypted_password = Column(String(1024), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<CCCredentials id={self.id} cc_ip={self.cc_ip} user={self.username}>"
