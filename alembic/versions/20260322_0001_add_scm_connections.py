"""Add SCM connections table and FK on project_repositories

Revision ID: 20260322_0001
Revises: 20260320_0001
Create Date: 2026-03-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260322_0001"
down_revision: Union[str, None] = "20260320_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scm_connections table and add FK to project_repositories."""

    op.create_table(
        "scm_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_slug", sa.String(), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("encrypted_token", sa.String(), nullable=False),
        sa.Column("extra_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
    )

    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.add_column(
            sa.Column("scm_connection_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_project_repos_scm_connection",
            "scm_connections",
            ["scm_connection_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Drop scm_connections table and FK from project_repositories."""

    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.drop_constraint("fk_project_repos_scm_connection", type_="foreignkey")
        batch_op.drop_column("scm_connection_id")

    op.drop_table("scm_connections")
