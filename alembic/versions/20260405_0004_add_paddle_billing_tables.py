"""Add Paddle billing sync tables.

Revision ID: 20260405_0004
Revises: 20260405_0003
Create Date: 2026-04-05 02:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260405_0004"
down_revision: Union[str, None] = "20260405_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_customer_id", sa.String(), nullable=False),
        sa.Column("tenant_slug", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("custom_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "provider", "provider_customer_id", name="uq_billing_customers_provider_customer"
        ),
    )
    op.create_index(
        op.f("ix_billing_customers_provider"), "billing_customers", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_billing_customers_provider_customer_id"),
        "billing_customers",
        ["provider_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_customers_tenant_slug"), "billing_customers", ["tenant_slug"], unique=False
    )

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subscription_id", sa.String(), nullable=False),
        sa.Column("provider_customer_id", sa.String(), nullable=True),
        sa.Column("tenant_slug", sa.String(), nullable=True),
        sa.Column("plan_tier", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("collection_mode", sa.String(), nullable=True),
        sa.Column("currency_code", sa.String(), nullable=True),
        sa.Column("price_id", sa.String(), nullable=True),
        sa.Column("custom_data", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("first_billed_at", sa.DateTime(), nullable=True),
        sa.Column("next_billed_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_billing_subscriptions_provider_subscription",
        ),
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider"),
        "billing_subscriptions",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_subscription_id"),
        "billing_subscriptions",
        ["provider_subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_customer_id"),
        "billing_subscriptions",
        ["provider_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_tenant_slug"),
        "billing_subscriptions",
        ["tenant_slug"],
        unique=False,
    )

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("tenant_slug", sa.String(), nullable=True),
        sa.Column("processing_status", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_billing_events_provider_event"
        ),
    )
    op.create_index(
        op.f("ix_billing_events_provider"), "billing_events", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_billing_events_provider_event_id"),
        "billing_events",
        ["provider_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_events_event_type"), "billing_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_billing_events_tenant_slug"), "billing_events", ["tenant_slug"], unique=False
    )
    op.create_index(
        op.f("ix_billing_events_occurred_at"), "billing_events", ["occurred_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_events_occurred_at"), table_name="billing_events")
    op.drop_index(op.f("ix_billing_events_tenant_slug"), table_name="billing_events")
    op.drop_index(op.f("ix_billing_events_event_type"), table_name="billing_events")
    op.drop_index(op.f("ix_billing_events_provider_event_id"), table_name="billing_events")
    op.drop_index(op.f("ix_billing_events_provider"), table_name="billing_events")
    op.drop_table("billing_events")

    op.drop_index(op.f("ix_billing_subscriptions_tenant_slug"), table_name="billing_subscriptions")
    op.drop_index(
        op.f("ix_billing_subscriptions_provider_customer_id"), table_name="billing_subscriptions"
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_provider_subscription_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(op.f("ix_billing_subscriptions_provider"), table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")

    op.drop_index(op.f("ix_billing_customers_tenant_slug"), table_name="billing_customers")
    op.drop_index(op.f("ix_billing_customers_provider_customer_id"), table_name="billing_customers")
    op.drop_index(op.f("ix_billing_customers_provider"), table_name="billing_customers")
    op.drop_table("billing_customers")
