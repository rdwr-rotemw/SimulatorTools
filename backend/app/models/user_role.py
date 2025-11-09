"""
Association table UserRole: links User and Role.
"""
from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from backend.app.utils.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "role_id", name="pk_user_role"),
    )

    # relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"

