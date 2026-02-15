"""
Fix admin user workspace to '*' (all workspaces).

This script updates the admin user's workspace from NULL to '*'
to enable proper workspace filtering and auto-detection.
"""
from sqlalchemy import create_engine, text
from backend.app.utils.config import settings

def fix_admin_workspace():
    """Update admin user workspace to '*'."""
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Update admin user workspace to '*'
        result = conn.execute(
            text("UPDATE users SET workspace = '*' WHERE username = 'admin'")
        )
        conn.commit()

        print(f"Updated {result.rowcount} admin user(s)")

        # Verify the update
        admin = conn.execute(
            text("SELECT user_id, username, workspace FROM users WHERE username = 'admin'")
        ).fetchone()

        if admin:
            print(f"Admin user: ID={admin[0]}, username={admin[1]}, workspace={admin[2]}")
        else:
            print("Admin user not found!")

if __name__ == "__main__":
    fix_admin_workspace()
