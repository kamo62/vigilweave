"""Billing and Paddle webhook persistence models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.tenant_license import SaaSTenantTier


class BillingProvider(StrEnum):
    """Supported billing backends."""

    PADDLE = "paddle"


class BillingCustomer(SQLModel, table=True):
    """Provider customer record linked to a VigilWeave tenant."""

    __tablename__ = "billing_customers"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_customer_id", name="uq_billing_customers_provider_customer"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    provider: BillingProvider = Field(default=BillingProvider.PADDLE, index=True)
    provider_customer_id: str = Field(index=True)
    tenant_slug: str | None = Field(default=None, index=True)
    email: str | None = None
    name: str | None = None
    status: str | None = None
    custom_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BillingSubscription(SQLModel, table=True):
    """Provider subscription synced into the local control plane."""

    __tablename__ = "billing_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_billing_subscriptions_provider_subscription",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    provider: BillingProvider = Field(default=BillingProvider.PADDLE, index=True)
    provider_subscription_id: str = Field(index=True)
    provider_customer_id: str | None = Field(default=None, index=True)
    tenant_slug: str | None = Field(default=None, index=True)
    plan_tier: SaaSTenantTier | None = Field(default=None)
    status: str | None = None
    collection_mode: str | None = None
    currency_code: str | None = None
    price_id: str | None = None
    custom_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime | None = None
    first_billed_at: datetime | None = None
    next_billed_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BillingEvent(SQLModel, table=True):
    """Idempotent storage for provider billing events."""

    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_billing_events_provider_event"),
    )

    id: int | None = Field(default=None, primary_key=True)
    provider: BillingProvider = Field(default=BillingProvider.PADDLE, index=True)
    provider_event_id: str = Field(index=True)
    event_type: str = Field(index=True)
    tenant_slug: str | None = Field(default=None, index=True)
    processing_status: str = Field(default="processed")
    occurred_at: datetime | None = Field(default=None, index=True)
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    response_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = Field(default=None)


class PaddleBillingPublicConfig(SQLModel):
    """Public Paddle configuration exposed to the marketing/app frontend."""

    provider: Literal["paddle"] = "paddle"
    enabled: bool
    environment: Literal["sandbox", "production"]
    client_token: str | None = None
    checkout_ready: bool
    pro_price_id: str | None = None
    enterprise_price_id: str | None = None
    default_success_url: str
    webhook_url: str


class BillingSubscriptionPublic(SQLModel):
    """Tenant-scoped billing subscription summary."""

    provider_subscription_id: str
    tenant_slug: str | None = None
    plan_tier: SaaSTenantTier | None = None
    status: str | None = None
    collection_mode: str | None = None
    currency_code: str | None = None
    price_id: str | None = None
    next_billed_at: datetime | None = None
    canceled_at: datetime | None = None
    updated_at: datetime


class BillingPortalSessionPublic(SQLModel):
    """Authenticated Paddle customer portal links for a tenant."""

    customer_id: str
    session_id: str
    overview_url: str | None = None
    subscription_urls: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


class PaddleWebhookIngestResponse(SQLModel):
    """Result of processing a Paddle webhook event."""

    accepted: bool = True
    event_id: str
    event_type: str
    tenant_slug: str | None = None
    message: str
