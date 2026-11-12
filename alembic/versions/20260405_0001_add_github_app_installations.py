"""Add tenant GitHub App installations and project repo bindings.

Revision ID: 20260405_0001
Revises: 20260324_0001
Create Date: 2026-04-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260405_0001"
down_revision: Union[str, None] = "20260324_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_github_installations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("installation_id", sa.Integer(), nullable=False),
        sa.Column("account_login", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=True),
        sa.Column("account_avatar_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_tenant_github_installations_tenant_slug"),
        "tenant_github_installations",
        ["tenant_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_github_installations_installation_id"),
        "tenant_github_installations",
        ["installation_id"],
        unique=True,
    )

    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.add_column(sa.Column("github_installation_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f("ix_project_repositories_github_installation_id"),
            ["github_installation_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.drop_index(op.f("ix_project_repositories_github_installation_id"))
        batch_op.drop_column("github_installation_id")

    op.drop_index(
        op.f("ix_tenant_github_installations_installation_id"),
        table_name="tenant_github_installations",
    )
    op.drop_index(
        op.f("ix_tenant_github_installations_tenant_slug"),
        table_name="tenant_github_installations",
    )
    op.drop_table("tenant_github_installations")
