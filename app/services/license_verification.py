"""License verification service with online/offline support.

Licensing Model:
- Community: Free, offline, no verification
- Pro: Online verification required, checked against license server
- Enterprise (Standard): Online verification required
- Enterprise (Offline): Premium pricing, self-contained keys, works air-gapped

Key Formats:
- Pro: vw-pro-{org}-{hash} (verified online)
- Enterprise (Standard): vw-ent-{org}-{hash} (verified online)
- Enterprise (Offline): vw-ent-offline-{org}-{signature} (self-verified)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core import database as database_module
from app.core.config import settings
from app.models import SaaSTenantLicense, SaaSTenantTier
from app.models.runtime_state import LicenseVerificationCache

logger = logging.getLogger(__name__)
LICENSE_CACHE_FILE: Path | None = None
_LICENSE_CACHE_VERSION = 2


class LicenseType(StrEnum):
    """License verification mode."""

    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE_STANDARD = "enterprise_standard"
    ENTERPRISE_OFFLINE = "enterprise_offline"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of license verification."""

    valid: bool
    license_type: LicenseType
    tier: str  # community, pro, enterprise
    organization: str | None
    expires_at: datetime | None
    features: list[str]
    error_message: str | None = None
    verified_online: bool = False


_PRO_FEATURES = [
    "bulk_triage",
    "custom_policies",
    "notifications",
    "scan_scheduling",
    "reporting",
    "audit_extended",
]

_ENTERPRISE_FEATURES = _PRO_FEATURES + [
    "sso_saml",
    "rbac",
    "multi_tenancy",
    "advanced_policies",
    "portfolios",
    "custom_adapters",
    "white_label",
    "security_reports",
    "executive_reporting",
]


def _features_for_tier(tier: str) -> list[str]:
    if tier == "enterprise":
        return list(_ENTERPRISE_FEATURES)
    if tier == "pro":
        return list(_PRO_FEATURES)
    return []


def _resolve_hosted_tenant_tier(tenant_slug: str | None) -> SaaSTenantTier:
    if tenant_slug:
        with Session(database_module.engine) as session:
            record = session.exec(
                select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == tenant_slug)
            ).first()
        if record is not None:
            return record.tier
    return SaaSTenantTier.ENTERPRISE


def _hosted_saas_verification_result(tenant_slug: str | None) -> VerificationResult:
    tier = _resolve_hosted_tenant_tier(tenant_slug)
    license_type = {
        SaaSTenantTier.COMMUNITY: LicenseType.COMMUNITY,
        SaaSTenantTier.PRO: LicenseType.PRO,
        SaaSTenantTier.ENTERPRISE: LicenseType.ENTERPRISE_STANDARD,
    }[tier]
    return VerificationResult(
        valid=True,
        license_type=license_type,
        tier=tier.value,
        organization="VigilWeave Cloud",
        expires_at=None,
        features=_features_for_tier(tier.value),
        verified_online=False,
    )


def _parse_license_key(key: str | None) -> tuple[LicenseType, str, str | None]:
    """Parse license key to determine type and extract organization.

    Returns:
        Tuple of (license_type, organization, remaining_hash)
    """
    if not key:
        return LicenseType.COMMUNITY, "", None

    if key.startswith("vw-ent-offline-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-ent-offline-")
        if parsed is not None:
            org, signature = parsed
            return LicenseType.ENTERPRISE_OFFLINE, org, signature

    if key.startswith("vw-ent-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-ent-")
        if parsed is not None:
            org, hash_part = parsed
            return LicenseType.ENTERPRISE_STANDARD, org, hash_part

    if key.startswith("vw-pro-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-pro-")
        if parsed is not None:
            org, hash_part = parsed
            return LicenseType.PRO, org, hash_part

    # Unknown key format - treat as community
    return LicenseType.COMMUNITY, "", None


def _parse_key_with_prefix(key: str, *, prefix: str) -> tuple[str, str] | None:
    """Parse keys as {prefix}{organization}-{suffix} with rightmost split."""

    if not key.startswith(prefix):
        return None

    remainder = key.removeprefix(prefix)
    organization, separator, suffix = remainder.rpartition("-")
    if not separator or not organization or not suffix:
        return None
    return organization, suffix


