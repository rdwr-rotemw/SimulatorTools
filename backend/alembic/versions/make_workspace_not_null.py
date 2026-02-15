"""Make workspace column NOT NULL with default values

Revision ID: workspace_not_null
Revises:
Create Date: 2026-02-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'workspace_not_null'
down_revision = None  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # First, set default values for any existing NULL workspaces
    op.execute("""
        UPDATE users
        SET workspace = CASE
            WHEN username = 'admin' THEN '*'
            ELSE 'default'
        END
        WHERE workspace IS NULL
    """)

    # Now make the column NOT NULL with a default value
    op.alter_column('users', 'workspace',
                    existing_type=sa.String(255),
                    nullable=False,
                    server_default='default')


def downgrade():
    # Remove NOT NULL constraint and default
    op.alter_column('users', 'workspace',
                    existing_type=sa.String(255),
                    nullable=True,
                    server_default=None)
