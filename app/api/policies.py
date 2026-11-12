"""Policy, waiver, and audit endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import Feature, get_license, require_feature
from app.core.security import get_principal, require_scope
from app.models import (
    AuditEvent,
    AuditEventPublic,
    PolicyKind,
    PolicyProfile,
    PolicyProfileCreate,
    PolicyProfilePublic,
    PolicyProfileUpdate,
    Waiver,
    WaiverCreate,
    WaiverPublic,
)
from app.services.policy_engine import (
    ensure_default_policy,
    ensure_policy_presets,
    set_default_policy,
    write_audit_event,
)

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("/", response_model=list[PolicyProfilePublic])
def list_policy_profiles(
    session: Session = Depends(get_session),
    principal=Depends(get_principal),
) -> list[PolicyProfile]:
    """List policy profiles for the current tenant."""

    profiles = ensure_policy_presets(session, principal.tenant_slug)
    return sorted(
        profiles,
        key=lambda profile: (
            1 if profile.kind == PolicyKind.PRESET else 0,
            1 if profile.is_default else 0,
            profile.name.lower(),
        ),
        reverse=True,
    )


@router.post("/", response_model=PolicyProfilePublic, status_code=status.HTTP_201_CREATED)
def create_policy_profile(
    payload: PolicyProfileCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.CUSTOM_POLICIES)),
) -> PolicyProfile:
    """Create a policy profile."""

    ensure_policy_presets(session, principal.tenant_slug)
    profile = PolicyProfile(
        name=payload.name,
        description=payload.description,
        kind=PolicyKind.CUSTOM,
        repo_pattern=payload.repo_pattern,
        branch_pattern=payload.branch_pattern,
        is_default=payload.is_default,
        max_critical_findings=payload.max_critical_findings,
        max_high_findings=payload.max_high_findings,
        min_quality_score=payload.min_quality_score,
        tenant_slug=principal.tenant_slug,
    )
    session.add(profile)
    session.flush()
    session.refresh(profile)
    if profile.is_default:
        set_default_policy(session, tenant_slug=principal.tenant_slug, policy_id=profile.id)
        session.refresh(profile)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="policy.created",
        entity_type="policy_profile",
        entity_id=str(profile.id),
        details=profile.model_dump(),
    )
    session.commit()
    return profile


@router.patch("/{policy_id}", response_model=PolicyProfilePublic)
def update_policy_profile(
    policy_id: int,
    payload: PolicyProfileUpdate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.CUSTOM_POLICIES)),
) -> PolicyProfile:
    """Update a custom policy profile."""

    ensure_policy_presets(session, principal.tenant_slug)
    profile = session.get(PolicyProfile, policy_id)
    if profile is None or profile.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="Policy profile not found")
    if profile.kind != PolicyKind.CUSTOM:
        raise HTTPException(status_code=400, detail="Built-in presets cannot be edited")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(UTC)
    session.add(profile)
    if payload.is_default:
        set_default_policy(session, tenant_slug=principal.tenant_slug, policy_id=profile.id)
    elif payload.is_default is False:
        ensure_default_policy(session, principal.tenant_slug)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="policy.updated",
        entity_type="policy_profile",
        entity_id=str(profile.id),
        details=updates,
    )
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy_profile(
    policy_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.CUSTOM_POLICIES)),
) -> None:
    """Delete a custom policy profile."""

    ensure_policy_presets(session, principal.tenant_slug)
    profile = session.get(PolicyProfile, policy_id)
    if profile is None or profile.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="Policy profile not found")
    if profile.kind != PolicyKind.CUSTOM:
        raise HTTPException(status_code=400, detail="Built-in presets cannot be deleted")
    was_default = profile.is_default
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="policy.deleted",
        entity_type="policy_profile",
        entity_id=str(profile.id),
        details={"name": profile.name},
    )
    session.delete(profile)
    session.commit()
    if was_default:
        ensure_default_policy(session, principal.tenant_slug)


@router.post("/{policy_id}/activate", response_model=PolicyProfilePublic)
def activate_policy_profile(
    policy_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> PolicyProfile:
    """Make a policy profile the tenant default without editing its thresholds."""

    profiles = ensure_policy_presets(session, principal.tenant_slug)
    profile = next(
        (
            item
            for item in profiles
            if item.id == policy_id and item.tenant_slug == principal.tenant_slug
        ),
        None,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Policy profile not found")
    if profile.kind == PolicyKind.CUSTOM and not get_license(principal.tenant_slug).has_feature(
        Feature.CUSTOM_POLICIES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Custom policy activation requires a Pro or Enterprise license",
        )

    set_default_policy(
        session,
        tenant_slug=principal.tenant_slug,
        policy_id=profile.id,
        profiles=profiles,
    )
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="policy.activated",
        entity_type="policy_profile",
        entity_id=str(profile.id),
        details={"name": profile.name, "kind": profile.kind.value},
    )
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/waivers", response_model=list[WaiverPublic])
def list_waivers(
    session: Session = Depends(get_session),
    principal=Depends(get_principal),
) -> list[Waiver]:
    """List waivers for the current tenant."""

    return list(
        session.exec(select(Waiver).where(Waiver.tenant_slug == principal.tenant_slug)).all()
    )


@router.post("/waivers", response_model=WaiverPublic, status_code=status.HTTP_201_CREATED)
def create_waiver(
    payload: WaiverCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.ADVANCED_POLICIES)),
) -> Waiver:
    """Create a waiver used during scan policy evaluation."""

    waiver = Waiver(
        **payload.model_dump(exclude={"tenant_slug", "created_by"}),
        tenant_slug=principal.tenant_slug,
        created_by=payload.created_by or principal.actor,
    )
    session.add(waiver)
    session.flush()
    session.refresh(waiver)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="waiver.created",
        entity_type="waiver",
        entity_id=str(waiver.id),
        details=payload.model_dump(),
    )
    session.commit()
    return waiver


@router.delete("/waivers/{waiver_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_waiver(
    waiver_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.ADVANCED_POLICIES)),
) -> None:
    """Deactivate a waiver."""

    waiver = session.get(Waiver, waiver_id)
    if waiver is None or waiver.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="Waiver not found")
    waiver.is_active = False
    session.add(waiver)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="waiver.deactivated",
        entity_type="waiver",
        entity_id=str(waiver.id),
        details={"reason": waiver.reason},
    )
    session.commit()


@router.get("/audit", response_model=list[AuditEventPublic])
def list_audit_events(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.AUDIT_EXTENDED)),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(
        default=settings.default_audit_events_limit,
        ge=1,
        le=settings.max_audit_events_limit,
    ),
) -> list[AuditEvent]:
    """Return audit events for the current tenant."""

    return list(
        session.exec(
            select(AuditEvent)
            .where(AuditEvent.tenant_slug == principal.tenant_slug)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