def _license_cache_key(key: str) -> str:
    """Return a deterministic, collision-resistant cache key for online licenses."""

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"online_v{_LICENSE_CACHE_VERSION}_{digest}"


def _license_key_fingerprint(key: str) -> str:
    """Return a short, non-sensitive fingerprint for support/debug metadata."""

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _verify_offline_enterprise_key(key: str | None, org: str, signature: str) -> VerificationResult:
    """Verify an offline enterprise key using HMAC signature.

    Offline keys use HMAC-SHA256 with a shared secret. This provides:
    - Basic tamper resistance (signature validation)
    - Organization binding (org in signature)
    - No network requirements

    Note: This is NOT cryptographically secure against determined attackers,
    but provides reasonable protection for offline enterprise customers who
    pay a premium for air-gapped operation.
    """
    if settings.offline_license_secret:
        expected_secret = settings.offline_license_secret
    else:
        if settings.environment not in {"development", "test"}:
            return VerificationResult(
                valid=False,
                license_type=LicenseType.COMMUNITY,
                tier="community",
                organization=None,
                expires_at=None,
                features=[],
                error_message=(
                    "OFFLINE_LICENSE_SECRET is not configured for offline enterprise validation"
                ),
                verified_online=False,
            )
        logger.warning(
            "OFFLINE_LICENSE_SECRET is not set — using insecure placeholder. "
            "Set OFFLINE_LICENSE_SECRET to a random value in production."
        )
        expected_secret = f"vigilweave-offline-{org}-secret"

    # Reconstruct the signed payload
    payload = f"vw-ent-offline-{org}"
    expected_signature = hmac.new(
        expected_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:32]

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(f"Invalid offline enterprise key signature for org: {org}")
        return VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message="Invalid license key signature",
            verified_online=False,
        )

    # Offline enterprise keys are valid for 1 year from first use
    # We track this via a simple cache file
    cache_data = _load_license_cache()
    cache_key = f"offline_ent_{org}"

    if cache_key in cache_data:
        first_seen = datetime.fromisoformat(cache_data[cache_key]["first_seen"])
        expires_at = datetime.fromisoformat(cache_data[cache_key]["expires_at"])
    else:
        first_seen = datetime.now(UTC)
        expires_at = first_seen.replace(year=first_seen.year + 1)
        cache_data[cache_key] = {
            "first_seen": first_seen.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        _save_license_cache(cache_data)

    if datetime.now(UTC) > expires_at:
        return VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=expires_at,
            features=[],
            error_message="License has expired. Please contact VigilWeave support to renew.",
            verified_online=False,
        )

    return VerificationResult(
        valid=True,
        license_type=LicenseType.ENTERPRISE_OFFLINE,
        tier="enterprise",
        organization=org,
        expires_at=expires_at,
        features=[
            "bulk_triage",
            "custom_policies",
            "notifications",
            "scan_scheduling",
            "reporting",
            "audit_extended",
            "sso_saml",
            "rbac",
            "multi_tenancy",
            "advanced_policies",
            "portfolios",
            "custom_adapters",
            "white_label",
            "security_reports",
            "executive_reporting",
        ],
        verified_online=False,
    )


