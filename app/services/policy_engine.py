"""Policy selection, waiver application, and audit helpers."""

from datetime import UTC, datetime
from fnmatch import fnmatch
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import (
    AuditEvent,
    Finding,
    PolicyEvaluation,
    PolicyKind,
    PolicyPresetKey,
    PolicyProfile,
    Scan,
    Waiver,
)

_PRESET_DEFINITIONS: dict[PolicyPresetKey, dict[str, Any]] = {
    PolicyPresetKey.LENIENT: {
        "name": "Lenient",
        "description": "Relaxed preset for legacy repositories and noisy baselines.",
        "is_default": False,
        "max_critical_findings": 0,
        "max_high_findings": 10,
        "min_quality_score": 60.0,
    },
    PolicyPresetKey.BALANCED: {
        "name": "Balanced",
        "description": "Default preset for most teams.",
        "is_default": True,
        "max_critical_findings": 0,
        "max_high_findings": 5,
        "min_quality_score": 70.0,
    },
    PolicyPresetKey.STRICT: {
        "name": "Strict",
        "description": "Tighter preset for release branches and hardened services.",
        "is_default": False,
        "max_critical_findings": 0,
        "max_high_findings": 1,
        "min_quality_score": 80.0,
    },
}


def ensure_policy_presets(session: Session, tenant_slug: str) -> list[PolicyProfile]:
    """Ensure the built-in presets exist for the given tenant."""

    existing = list(
        session.exec(select(PolicyProfile).where(PolicyProfile.tenant_slug == tenant_slug)).all()
    )
    existing_presets = {
        profile.preset_key
        for profile in existing
        if profile.kind == PolicyKind.PRESET and profile.preset_key is not None
    }

    missing = [key for key in _PRESET_DEFINITIONS if key not in existing_presets]
    if not missing:
        return ensure_default_policy(session, tenant_slug, profiles=existing)

    for preset_key in missing:
        preset = _PRESET_DEFINITIONS[preset_key]
        session.add(
            PolicyProfile(
                tenant_slug=tenant_slug,
                kind=PolicyKind.PRESET,
                preset_key=preset_key,
                name=str(preset["name"]),
                description=str(preset["description"]),
                is_default=bool(preset["is_default"]),
                max_critical_findings=int(preset["max_critical_findings"]),
                max_high_findings=int(preset["max_high_findings"]),
                min_quality_score=float(preset["min_quality_score"]),
            )
        )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return ensure_default_policy(
        session,
        tenant_slug,
        profiles=list(
            session.exec(
                select(PolicyProfile).where(PolicyProfile.tenant_slug == tenant_slug)
            ).all()
        ),
    )


def ensure_default_policy(
    session: Session,
    tenant_slug: str,
    *,
    profiles: list[PolicyProfile] | None = None,
) -> list[PolicyProfile]:
    """Ensure exactly one default policy exists for the tenant."""

    resolved_profiles = profiles or list(
        session.exec(select(PolicyProfile).where(PolicyProfile.tenant_slug == tenant_slug)).all()
    )
    defaults = [profile for profile in resolved_profiles if profile.is_default]
    if len(defaults) == 1:
        return resolved_profiles

    preferred = (
        _rank_profiles(defaults)[0]
        if defaults
        else next(
            (
                profile
                for profile in resolved_profiles
                if profile.kind == PolicyKind.PRESET
                and profile.preset_key == PolicyPresetKey.BALANCED
            ),
            resolved_profiles[0] if resolved_profiles else None,
        )
    )
    if preferred is None:
        return resolved_profiles

    return set_default_policy(
        session,
        tenant_slug=tenant_slug,
        policy_id=preferred.id,
        profiles=resolved_profiles,
    )


def set_default_policy(
    session: Session,
    *,
    tenant_slug: str,
    policy_id: int | None,
    profiles: list[PolicyProfile] | None = None,
) -> list[PolicyProfile]:
    """Mark one policy as default and clear the rest."""

    if policy_id is None:
        return ensure_default_policy(session, tenant_slug, profiles=profiles)

    resolved_profiles = profiles or list(
        session.exec(select(PolicyProfile).where(PolicyProfile.tenant_slug == tenant_slug)).all()
    )
    changed = False
    for profile in resolved_profiles:
        should_be_default = profile.id == policy_id
        if profile.is_default != should_be_default:
            profile.is_default = should_be_default
            profile.updated_at = datetime.now(UTC)
            session.add(profile)
            changed = True
    if changed:
        session.commit()
        for profile in resolved_profiles:
            session.refresh(profile)
    return resolved_profiles


