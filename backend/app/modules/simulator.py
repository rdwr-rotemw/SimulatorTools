"""
SQLAlchemy model for simulator metadata.

Fields:
- id: primary key
- ip_address: unique ip
- name: display name
- type: simulator type
- cc_ip: foreign key referencing CyberController (if used)
- status: status string
- created_at: timestamp
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from backend.app.modules.base import Base


class Simulator(Base):
    __tablename__ = "simulators"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    type = Column(String(100), nullable=True)

    # Optionally reference a CyberController by its IP or id
    cc_ip = Column(String(45), nullable=True)

    status = Column(String(50), default="unknown", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Simulator id={self.id} ip={self.ip_address} status={self.status}>"