def _verify_online_key(key: str | None, license_type: LicenseType, org: str) -> VerificationResult:
    """Verify a Pro or Enterprise Standard key against the license server.

    Attempts online verification with graceful fallback to cached results
    if the server is unavailable.
    """
    # Handle None key
    if key is None:
        key = ""

    cache_data = _load_license_cache()
    cache_key = _license_cache_key(key)

    # Check if we have a valid cached result
    if cache_key in cache_data:
        cached = cache_data[cache_key]
        cached_at = datetime.fromisoformat(cached["cached_at"])

        # Use cache if it's less than configured TTL old
        cache_ttl = settings.license_cache_ttl_hours * 3600
        if (datetime.now(UTC) - cached_at).total_seconds() < cache_ttl:
            logger.debug(f"Using cached license verification for {org}")
            return VerificationResult(
                valid=cached["valid"],
                license_type=LicenseType(cached["license_type"]),
                tier=cached["tier"],
                organization=cached["organization"],
                expires_at=datetime.fromisoformat(cached["expires_at"])
                if cached["expires_at"]
                else None,
                features=cached["features"],
                error_message=cached.get("error_message"),
                verified_online=False,  # Cached result
            )

    # Attempt online verification
    try:
        result = _call_license_server(key, license_type, org)

        # Cache successful results
        if result.valid:
            cache_data[cache_key] = {
                "valid": result.valid,
                "license_type": result.license_type.value,
                "tier": result.tier,
                "organization": result.organization,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
                "features": result.features,
                "cached_at": datetime.now(UTC).isoformat(),
                "verified_at": datetime.now(UTC).isoformat(),
                "verification_source": "online",
                "key_fingerprint": _license_key_fingerprint(key),
                "cache_version": _LICENSE_CACHE_VERSION,
            }
            _save_license_cache(cache_data)

        return result

    except Exception as exc:
        logger.warning(f"License server verification failed: {exc}")

        # Check for stale cache (up to 7 days old during outages)
        if cache_key in cache_data:
            cached = cache_data[cache_key]
            cached_at = datetime.fromisoformat(cached["cached_at"])
            age_days = (datetime.now(UTC) - cached_at).total_seconds() / 86400

            if age_days <= 7:
                logger.info(f"Using stale cache ({age_days:.1f} days old) for {org}")
                return VerificationResult(
                    valid=cached["valid"],
                    license_type=LicenseType(cached["license_type"]),
                    tier=cached["tier"],
                    organization=cached["organization"],
                    expires_at=datetime.fromisoformat(cached["expires_at"])
                    if cached["expires_at"]
                    else None,
                    features=cached["features"],
                    error_message=(
                        "Using cached license (server unavailable). "
                        f"{cached.get('error_message', '')}"
                    ),
                    verified_online=False,
                )

        # No valid cache and server unavailable
        return VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message=(
                "License verification server unavailable. Please check your internet connection."
            ),
            verified_online=False,
        )


def _call_license_server(
    key: str | None, license_type: LicenseType, org: str
) -> VerificationResult:
    """Call the license verification server.

    Makes an HTTP request to the license server to verify the key.
    Falls back to cached results if the server is unavailable.
    """
    if key is None:
        key = ""

    try:
        response = httpx.post(
            settings.license_server_url,
            json={
                "license_key": key,
                "instance_id": str(uuid.uuid4()),  # Generate unique instance ID
            },
            timeout=settings.license_verify_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        return VerificationResult(
            valid=data["valid"],
            license_type=LicenseType(data["license_type"])
            if data["license_type"] != "community"
            else LicenseType.COMMUNITY,
            tier=data["tier"],
            organization=data["organization"],
            expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None,
            features=data["features"],
            error_message=data.get("error_message"),
            verified_online=True,
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"License server returned error: {exc.response.status_code} - {exc.response.text}"
        )
        return VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message=f"License server error: {exc.response.status_code}",
            verified_online=False,
        )

    except httpx.RequestError as exc:
        logger.warning(f"License server request failed: {exc}")
        # This will trigger the cache fallback in _verify_online_key
        raise  # Re-raise to be handled by caller

    except Exception as exc:
        logger.error(f"Unexpected error calling license server: {exc}")
        return VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message=f"License verification error: {str(exc)}",
            verified_online=False,
        )


