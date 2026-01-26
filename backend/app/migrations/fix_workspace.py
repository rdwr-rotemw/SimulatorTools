"""Production migration script - reads from .env file."""
import psycopg2
import sys
import os
from pathlib import Path

def load_env():
    """Load .env file from backend directory."""
    env_path = Path(__file__).parent.parent / '.env'

    if not env_path.exists():
        print(f"❌ .env file not found at {env_path}")
        sys.exit(1)

    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value

    return env_vars

def add_workspace_column():
    """Add workspace column to users table."""
    # Load environment variables
    env = load_env()

    host = env.get('PG_HOST', 'localhost')
    port = int(env.get('PG_PORT', 5432))
    database = env.get('PG_DB', 'simulators')
    user = env.get('PG_USER', 'postgres')
    password = env.get('PG_PASSWORD', '')

    print(f"Connecting to {host}:{port}/{database} as {user}...")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        print("✅ Connected")

        cursor = conn.cursor()

        print("\nAdding workspace column...")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS workspace VARCHAR(255)")
        print("✅ Column added (or already exists)")

        print("\nSetting admin workspace to '*'...")
        cursor.execute("UPDATE users SET workspace = '*' WHERE username = 'admin'")
        rows_updated = cursor.rowcount
        print(f"✅ Admin workspace set ({rows_updated} row(s) updated)")

        print("\nSetting other users to 'default'...")
        cursor.execute("UPDATE users SET workspace = 'default' WHERE username != 'admin' AND workspace IS NULL")
        rows_updated = cursor.rowcount
        print(f"✅ Updated {rows_updated} user(s) to default workspace")

        conn.commit()
        print("\n" + "="*50)
        print("✅ Production migration completed successfully!")
        print("="*50)

    except psycopg2.OperationalError as e:
        print(f"❌ Database connection error: {e}")
        sys.exit(1)
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"❌ Migration error: {e}")
        sys.exit(1)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    add_workspace_column()