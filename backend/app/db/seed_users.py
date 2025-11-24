"""
Database seeding helpers for users.

Provides `seed_test_user(db: Session)` which ensures a test user `sapro_test`
exists and is linked to the `sapro_admin` role.

Provides `seed_cc_admin_user(db: Session)` which ensures a test user `cc_test`
exists and is linked to the `cc_admin` role.

Provides `seed_admin_user(db: Session, username, password=None, password_hash=None)`
which creates an `admin` user if not already present. If `password_hash` is
provided it will be used directly; otherwise `password` will be hashed.
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


def seed_cc_admin_user(db: Session) -> Optional[User]:
    """Ensure a CC admin test user exists and is assigned the `cc_admin` role.

    Args:
        db: SQLAlchemy Session (short-lived session provided by caller)

    Returns:
        The created or existing User instance on success.

    Raises:
        ValueError: if the required role `cc_admin` does not exist.
        Exception: re-raises unexpected exceptions after rolling back the session.
    """
    username = "cc_test"
    password = "testpass123"

    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            msg = "CC admin user already exists"
            print(msg)
            logger.info(msg)
            return existing

        # Ensure role exists
        role = db.query(Role).filter(Role.role_name == "cc_admin").first()
        if not role:
            msg = "Role 'cc_admin' not found; cannot create CC admin user"
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

        msg = "CC admin user created"
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
        logger.exception("Failed to seed CC admin user: %s", exc)
        print(f"Failed to seed CC admin user: {exc}")
        raise


def seed_admin_user(db: Session, username: str, password: Optional[str] = None, password_hash: Optional[str] = None) -> Optional[User]:
    """Create an admin user if not already present.

    Args:
        db: SQLAlchemy Session
        username: username to create
        password: plaintext password (will be hashed) - optional if password_hash provided
        password_hash: precomputed Argon2 password hash (preferred)

    Returns:
        The created or existing User instance on success.

    Notes:
        - This function is idempotent: if a user with the given username exists,
          it will return the existing user and will not alter roles.
        - It expects the `admin` role to already exist (seed_roles should run first).
    """
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            msg = f"Admin user '{username}' already exists"
            logger.info(msg)
            print(msg)
            return existing

        # Ensure admin role exists
        role = db.query(Role).filter(Role.role_name == "admin").first()
        if not role:
            msg = "Role 'admin' not found; cannot create admin user"
            logger.error(msg)
            print(msg)
            raise ValueError(msg)

        # Compute password hash
        if password_hash:
            phash = password_hash
        elif password:
            phash = hash_password(password)
        else:
            raise ValueError("Either password or password_hash must be provided to create admin user")

        user = User(username=username, password_hash=phash)
        db.add(user)
        db.flush()

        user_role = UserRole(user_id=user.user_id, role_id=role.role_id)
        db.add(user_role)
        db.commit()

        msg = f"Admin user '{username}' created"
        logger.info(msg)
        print(msg)
        return user

    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("Failed to seed admin user: %s", exc)
        print(f"Failed to seed admin user: {exc}")
        raise
