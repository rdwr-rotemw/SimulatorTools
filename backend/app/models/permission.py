from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(Integer, primary_key=True, index=True)
    permission_name = Column(String(150), unique=True, nullable=False)
    resource = Column(String(200), nullable=True)
    action = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions", overlaps="role_permissions")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Permission id={self.permission_id} name={self.permission_name}>"
