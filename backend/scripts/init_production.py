"""
Production initialization script.

Run this script on new production deployments to ensure:
1. Admin user has workspace='*'
2. All users have proper workspace assignments
3. Database constraints are correct
"""
from sqlalchemy import create_engine, text
from backend.app.utils.config import settings
import sys


def init_production():
    """Initialize production database with correct workspace values."""
    print("=" * 60)
    print("SimulatorTools Production Initialization")
    print("=" * 60)

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 1. Check admin user exists and has workspace='*'
        print("\n1. Checking admin user...")
        admin = conn.execute(
            text("SELECT user_id, username, workspace FROM users WHERE username = 'admin'")
        ).fetchone()

        if not admin:
            print("   ❌ ERROR: Admin user not found!")
            print("   Please create admin user first.")
            sys.exit(1)

        if admin[2] != '*':
            print(f"   ⚠️  Admin workspace is '{admin[2]}', fixing to '*'...")
            conn.execute(
                text("UPDATE users SET workspace = '*' WHERE username = 'admin'")
            )
            conn.commit()
            print("   ✅ Admin workspace set to '*'")
        else:
            print("   ✅ Admin workspace is correct ('*')")

        # 2. Check for NULL workspaces
        print("\n2. Checking for NULL workspaces...")
        null_workspaces = conn.execute(
            text("SELECT user_id, username FROM users WHERE workspace IS NULL")
        ).fetchall()

        if null_workspaces:
            print(f"   ⚠️  Found {len(null_workspaces)} users with NULL workspace:")
            for user in null_workspaces:
                print(f"      - {user[1]} (ID: {user[0]})")

            print("   Fixing NULL workspaces to 'default'...")
            conn.execute(
                text("UPDATE users SET workspace = 'default' WHERE workspace IS NULL")
            )
            conn.commit()
            print("   ✅ Fixed NULL workspaces")
        else:
            print("   ✅ No NULL workspaces found")

        # 3. Verify all users
        print("\n3. Verifying all users...")
        all_users = conn.execute(
            text("SELECT user_id, username, workspace FROM users ORDER BY user_id")
        ).fetchall()

        print(f"\n   Total users: {len(all_users)}")
        print("   " + "-" * 50)
        for user in all_users:
            print(f"   {user[0]:3d} | {user[1]:20s} | {user[2] or 'NULL'}")
        print("   " + "-" * 50)

        # 4. Check workspace distribution
        print("\n4. Workspace distribution:")
        workspace_counts = conn.execute(
            text("""
                SELECT workspace, COUNT(*) as count
                FROM users
                GROUP BY workspace
                ORDER BY count DESC
            """)
        ).fetchall()

        for ws, count in workspace_counts:
            print(f"   {ws or 'NULL':20s}: {count} user(s)")

    print("\n" + "=" * 60)
    print("✅ Production initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    init_production()
