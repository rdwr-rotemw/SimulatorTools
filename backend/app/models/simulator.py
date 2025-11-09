"""
Simulator ORM model.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class Simulator(Base):
    __tablename__ = "simulators"

    ip_address = Column(String(45), primary_key=True, index=True)
    type = Column(String(100), nullable=True)
    map = Column(String(200), nullable=True)

    # reference to CyberController credentials (by cc_ip)
    cc_ip = Column(String(45), ForeignKey("cc_credentials.cc_ip"), nullable=True)
    cc_credentials = relationship("CCCredentials", back_populates="simulators")

    status = Column(String(50), default="unknown", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Simulator ip={self.ip_address} type={self.type} status={self.status}>"

