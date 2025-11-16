"""
Simulator ORM model.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from backend.app.utils.database import Base


class Simulator(Base):
    __tablename__ = "simulators"

    # Primary key - IP address of the simulator
    ip_address = Column(String(45), primary_key=True, index=True)
    # Device type (e.g., "Alteons", "DefensePros", ...)
    type = Column(String(100), nullable=True)
    # Device version (optional, stored as string)
    version = Column(String(100), nullable=True)
    # Map or profile name associated with this simulator
    map = Column(String(200), nullable=True)

    # Current status (e.g., running/stopped/unknown)
    status = Column(String(50), default="unknown", nullable=False)

    # Creation timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Simulator ip={self.ip_address} type={self.type} status={self.status}>"
