from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.permission_id"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permission"),
    )

    # relationships
    role = relationship("Role", back_populates="role_permissions", overlaps="permissions,roles")
    permission = relationship("Permission", back_populates="role_permissions", overlaps="permissions,roles")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<RolePermission role_id={self.role_id} perm_id={self.permission_id}>"
