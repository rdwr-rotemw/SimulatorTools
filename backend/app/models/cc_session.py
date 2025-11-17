"""
CyberController Session model.

Tracks active JSESSIONID sessions for CyberController instances.
Each session is associated with a user and a specific CC instance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base

if TYPE_CHECKING:
    from backend.app.models.user import User


class CCSession(Base):
    """CyberController session tracking model.

    Stores active JSESSIONID sessions for CyberController instances,
    allowing users to maintain persistent sessions without re-authenticating.
    """

    __tablename__ = "cc_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cc_ip = Column(String(255), nullable=False, index=True)
    jsession_id = Column(String(512), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    login_time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_activity = Column(DateTime, nullable=True)

    # Relationship to User
    user = relationship("User", back_populates="cc_sessions")

    def __repr__(self) -> str:
        return f"<CCSession(id={self.id}, cc_ip={self.cc_ip}, user_id={self.user_id})>"

