"""
002 — MVP: make spaces.user_id nullable and drop FK to users.

Root cause: the auth layer (users table + JWT) is not implemented yet,
but spaces.user_id was defined as NOT NULL FK → users.id. Any attempt to
create a space raised ForeignKeyViolationError because no user record exists.

Fix: drop the FK constraint and make the column nullable. The column is
preserved so that once auth is wired in (see TODO(auth) markers) a new
migration can restore the FK and back-fill user_id from session data.

Downgrade: restores the FK. Requires all spaces.user_id to be non-null;
run only when auth is fully implemented.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the FK constraint from spaces → users
    op.drop_constraint("spaces_user_id_fkey", "spaces", type_="foreignkey")

    # 2. Make user_id nullable (was NOT NULL)
    op.alter_column(
        "spaces", "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "spaces", "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    # Re-add FK
    op.create_foreign_key(
        "spaces_user_id_fkey",
        "spaces", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )
