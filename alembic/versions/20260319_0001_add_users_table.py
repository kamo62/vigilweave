"""Add users table for SaaS authentication

Revision ID: 20260319_0001
Revises: 20260318_0002
Create Date: 2026-03-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260319_0001"
down_revision: Union[str, None] = "20260318_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table for SaaS authentication."""

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workos_user_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("tenant_slug", sa.String(), nullable=False, server_default="default"),
        sa.Column("workos_org_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_users_workos_user_id"), "users", ["workos_user_id"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_tenant_slug"), "users", ["tenant_slug"], unique=False)
    op.create_index(op.f("ix_users_workos_org_id"), "users", ["workos_org_id"], unique=False)


def downgrade() -> None:
    """Drop users table."""

    op.drop_index(op.f("ix_users_workos_org_id"), table_name="users")
    op.drop_index(op.f("ix_users_tenant_slug"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_workos_user_id"), table_name="users")
    op.drop_table("users")
