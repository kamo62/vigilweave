"""First-class tenant records for hosted and self-hosted commercial flows."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.tenant_license import SaaSTenantTier


class TenantDeploymentMode(StrEnum):
    """Deployment shape for a tenant."""

    SAAS = "saas"
    SELF_HOSTED = "self_hosted"


class TenantBillingStatus(StrEnum):
    """Normalized billing lifecycle snapshot for a tenant."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    TRIALING = "trialing"
    PAUSED = "paused"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    MANUAL = "manual"


class Tenant(SQLModel, table=True):
    """Tenant metadata tracked independently from users and subscriptions."""

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    display_name: str = Field(default="Unnamed Tenant")
    billing_email: str | None = None
    deployment_mode: TenantDeploymentMode = Field(default=TenantDeploymentMode.SAAS)
    plan_tier: SaaSTenantTier = Field(default=SaaSTenantTier.COMMUNITY)
    billing_status: TenantBillingStatus = Field(default=TenantBillingStatus.INACTIVE)
    workos_org_id: str | None = Field(default=None, index=True)
    paddle_customer_id: str | None = Field(default=None, index=True)
    paddle_subscription_id: str | None = Field(default=None, index=True)
    self_hosted_license_id: int | None = None
    self_hosted_license_key_prefix: str | None = None
    encrypted_self_hosted_license_key: str | None = None
    self_hosted_license_status: str | None = None
    self_hosted_last_fulfilled_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantPublic(SQLModel):
    """Current tenant summary exposed through billing/admin APIs."""

    slug: str
    display_name: str
    billing_email: str | None = None
    deployment_mode: TenantDeploymentMode
    plan_tier: SaaSTenantTier
    billing_status: TenantBillingStatus
    workos_org_id: str | None = None
    paddle_customer_id: str | None = None
    paddle_subscription_id: str | None = None
    self_hosted_license_id: int | None = None
    self_hosted_license_key_prefix: str | None = None
    self_hosted_license_status: str | None = None
    self_hosted_last_fulfilled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SelfHostedLicensePublic(SQLModel):
    """Tenant-admin view of an issued self-hosted commercial key."""

    tenant_slug: str
    license_id: int | None = None
    key_prefix: str | None = None
    status: str | None = None
    license_key: str | None = None
    last_fulfilled_at: datetime | None = None
