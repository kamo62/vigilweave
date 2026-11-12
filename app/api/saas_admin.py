"""Operator-only SaaS tenant license management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import clear_license_cache, get_license
from app.core.security import require_platform_operator
from app.models import (
    PlatformRole,
    SaaSTenantLicense,
    SaaSTenantLicensePublic,
    SaaSTenantLicenseUpdate,
    SaaSTenantTier,
    TenantBillingStatus,
    TenantDeploymentMode,
    User,
    UserPlatformRoleUpdate,
    UserPublic,
)
from app.services.tenants import upsert_tenant

router = APIRouter(prefix="/saas-admin", tags=["saas-admin"])


def _require_hosted_vigilweave_cloud() -> None:
    if not settings.is_vigilweave_cloud():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hosted VigilWeave cloud controls are not enabled for this environment",
        )


@router.get("/tenant-licenses", response_model=list[SaaSTenantLicensePublic])
def list_tenant_licenses(
    session: Session = Depends(get_session),
    principal=Depends(require_platform_operator()),
) -> list[SaaSTenantLicensePublic]:
    """List effective SaaS tiers for known tenants."""

    del principal
    _require_hosted_vigilweave_cloud()

    tenant_counts = dict(
        session.exec(select(User.tenant_slug, func.count(User.id)).group_by(User.tenant_slug)).all()
    )
    overrides = {
        record.tenant_slug: record
        for record in session.exec(
            select(SaaSTenantLicense).order_by(SaaSTenantLicense.tenant_slug)
        ).all()
    }
    tenant_slugs = sorted(set(tenant_counts) | set(overrides))

    response: list[SaaSTenantLicensePublic] = []
    for tenant_slug in tenant_slugs:
        override = overrides.get(tenant_slug)
        resolved = get_license(tenant_slug)
        response.append(
            SaaSTenantLicensePublic(
                tenant_slug=tenant_slug,
                tier=resolved.tier.value,
                source="override" if override else "default",
                assigned_by=override.assigned_by if override else None,
                note=override.note if override else None,
                created_at=override.created_at if override else None,
                updated_at=override.updated_at if override else None,
                user_count=int(tenant_counts.get(tenant_slug, 0)),
            )
        )
    return response


@router.put("/tenant-licenses/{tenant_slug}", response_model=SaaSTenantLicensePublic)
def upsert_tenant_license(
    tenant_slug: str,
    payload: SaaSTenantLicenseUpdate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_platform_operator()),
) -> SaaSTenantLicensePublic:
    """Assign or update a hosted SaaS tier for a tenant."""

    del request
    _require_hosted_vigilweave_cloud()

    normalized_tenant_slug = tenant_slug.strip()
    if not normalized_tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant slug is required"
        )

    record = session.exec(
        select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == normalized_tenant_slug)
    ).first()
    now = datetime.now(UTC)

    if record is None:
        record = SaaSTenantLicense(
            tenant_slug=normalized_tenant_slug,
            tier=payload.tier,
            assigned_by=principal.actor,
            note=payload.note,
            created_at=now,
            updated_at=now,
        )
    else:
        record.tier = payload.tier
        record.assigned_by = principal.actor
        record.note = payload.note
        record.updated_at = now

    session.add(record)
    upsert_tenant(
        session,
        slug=record.tenant_slug,
        display_name=record.tenant_slug,
        deployment_mode=TenantDeploymentMode.SAAS,
        plan_tier=record.tier,
        billing_status=TenantBillingStatus.MANUAL,
    )
    session.commit()
    session.refresh(record)
    clear_license_cache()

    return SaaSTenantLicensePublic(
        tenant_slug=record.tenant_slug,
        tier=record.tier,
        source="override",
        assigned_by=record.assigned_by,
        note=record.note,
        created_at=record.created_at,
        updated_at=record.updated_at,
        user_count=int(
            session.exec(
                select(func.count(User.id)).where(User.tenant_slug == record.tenant_slug)
            ).one()
        ),
    )


@router.delete("/tenant-licenses/{tenant_slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant_license(
    tenant_slug: str,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_platform_operator()),
) -> None:
    """Remove a tenant override and fall back to hosted Enterprise defaults."""

    del request, principal
    _require_hosted_vigilweave_cloud()

    normalized_tenant_slug = tenant_slug.strip()
    if not normalized_tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant slug is required"
        )

    record = session.exec(
        select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == normalized_tenant_slug)
    ).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant license not found"
        )

    session.delete(record)
    upsert_tenant(
        session,
        slug=normalized_tenant_slug,
        display_name=normalized_tenant_slug,
        deployment_mode=TenantDeploymentMode.SAAS,
        plan_tier=SaaSTenantTier.ENTERPRISE,
        billing_status=TenantBillingStatus.MANUAL,
    )
    session.commit()
    clear_license_cache()


@router.get("/users", response_model=list[UserPublic])
def list_platform_users(
    session: Session = Depends(get_session),
    principal=Depends(require_platform_operator()),
) -> list[User]:
    """List users across all hosted SaaS tenants for operator management."""

    del principal
    _require_hosted_vigilweave_cloud()
    return list(session.exec(select(User).order_by(User.created_at)).all())


@router.patch("/users/{user_id}/platform-role", response_model=UserPublic)
def update_platform_user_role(
    user_id: int,
    payload: UserPlatformRoleUpdate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_platform_operator()),
) -> User:
    """Grant or revoke persistent platform operator access."""

    del request
    _require_hosted_vigilweave_cloud()

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == principal.user_id and payload.platform_role != PlatformRole.OPERATOR:
        operator_count = int(
            session.exec(
                select(func.count(User.id)).where(User.platform_role == PlatformRole.OPERATOR)
            ).one()
        )
        if operator_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last platform operator",
            )

    user.platform_role = payload.platform_role
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
