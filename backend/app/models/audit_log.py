"""
Audit log ORM model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    action = Column(String(200), nullable=False)
    resource = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(45), nullable=True)

    # relationship back to user
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<AuditLog id={self.log_id} user_id={self.user_id} action={self.action}>"

