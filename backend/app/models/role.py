"""
Role ORM model.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # relationships
    # association to user_roles (association table)
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    # expose users via the user_roles secondary association
    users = relationship("User", secondary="user_roles", back_populates="roles", overlaps="user_roles")

    # explicit association to RolePermission for easier management
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles", overlaps="role_permissions")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Role id={self.role_id} name={self.role_name}>"