def matching_policy(
    session: Session,
    tenant_slug: str,
    repo: str,
    branch: str | None,
) -> PolicyProfile | None:
    """Return the most specific policy profile for the scan context."""

    profiles = ensure_policy_presets(session, tenant_slug)
    exact_matches = [
        profile
        for profile in profiles
        if _matches(profile.repo_pattern, repo) and _matches(profile.branch_pattern, branch or "")
    ]
    if exact_matches:
        return _rank_profiles(exact_matches)[0]
    defaults = [profile for profile in profiles if profile.is_default]
    return _rank_profiles(defaults)[0] if defaults else None


def evaluate_scan_policy(scan: Scan, profile: PolicyProfile | None) -> PolicyEvaluation:
    """Evaluate a scan against the selected policy profile."""

    if profile is None:
        return PolicyEvaluation(matched=False, passed=scan.quality_gate_passed is not False)

    reasons: list[str] = []
    if scan.critical_findings > profile.max_critical_findings:
        reasons.append(
            "Critical findings "
            f"{scan.critical_findings} exceed limit {profile.max_critical_findings}"
        )
    if scan.high_findings > profile.max_high_findings:
        reasons.append(
            f"High findings {scan.high_findings} exceed limit {profile.max_high_findings}"
        )
    if scan.quality_score is not None and scan.quality_score < profile.min_quality_score:
        reasons.append(
            "Quality score "
            f"{scan.quality_score:.2f} is below minimum {profile.min_quality_score:.2f}"
        )

    return PolicyEvaluation(
        profile_id=profile.id,
        profile_name=profile.name,
        matched=True,
        passed=not reasons,
        reasons=reasons,
        thresholds={
            "max_critical_findings": profile.max_critical_findings,
            "max_high_findings": profile.max_high_findings,
            "min_quality_score": profile.min_quality_score,
        },
    )


def apply_waivers(
    session: Session, scan: Scan, findings: list[Finding], actor: str = "system"
) -> tuple[list[Finding], int]:
    """Apply active waivers to findings in-place and return suppressed count."""

    waivers = list(
        session.exec(
            select(Waiver).where(Waiver.tenant_slug == scan.tenant_slug, Waiver.is_active.is_(True))
        ).all()
    )
    now = datetime.now(UTC)
    suppressed = 0
    for finding in findings:
        matched = next(
            (
                waiver
                for waiver in waivers
                if (waiver.expires_at is None or waiver.expires_at >= now)
                and _matches(waiver.repo_pattern, scan.repo)
                and _matches(waiver.branch_pattern, scan.branch or "")
                and _matches_field(waiver.rule_id, finding.rule_id)
                and _matches_field(waiver.fingerprint, finding.fingerprint)
                and _matches_field(waiver.file_path, finding.file_path)
                and _matches_field(waiver.category, finding.category)
            ),
            None,
        )
        if matched is None:
            continue
        if finding.is_suppressed:
            continue
        finding.is_suppressed = True
        finding.suppression_reason = matched.reason
        finding.waiver_id = matched.id
        suppressed += 1
        session.add(
            AuditEvent(
                tenant_slug=scan.tenant_slug,
                actor=actor,
                action="waiver.applied",
                entity_type="finding",
                entity_id=str(finding.id or finding.fingerprint),
                details={
                    "repo": scan.repo,
                    "waiver_id": matched.id,
                    "reason": matched.reason,
                    "fingerprint": finding.fingerprint,
                },
            )
        )
    return findings, suppressed


def write_audit_event(
    session: Session,
    *,
    tenant_slug: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Persist a single audit event."""

    session.add(
        AuditEvent(
            tenant_slug=tenant_slug,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=jsonable_encoder(details or {}),
        )
    )


def _matches(pattern: str | None, value: str) -> bool:
    return pattern is None or fnmatch(value, pattern)


def _matches_field(expected: str | None, actual: str | None) -> bool:
    return expected is None or expected == actual


def _rank_profiles(profiles: list[PolicyProfile]) -> list[PolicyProfile]:
    """Sort profiles by specificity and custom precedence."""

    return sorted(
        profiles,
        key=lambda profile: (
            1 if profile.repo_pattern else 0,
            1 if profile.branch_pattern else 0,
            1 if profile.kind == PolicyKind.CUSTOM else 0,
            1 if profile.is_default else 0,
            -(profile.id or 0),
        ),
        reverse=True,
    )
