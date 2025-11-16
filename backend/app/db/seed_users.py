"""
Database seeding helpers for users.

Provides `seed_test_user(db: Session)` which ensures a test user `sapro_test`
exists and is linked to the `sapro_admin` role.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.utils.auth import hash_password
from backend.app.models.user import User
from backend.app.models.role import Role
from backend.app.models.user_role import UserRole

logger = logging.getLogger("sim-tools.db.seed_users")


def seed_test_user(db: Session) -> Optional[User]:
    """Ensure a test user exists and is assigned the `sapro_admin` role.

    Args:
        db: SQLAlchemy Session (short-lived session provided by caller)

    Returns:
        The created or existing User instance on success.

    Raises:
        ValueError: if the required role `sapro_admin` does not exist.
        Exception: re-raises unexpected exceptions after rolling back the session.
    """
    username = "sapro_test"
    password = "testpass123"

    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            msg = "Test user already exists"
            print(msg)
            logger.info(msg)
            return existing

        # Ensure role exists
        role = db.query(Role).filter(Role.role_name == "sapro_admin").first()
        if not role:
            msg = "Role 'sapro_admin' not found; cannot create test user"
            print(msg)
            logger.error(msg)
            raise ValueError(msg)

        # Create user with hashed password
        password_hash = hash_password(password)
        user = User(username=username, password_hash=password_hash)
        db.add(user)
        # Flush to populate user.user_id for the association
        db.flush()

        # Link user to role
        user_role = UserRole(user_id=user.user_id, role_id=role.role_id)
        db.add(user_role)

        # Commit transaction
        db.commit()

        msg = "Test user created"
        print(msg)
        logger.info(msg)
        return user
    except Exception as exc:
        # Rollback any partial changes and re-raise after logging
        try:
            db.rollback()
        except Exception:
            # Best-effort rollback; ignore rollback failures
            pass
        logger.exception("Failed to seed test user: %s", exc)
        print(f"Failed to seed test user: {exc}")
        raise

