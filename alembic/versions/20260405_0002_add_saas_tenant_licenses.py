"""Add hosted SaaS tenant license overrides.

Revision ID: 20260405_0002
Revises: 20260405_0001
Create Date: 2026-04-05 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260405_0002"
down_revision: Union[str, None] = "20260405_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saas_tenant_licenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("assigned_by", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_slug", name="uq_saas_tenant_licenses_tenant_slug"),
    )
    op.create_index(
        op.f("ix_saas_tenant_licenses_tenant_slug"),
        "saas_tenant_licenses",
        ["tenant_slug"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_saas_tenant_licenses_tenant_slug"), table_name="saas_tenant_licenses")
    op.drop_table("saas_tenant_licenses")
