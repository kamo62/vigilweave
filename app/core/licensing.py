"""License framework for the open-core model with hybrid verification.

Verification modes:
- Community: Free, offline, no verification needed
- Pro: Online verification required against license server
- Enterprise (Standard): Online verification required
- Enterprise (Offline): Self-verified, works air-gapped, premium pricing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache

from fastapi import Depends, HTTPException, status

from app.core.metrics import increment_metric
from app.core.security import AuthenticatedPrincipal, get_principal
from app.services.license_verification import (
    LicenseType,
    verify_license,
)


class FeatureTier(StrEnum):
    """Product edition."""

    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Feature(StrEnum):
    """Gated capabilities."""

    # Pro tier ($69/dev/year)
    BULK_TRIAGE = "bulk_triage"
    CUSTOM_POLICIES = "custom_policies"
    NOTIFICATIONS = "notifications"
    SCAN_SCHEDULING = "scan_scheduling"
    REPORTING = "reporting"
    AUDIT_EXTENDED = "audit_extended"

    # Enterprise tier (custom pricing)
    SSO_SAML = "sso_saml"
    RBAC = "rbac"
    MULTI_TENANCY = "multi_tenancy"
    ADVANCED_POLICIES = "advanced_policies"
    PORTFOLIOS = "portfolios"
    CUSTOM_ADAPTERS = "custom_adapters"
    WHITE_LABEL = "white_label"
    SECURITY_REPORTS = "security_reports"
    EXECUTIVE_REPORTING = "executive_reporting"


_PRO_FEATURES: set[Feature] = {
    Feature.BULK_TRIAGE,
    Feature.CUSTOM_POLICIES,
    Feature.NOTIFICATIONS,
    Feature.SCAN_SCHEDULING,
    Feature.REPORTING,
    Feature.AUDIT_EXTENDED,
}

_ENTERPRISE_FEATURES: set[Feature] = _PRO_FEATURES | {
    Feature.SSO_SAML,
    Feature.RBAC,
    Feature.MULTI_TENANCY,
    Feature.ADVANCED_POLICIES,
    Feature.PORTFOLIOS,
    Feature.CUSTOM_ADAPTERS,
    Feature.WHITE_LABEL,
    Feature.SECURITY_REPORTS,
    Feature.EXECUTIVE_REPORTING,
}

TIER_FEATURES: dict[FeatureTier, set[Feature]] = {
    FeatureTier.COMMUNITY: set(),
    FeatureTier.PRO: _PRO_FEATURES,
    FeatureTier.ENTERPRISE: _ENTERPRISE_FEATURES,
}


@dataclass(slots=True)
class LicenseInfo:
    """Resolved license state."""

    tier: FeatureTier = FeatureTier.COMMUNITY
    features: set[Feature] = field(default_factory=set)
    organization: str | None = None
    verified_online: bool = False
    license_type: LicenseType = LicenseType.COMMUNITY
    expires_at: str | None = None
    verification_error: str | None = None

    def has_feature(self, feature: Feature) -> bool:
        return feature in self.features


@lru_cache
def get_license(tenant_slug: str | None = None) -> LicenseInfo:
    """Derive the active license from the configured key.

    Uses hybrid verification:
    - Community: No verification needed
    - Pro/Enterprise Standard: Online verification required
    - Enterprise Offline: Self-verified with HMAC signature
    """
    result = verify_license(tenant_slug=tenant_slug)

    # Track license tier usage
    increment_metric("license_tier_usage", tags={"tier": result.tier})
    if result.verified_online:
        increment_metric("license_verification", tags={"mode": "online"})
    else:
        increment_metric("license_verification", tags={"mode": "offline"})

    # Convert string features to Feature enum
    features = set()
    for feature_str in result.features:
        try:
            features.add(Feature(feature_str))
        except ValueError:
            # Unknown feature, skip
            pass

    return LicenseInfo(
        tier=FeatureTier(result.tier),
        features=features,
        organization=result.organization,
        verified_online=result.verified_online,
        license_type=result.license_type,
        expires_at=result.expires_at.isoformat() if result.expires_at else None,
        verification_error=result.error_message,
    )


def require_feature(feature: Feature):
    """FastAPI dependency factory that gates an endpoint behind a feature.

    For Pro/Enterprise Standard tiers, this will fail if:
    - License verification failed
    - Server is unavailable and no valid cache exists
    - Feature is not in the license tier

    For Enterprise Offline, works without network access.
    """

    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_principal),
    ) -> LicenseInfo:
        info = get_license(principal.tenant_slug)

        if not info.has_feature(feature):
            # Check if there was a verification error to provide better messaging
            if info.verification_error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"License verification failed: {info.verification_error}. "
                        "Feature "
                        f"'{feature.value}' requires a "
                        f"{feature.value.split('_')[0].title()} license. "
                        "Visit https://vigilweave.com/pricing to upgrade."
                    ),
                )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Feature '{feature.value}' requires a higher-tier license. "
                    "Visit https://vigilweave.com/pricing to upgrade."
                ),
            )

        return info

    return dependency


def clear_license_cache() -> None:
    """Clear the license cache to force re-verification.

    Useful for:
    - Testing license changes
    - Manual cache invalidation
    - Resolving verification issues
    """
    get_license.cache_clear()
