"""Public and tenant-scoped billing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.csrf import enforce_csrf_if_session
from app.core.database import get_session
from app.core.security import get_principal, require_scope
from app.core.token_encryption import TokenEncryptionError, decrypt_token
from app.models import (
    BillingPortalSessionPublic,
    BillingSubscription,
    BillingSubscriptionPublic,
    PaddleBillingPublicConfig,
    SelfHostedLicensePublic,
    Tenant,
    TenantPublic,
)
from app.services.billing import create_customer_portal_session, paddle_public_config

router = APIRouter(prefix="/billing", tags=["billing"])


def _require_commercial_activation() -> None:
    if settings.commercial_activation_enabled():
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Billing is not available in the Community distribution",
    )


@router.get("/public-config", response_model=PaddleBillingPublicConfig)
def get_billing_public_config() -> PaddleBillingPublicConfig:
    """Return public Paddle configuration used by the frontend checkout flow."""

    return paddle_public_config()


@router.get("/subscription", response_model=BillingSubscriptionPublic | None)
def get_current_tenant_subscription(
    session: Session = Depends(get_session),
    principal=Depends(get_principal),
) -> BillingSubscriptionPublic | None:
    """Return the latest synced billing subscription for the authenticated tenant."""

    record = session.exec(
        select(BillingSubscription)
        .where(BillingSubscription.tenant_slug == principal.tenant_slug)
        .order_by(BillingSubscription.updated_at.desc())
    ).first()
    if record is None:
        return None
    return BillingSubscriptionPublic.model_validate(record)


@router.get("/tenant", response_model=TenantPublic | None)
def get_current_tenant_summary(
    session: Session = Depends(get_session),
    principal=Depends(get_principal),
) -> TenantPublic | None:
    """Return the first-class tenant record for the authenticated tenant."""

    tenant = session.exec(select(Tenant).where(Tenant.slug == principal.tenant_slug)).first()
    if tenant is None:
        return None
    return TenantPublic.model_validate(tenant)


@router.post("/portal-session", response_model=BillingPortalSessionPublic)
def create_current_tenant_portal_session(
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> BillingPortalSessionPublic:
    """Create an authenticated Paddle customer portal session for the current tenant."""

    _require_commercial_activation()
    enforce_csrf_if_session(request)

    try:
        return create_customer_portal_session(session, tenant_slug=principal.tenant_slug)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/self-hosted-license", response_model=SelfHostedLicensePublic)
def get_current_self_hosted_license(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> SelfHostedLicensePublic:
    """Return the current tenant's issued self-hosted commercial key for admins."""

    _require_commercial_activation()

    tenant = session.exec(select(Tenant).where(Tenant.slug == principal.tenant_slug)).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    license_key: str | None = None
    if tenant.encrypted_self_hosted_license_key:
        try:
            license_key = decrypt_token(tenant.encrypted_self_hosted_license_key)
        except TokenEncryptionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    return SelfHostedLicensePublic(
        tenant_slug=tenant.slug,
        license_id=tenant.self_hosted_license_id,
        key_prefix=tenant.self_hosted_license_key_prefix,
        status=tenant.self_hosted_license_status,
        license_key=license_key,
        last_fulfilled_at=tenant.self_hosted_last_fulfilled_at,
    )
