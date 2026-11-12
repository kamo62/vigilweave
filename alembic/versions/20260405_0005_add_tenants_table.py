"""Add first-class tenants table.

Revision ID: 20260405_0005
Revises: 20260405_0004
Create Date: 2026-04-05 03:15:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260405_0005"
down_revision: Union[str, None] = "20260405_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("billing_email", sa.String(), nullable=True),
        sa.Column("deployment_mode", sa.String(), nullable=False),
        sa.Column("plan_tier", sa.String(), nullable=False),
        sa.Column("billing_status", sa.String(), nullable=False),
        sa.Column("workos_org_id", sa.String(), nullable=True),
        sa.Column("paddle_customer_id", sa.String(), nullable=True),
        sa.Column("paddle_subscription_id", sa.String(), nullable=True),
        sa.Column("self_hosted_license_id", sa.Integer(), nullable=True),
        sa.Column("self_hosted_license_key_prefix", sa.String(), nullable=True),
        sa.Column("encrypted_self_hosted_license_key", sa.String(), nullable=True),
        sa.Column("self_hosted_license_status", sa.String(), nullable=True),
        sa.Column("self_hosted_last_fulfilled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=False)
    op.create_index(op.f("ix_tenants_workos_org_id"), "tenants", ["workos_org_id"], unique=False)
    op.create_index(
        op.f("ix_tenants_paddle_customer_id"), "tenants", ["paddle_customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_tenants_paddle_subscription_id"),
        "tenants",
        ["paddle_subscription_id"],
        unique=False,
    )

    connection = op.get_bind()
    now = datetime.now(UTC)
    user_rows = connection.execute(
        sa.text(
            "SELECT tenant_slug, MIN(email) AS billing_email, MIN(workos_org_id) AS workos_org_id "
            "FROM users WHERE tenant_slug IS NOT NULL AND tenant_slug != '' GROUP BY tenant_slug"
        )
    ).mappings()
    existing_slugs: set[str] = set()

    for row in user_rows:
        slug = str(row["tenant_slug"])
        existing_slugs.add(slug)
        connection.execute(
            sa.text(
                "INSERT INTO tenants (slug, display_name, billing_email, deployment_mode, plan_tier, billing_status, workos_org_id, created_at, updated_at) "
                "VALUES (:slug, :display_name, :billing_email, :deployment_mode, :plan_tier, :billing_status, :workos_org_id, :created_at, :updated_at)"
            ),
            {
                "slug": slug,
                "display_name": slug,
                "billing_email": row["billing_email"],
                "deployment_mode": "SAAS",
                "plan_tier": "COMMUNITY",
                "billing_status": "INACTIVE",
                "workos_org_id": row["workos_org_id"],
                "created_at": now,
                "updated_at": now,
            },
        )

    license_rows = connection.execute(
        sa.text("SELECT tenant_slug, tier FROM saas_tenant_licenses")
    ).mappings()
    for row in license_rows:
        slug = str(row["tenant_slug"])
        plan_tier = str(row["tier"] or "enterprise").upper()
        if slug in existing_slugs:
            connection.execute(
                sa.text(
                    "UPDATE tenants SET plan_tier = :plan_tier, billing_status = :billing_status, updated_at = :updated_at WHERE slug = :slug"
                ),
                {
                    "slug": slug,
                    "plan_tier": plan_tier,
                    "billing_status": "MANUAL",
                    "updated_at": now,
                },
            )
            continue

        connection.execute(
            sa.text(
                "INSERT INTO tenants (slug, display_name, deployment_mode, plan_tier, billing_status, created_at, updated_at) "
                "VALUES (:slug, :display_name, :deployment_mode, :plan_tier, :billing_status, :created_at, :updated_at)"
            ),
            {
                "slug": slug,
                "display_name": slug,
                "deployment_mode": "SAAS",
                "plan_tier": plan_tier,
                "billing_status": "MANUAL",
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_paddle_subscription_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_paddle_customer_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_workos_org_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")
