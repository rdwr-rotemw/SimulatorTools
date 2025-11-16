"""
CyberController Credentials ORM model.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime

from backend.app.utils.database import Base


class CCCredentials(Base):
    __tablename__ = "cc_credentials"

    cc_ip = Column(String(45), primary_key=True, index=True)
    cc_host = Column(String(200), nullable=True)
    cc_port = Column(Integer, default=443, nullable=False)

    username = Column(String(200), nullable=False)
    encrypted_password = Column(String(1024), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<CCCredentials cc_ip={self.cc_ip} user={self.username}>"