def _load_license_cache() -> dict[str, Any]:
    """Load license verification cache entries from the application database."""

    if LICENSE_CACHE_FILE is not None:
        try:
            if not LICENSE_CACHE_FILE.exists():
                return {}
            return json.loads(LICENSE_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load license cache file: %s", exc)
            return {}

    try:
        with Session(database_module.engine) as session:
            rows = session.exec(select(LicenseVerificationCache)).all()
            cache: dict[str, Any] = {}
            for row in rows:
                if row.cache_key.startswith("online_") and not row.cache_key.startswith(
                    f"online_v{_LICENSE_CACHE_VERSION}_"
                ):
                    continue
                cache[row.cache_key] = row.payload
            return cache
    except Exception as exc:
        logger.warning("Failed to load license cache: %s", exc)
        return {}


def _save_license_cache(data: dict[str, Any]) -> None:
    """Save license verification cache entries to the application database."""

    if LICENSE_CACHE_FILE is not None:
        try:
            LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            LICENSE_CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to save license cache file: %s", exc)
        return

    try:
        with Session(database_module.engine) as session:
            existing_rows = session.exec(select(LicenseVerificationCache)).all()
            existing = {row.cache_key: row for row in existing_rows}
            seen_keys: set[str] = set()
            for cache_key, payload in data.items():
                row = existing.get(cache_key)
                if row is None:
                    row = LicenseVerificationCache(cache_key=cache_key)
                row.payload = payload
                row.cached_at = datetime.now(UTC)
                session.add(row)
                seen_keys.add(cache_key)
            for cache_key, row in existing.items():
                if cache_key not in seen_keys or (
                    cache_key.startswith("online_")
                    and not cache_key.startswith(f"online_v{_LICENSE_CACHE_VERSION}_")
                ):
                    session.delete(row)
            session.commit()
    except Exception as exc:
        logger.warning("Failed to save license cache: %s", exc)


def verify_license(key: str | None = None, tenant_slug: str | None = None) -> VerificationResult:
    """Verify a license key.

    This is the main entry point for license verification.

    DEVELOPER NOTE: Set LICENSE_TESTING_MODE=true in your .env file to bypass
    verification and unlock all features for testing.

    Args:
        key: License key to verify. If None, uses settings.license_key

    Returns:
        VerificationResult with validation status and features
    """
    if key is None:
        key = settings.license_key

    # Handle case where no key is provided and settings.license_key is None
    if key is None:
        key = ""

    if settings.resolved_distribution_mode() == "community":
        return VerificationResult(
            valid=True,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization="VigilWeave Community",
            expires_at=None,
            features=[],
            verified_online=False,
        )

    # TESTING MODE: Bypass all verification and grant full access
    if settings.license_testing_mode:
        logger.warning("LICENSE TESTING MODE ENABLED - All features unlocked!")
        return VerificationResult(
            valid=True,
            license_type=LicenseType.ENTERPRISE_STANDARD,
            tier="enterprise",
            organization="test-mode",
            expires_at=None,
            features=[
                "bulk_triage",
                "custom_policies",
                "notifications",
                "scan_scheduling",
                "reporting",
                "audit_extended",
                "sso_saml",
                "rbac",
                "multi_tenancy",
                "advanced_policies",
                "portfolios",
                "custom_adapters",
                "white_label",
                "security_reports",
                "executive_reporting",
            ],
            verified_online=False,
        )

    if settings.is_vigilweave_cloud():
        return _hosted_saas_verification_result(tenant_slug)

    if settings.saas_enabled and not key:
        return VerificationResult(
            valid=True,
            license_type=LicenseType.PRO,
            tier="pro",
            organization="VigilWeave Cloud",
            expires_at=None,
            features=_features_for_tier("pro"),
            verified_online=False,
        )

    license_type, org, hash_or_signature = _parse_license_key(key)

    if license_type == LicenseType.COMMUNITY:
        return VerificationResult(
            valid=True,  # Community is always "valid" (just limited)
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            verified_online=False,
        )

    elif license_type == LicenseType.ENTERPRISE_OFFLINE:
        return _verify_offline_enterprise_key(key, org, hash_or_signature or "")

    elif license_type in (LicenseType.PRO, LicenseType.ENTERPRISE_STANDARD):
        return _verify_online_key(key, license_type, org)

    return VerificationResult(
        valid=False,
        license_type=LicenseType.COMMUNITY,
        tier="community",
        organization=None,
        expires_at=None,
        features=[],
        error_message="Invalid license key format",
        verified_online=False,
    )
