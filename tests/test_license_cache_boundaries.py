"""Synthetic entitlement regression checks for expiry, rejection and outages."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core import licensing
from app.core.config import settings
from app.services import license_verification as verification
from app.services import tool_adapters


def _result(valid=True, expires_at=None):
    return verification.VerificationResult(
        valid=valid,
        license_type=verification.LicenseType.PRO if valid else verification.LicenseType.COMMUNITY,
        tier="pro" if valid else "community",
        organization="Synthetic",
        expires_at=expires_at,
        features=["reporting"] if valid else [],
        verified_online=True,
    )


def _cache(monkeypatch, *, expired=False, old=False):
    now = datetime.now(UTC)
    cache = {
        verification._license_cache_key("synthetic"): {
            "valid": True,
            "license_type": "pro",
            "tier": "pro",
            "organization": "Synthetic",
            "expires_at": (now + timedelta(hours=-1 if expired else 12)).isoformat(),
            "features": ["reporting"],
            "cached_at": (now - timedelta(days=2) if old else now).isoformat(),
        }
    }
    monkeypatch.setattr(verification, "_load_license_cache", lambda: cache)
    monkeypatch.setattr(verification, "_save_license_cache", lambda data: None)
    return cache


@pytest.mark.parametrize("old", [False, True])
def test_expired_licence_never_grants_cached_entitlement(monkeypatch, old):
    _cache(monkeypatch, expired=True, old=old)

    def offline(*args):
        raise httpx.ConnectError("synthetic outage")

    monkeypatch.setattr(verification, "_call_license_server", offline)
    result = verification._verify_online_key("synthetic", verification.LicenseType.PRO, "Synthetic")
    assert result.valid is False
    assert result.features == []


def test_rejection_removes_old_positive_before_a_later_outage(monkeypatch):
    cache = _cache(monkeypatch, old=True)
    monkeypatch.setattr(verification, "_call_license_server", lambda *args: _result(False))
    assert not verification._verify_online_key(
        "synthetic", verification.LicenseType.PRO, "Synthetic"
    ).valid
    assert verification._license_cache_key("synthetic") not in cache


def test_server_error_uses_unexpired_outage_grace(monkeypatch):
    _cache(monkeypatch, old=True)
    monkeypatch.setattr(
        verification.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            503, request=httpx.Request("POST", "https://license.example.com")
        ),
    )
    result = verification._verify_online_key("synthetic", verification.LicenseType.PRO, "Synthetic")
    assert result.valid is True
    assert result.verified_online is False


def test_entitlement_is_rechecked_without_manual_cache_clear(monkeypatch):
    licensing.get_license.cache_clear()
    result = _result()
    monkeypatch.setattr(licensing, "verify_license", lambda **kwargs: result)
    assert licensing.get_license("synthetic").tier.value == "pro"
    result = _result(False)
    assert licensing.get_license("synthetic").tier.value == "community"


def test_testing_bypass_is_rejected_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "license_testing_mode", True)
    with pytest.raises(RuntimeError, match="LICENSE_TESTING_MODE"):
        verification.verify_license("")


def test_eslint_is_not_executed_without_repository_code_opt_in(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "enable_repo_build_tool_adapters", False)
    monkeypatch.setattr(
        tool_adapters,
        "_eslint_command",
        lambda path: pytest.fail("must not resolve repo executable"),
    )
    result = tool_adapters._run_eslint(1, tmp_path)
    assert result.status.value == "skipped"
