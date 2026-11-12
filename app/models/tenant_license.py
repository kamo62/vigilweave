"""Tenant-scoped SaaS license overrides for VigilWeave cloud."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SaaSTenantTier(StrEnum):
    """Commercial tier assigned to a hosted SaaS tenant."""

    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SaaSTenantLicense(SQLModel, table=True):
    """Explicit hosted SaaS tier override for a tenant."""

    __tablename__ = "saas_tenant_licenses"
    __table_args__ = (UniqueConstraint("tenant_slug", name="uq_saas_tenant_licenses_tenant_slug"),)

    id: int | None = Field(default=None, primary_key=True)
    tenant_slug: str = Field(index=True)
    tier: SaaSTenantTier = Field(default=SaaSTenantTier.ENTERPRISE)
    assigned_by: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SaaSTenantLicenseUpdate(SQLModel):
    """Payload to assign or update a hosted tenant tier."""

    tier: SaaSTenantTier
    note: str | None = None


class SaaSTenantLicensePublic(SQLModel):
    """Operator-facing SaaS tenant license view."""

    tenant_slug: str
    tier: SaaSTenantTier
    source: str
    assigned_by: str | None = None
    note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    user_count: int = 0
