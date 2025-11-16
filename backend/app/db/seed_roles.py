from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from backend.app.models.role import Role


def seed_roles(db: Session) -> None:
    """Ensure required roles exist in the database.

    - Creates the "admin" role if missing
    - Creates the "sapro_admin" role if missing

    The function commits its changes and prints a short summary. It
    handles database errors and performs a rollback on failure.
    """
    required: List[dict] = [
        {"role_name": "admin", "description": "Administrator with all privileges"},
        {"role_name": "sapro_admin", "description": "Sapro administrator - Sapro only, no CyberController"},
    ]

    created = []
    try:
        for r in required:
            existing = db.query(Role).filter(Role.role_name == r["role_name"]).first()
            if not existing:
                role = Role(role_name=r["role_name"], description=r.get("description"))
                db.add(role)
                created.append(r["role_name"])

        if created:
            try:
                db.commit()
                print(f"Roles seeded successfully: {', '.join(created)}")
            except IntegrityError:
                db.rollback()
                print("Roles seeding encountered integrity issues; rollback performed")
        else:
            print("Roles already exist; nothing to do")
    except SQLAlchemyError as exc:
        # Ensure rollback on any DB error
        try:
            db.rollback()
        except Exception:
            pass
        print(f"Failed to seed roles: {exc}")
        raise

