"""
Helpers to verify seeded users/roles in the database.

Provides `verify_setup(db: Session)` which prints/logs details about the
`sapro_test` user, `sapro_admin` role, and existing UserRole association
entries.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.role import Role
from backend.app.models.user_role import UserRole

logger = logging.getLogger("sim-tools.db.verify_setup")


def verify_setup(db: Session) -> None:
    """Verify the presence and associations of seeded test data.

    This function queries for the `sapro_test` user, the `sapro_admin` role,
    and all `UserRole` entries. It prints and logs summary information.

    Per the requested behavior this function will attempt to commit and
    close the session when finished.
    """
    try:
        # Check user
        user = db.query(User).filter(User.username == "sapro_test").first()
        if user:
            role_names = [r.role_name for r in user.roles] if getattr(user, "roles", None) else []
            msg = f"User found: id={user.user_id}, username={user.username}, roles={role_names}"
            print(msg)
            logger.info(msg)
        else:
            msg = "User 'sapro_test' not found"
            print(msg)
            logger.warning(msg)

        # Check role
        role = db.query(Role).filter(Role.role_name == "sapro_admin").first()
        if role:
            msg = f"Role found: id={role.role_id}, name={role.role_name}"
            print(msg)
            logger.info(msg)
        else:
            msg = "Role 'sapro_admin' not found"
            print(msg)
            logger.warning(msg)

        # List UserRole entries
        entries = db.query(UserRole).all()
        count = len(entries)
        print(f"UserRole entries count: {count}")
        logger.info("UserRole entries count: %d", count)
        for ur in entries:
            print(f"- user_id={ur.user_id}, role_id={ur.role_id}")

        # Commit (no-op for reads, but requested) and close session
        try:
            db.commit()
        except Exception:
            logger.exception("Failed to commit during verify_setup (non-fatal)")
        try:
            db.close()
        except Exception:
            logger.exception("Failed to close DB session in verify_setup (non-fatal)")

    except Exception as exc:
        logger.exception("Unexpected error in verify_setup: %s", exc)
        print(f"Unexpected error in verify_setup: {exc}")
        # Best-effort rollback/close
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        raise
