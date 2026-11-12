"""Tenant upsert and synchronization helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import SaaSTenantTier, Tenant, TenantBillingStatus, TenantDeploymentMode


def upsert_tenant(
    session: Session,
    *,
    slug: str,
    display_name: str | None = None,
    billing_email: str | None = None,
    deployment_mode: TenantDeploymentMode | None = None,
    plan_tier: SaaSTenantTier | None = None,
    billing_status: TenantBillingStatus | None = None,
    workos_org_id: str | None = None,
    paddle_customer_id: str | None = None,
    paddle_subscription_id: str | None = None,
    self_hosted_license_id: int | None = None,
    self_hosted_license_key_prefix: str | None = None,
    encrypted_self_hosted_license_key: str | None = None,
    self_hosted_license_status: str | None = None,
    self_hosted_last_fulfilled_at: datetime | None = None,
) -> Tenant:
    """Create or update a tenant metadata record keyed by slug."""

    normalized_slug = slug.strip()
    if not normalized_slug:
        raise ValueError("Tenant slug is required")

    tenant = session.exec(select(Tenant).where(Tenant.slug == normalized_slug)).first()
    now = datetime.now(UTC)

    if tenant is None:
        tenant = Tenant(
            slug=normalized_slug,
            display_name=display_name or normalized_slug,
            billing_email=billing_email,
            deployment_mode=deployment_mode or TenantDeploymentMode.SAAS,
            plan_tier=plan_tier or SaaSTenantTier.COMMUNITY,
            billing_status=billing_status or TenantBillingStatus.INACTIVE,
            workos_org_id=workos_org_id,
            paddle_customer_id=paddle_customer_id,
            paddle_subscription_id=paddle_subscription_id,
            self_hosted_license_id=self_hosted_license_id,
            self_hosted_license_key_prefix=self_hosted_license_key_prefix,
            encrypted_self_hosted_license_key=encrypted_self_hosted_license_key,
            self_hosted_license_status=self_hosted_license_status,
            self_hosted_last_fulfilled_at=self_hosted_last_fulfilled_at,
            created_at=now,
            updated_at=now,
        )
    else:
        tenant.display_name = display_name or tenant.display_name
        tenant.billing_email = billing_email or tenant.billing_email
        tenant.deployment_mode = deployment_mode or tenant.deployment_mode
        tenant.plan_tier = plan_tier or tenant.plan_tier
        tenant.billing_status = billing_status or tenant.billing_status
        tenant.workos_org_id = workos_org_id or tenant.workos_org_id
        tenant.paddle_customer_id = paddle_customer_id or tenant.paddle_customer_id
        tenant.paddle_subscription_id = paddle_subscription_id or tenant.paddle_subscription_id
        tenant.self_hosted_license_id = self_hosted_license_id or tenant.self_hosted_license_id
        tenant.self_hosted_license_key_prefix = (
            self_hosted_license_key_prefix or tenant.self_hosted_license_key_prefix
        )
        tenant.encrypted_self_hosted_license_key = (
            encrypted_self_hosted_license_key or tenant.encrypted_self_hosted_license_key
        )
        tenant.self_hosted_license_status = (
            self_hosted_license_status or tenant.self_hosted_license_status
        )
        tenant.self_hosted_last_fulfilled_at = (
            self_hosted_last_fulfilled_at or tenant.self_hosted_last_fulfilled_at
        )
        tenant.updated_at = now

    session.add(tenant)
    return tenant
