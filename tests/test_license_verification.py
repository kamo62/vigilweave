"""Tests for license verification system."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.core.config import settings
from app.models import SaaSTenantTier
from app.services.license_verification import (
    LicenseType,
    VerificationResult,
    _license_cache_key,
    _load_license_cache,
    _parse_license_key,
    _save_license_cache,
    verify_license,
)


class TestParseLicenseKey:
    """Test license key parsing."""

    def test_parse_community_no_key(self) -> None:
        """Test parsing when no key provided."""
        license_type, org, hash_part = _parse_license_key("")
        assert license_type == LicenseType.COMMUNITY
        assert org == ""
        assert hash_part is None

    def test_parse_community_none(self) -> None:
        """Test parsing None key."""
        license_type, org, hash_part = _parse_license_key(None)
        assert license_type == LicenseType.COMMUNITY

    def test_parse_pro_key(self) -> None:
        """Test parsing Pro license key."""
        key = "vw-pro-acme-corp-a1b2c3d4"
        license_type, org, hash_part = _parse_license_key(key)
        assert license_type == LicenseType.PRO
        assert org == "acme-corp"
        assert hash_part == "a1b2c3d4"

    def test_parse_enterprise_standard_key(self) -> None:
        """Test parsing Enterprise Standard license key."""
        key = "vw-ent-acme-corp-a1b2c3d4"
        license_type, org, hash_part = _parse_license_key(key)
        assert license_type == LicenseType.ENTERPRISE_STANDARD
        assert org == "acme-corp"
        assert hash_part == "a1b2c3d4"

    def test_parse_enterprise_offline_key(self) -> None:
        """Test parsing Enterprise Offline license key."""
        key = "vw-ent-offline-acme-corp-a1b2c3d4e5f6"
        license_type, org, signature = _parse_license_key(key)
        assert license_type == LicenseType.ENTERPRISE_OFFLINE
        assert org == "acme-corp"
        assert signature == "a1b2c3d4e5f6"

    def test_parse_invalid_key_format(self) -> None:
        """Test parsing invalid key format."""
        key = "invalid-key-format"
        license_type, org, hash_part = _parse_license_key(key)
        assert license_type == LicenseType.COMMUNITY


class TestVerifyLicenseCommunity:
    """Test Community license verification."""

    def test_verify_community_no_key(self) -> None:
        """Test verifying with no license key."""
        result = verify_license("")
        assert result.valid is True
        assert result.license_type == LicenseType.COMMUNITY
        assert result.tier == "community"
        assert result.features == []
        assert result.verified_online is False

    def test_verify_community_none_key(self) -> None:
        """Test verifying with None license key."""
        result = verify_license(None)
        assert result.valid is True
        assert result.license_type == LicenseType.COMMUNITY

    def test_verify_invalid_key_format(self) -> None:
        """Test verifying invalid key format falls back to community."""
        result = verify_license("invalid-key")
        assert result.valid is True  # Community is always "valid"
        assert result.license_type == LicenseType.COMMUNITY

    def test_community_distribution_ignores_paid_license_keys(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "distribution_mode", "community")

        result = verify_license("vw-ent-acme-corp-a1b2c3d4")

        assert result.valid is True
        assert result.license_type == LicenseType.COMMUNITY
        assert result.tier == "community"
        assert result.features == []

    def test_verify_hosted_saas_defaults_to_enterprise_when_no_license_key(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "saas_enabled", True)
        monkeypatch.setattr(settings, "auth_mode", "workos")
        monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
        monkeypatch.setattr(settings, "license_key", None)

        result = verify_license(None)

        assert result.valid is True
        assert result.license_type == LicenseType.ENTERPRISE_STANDARD
        assert result.tier == "enterprise"
        assert result.organization == "VigilWeave Cloud"
        assert "executive_reporting" in result.features

    def test_verify_hosted_saas_uses_tenant_override(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "saas_enabled", True)
        monkeypatch.setattr(settings, "auth_mode", "workos")
        monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
        monkeypatch.setattr(settings, "license_key", None)
        monkeypatch.setattr(
            "app.services.license_verification._resolve_hosted_tenant_tier",
            lambda tenant_slug: (
                SaaSTenantTier.PRO
                if tenant_slug == "workos-org-acme"
                else SaaSTenantTier.ENTERPRISE
            ),
        )

        result = verify_license(None, tenant_slug="workos-org-acme")

        assert result.valid is True
        assert result.license_type == LicenseType.PRO
        assert result.tier == "pro"
        assert "executive_reporting" not in result.features


class TestVerifyOfflineEnterpriseKey:
    """Test Enterprise Offline license verification."""

    def test_verify_valid_offline_key(self, tmp_path) -> None:
        """Test verifying a valid offline enterprise key."""
        with patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"):
            # Generate a valid signature for test org
            import hashlib
            import hmac

            org = "testcorp"
            expected_secret = f"vigilweave-offline-{org}-secret"
            payload = f"vw-ent-offline-{org}"
            valid_signature = hmac.new(
                expected_secret.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()[:32]

            key = f"vw-ent-offline-{org}-{valid_signature}"

            result = verify_license(key)

            assert result.valid is True
            assert result.license_type == LicenseType.ENTERPRISE_OFFLINE
            assert result.tier == "enterprise"
            assert result.organization == org
            assert result.verified_online is False
            # Should have all enterprise features
            assert "bulk_triage" in result.features
            assert "executive_reporting" in result.features

    def test_verify_invalid_signature(self, tmp_path) -> None:
        """Test verifying offline key with invalid signature."""
        with patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"):
            key = "vw-ent-offline-testcorp-invalidsignature123"

            result = verify_license(key)

            assert result.valid is False
            assert result.license_type == LicenseType.COMMUNITY
            assert "Invalid license key signature" in (result.error_message or "")

    def test_verify_offline_key_expiration(self, tmp_path) -> None:
        """Test offline key expiration."""
        with patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"):
            import hashlib
            import hmac

            org = "testcorp"
            expected_secret = f"vigilweave-offline-{org}-secret"
            payload = f"vw-ent-offline-{org}"
            valid_signature = hmac.new(
                expected_secret.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()[:32]

            key = f"vw-ent-offline-{org}-{valid_signature}"

            # First verification - should succeed and create cache
            result1 = verify_license(key)
            assert result1.valid is True

            # Manually expire the cache by setting expires_at to past
            cache_data = _load_license_cache()
            cache_key = f"offline_ent_{org}"
            past_date = datetime(2020, 1, 1, tzinfo=UTC)
            cache_data[cache_key] = {
                "first_seen": past_date.isoformat(),
                "expires_at": past_date.isoformat(),
            }
            _save_license_cache(cache_data)

            # Verify again - should fail due to expiration
            result2 = verify_license(key)
            assert result2.valid is False
            assert "expired" in (result2.error_message or "").lower()


class TestLicenseCache:
    """Test license cache operations."""

    def test_load_save_cache(self, tmp_path) -> None:
        """Test loading and saving license cache."""
        with patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"):
            test_data = {
                "test_key": {
                    "valid": True,
                    "tier": "pro",
                    "cached_at": datetime.now(UTC).isoformat(),
                }
            }

            _save_license_cache(test_data)
            loaded = _load_license_cache()

            assert loaded["test_key"]["valid"] is True
            assert loaded["test_key"]["tier"] == "pro"

    def test_load_nonexistent_cache(self, tmp_path) -> None:
        """Test loading cache when file doesn't exist."""
        with patch(
            "app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "nonexistent.json"
        ):
            loaded = _load_license_cache()
            assert loaded == {}


class TestOnlineKeyVerification:
    """Test online license verification (Pro and Enterprise Standard)."""

    def test_pro_key_online_verification(self, tmp_path) -> None:
        """Test Pro key online verification with a mocked license server."""
        with (
            patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"),
            patch("app.services.license_verification._call_license_server") as mock_verify,
        ):
            key = "vw-pro-acme-testhash123"
            mock_verify.return_value = VerificationResult(
                valid=True,
                license_type=LicenseType.PRO,
                tier="pro",
                organization="acme",
                expires_at=None,
                features=["bulk_triage", "reporting"],
                verified_online=True,
            )

            result = verify_license(key)

            assert result.valid is True
            assert result.license_type == LicenseType.PRO
            assert result.tier == "pro"
            assert result.organization == "acme"
            assert result.verified_online is True
            assert "bulk_triage" in result.features
            assert "reporting" in result.features
            assert "executive_reporting" not in result.features
            mock_verify.assert_called_once_with(key, LicenseType.PRO, "acme")

    def test_enterprise_standard_online_verification(self, tmp_path) -> None:
        """Test Enterprise Standard online verification with a mocked server."""
        with (
            patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"),
            patch("app.services.license_verification._call_license_server") as mock_verify,
        ):
            key = "vw-ent-acme-testhash123"
            mock_verify.return_value = VerificationResult(
                valid=True,
                license_type=LicenseType.ENTERPRISE_STANDARD,
                tier="enterprise",
                organization="acme",
                expires_at=None,
                features=["bulk_triage", "reporting", "executive_reporting"],
                verified_online=True,
            )

            result = verify_license(key)

            assert result.valid is True
            assert result.license_type == LicenseType.ENTERPRISE_STANDARD
            assert result.tier == "enterprise"
            assert result.organization == "acme"
            assert result.verified_online is True
            assert "executive_reporting" in result.features
            mock_verify.assert_called_once_with(key, LicenseType.ENTERPRISE_STANDARD, "acme")

    def test_cached_result_used(self, tmp_path) -> None:
        """Test that cached results are used when available."""
        with (
            patch("app.services.license_verification.LICENSE_CACHE_FILE", tmp_path / "cache.json"),
            patch("app.services.license_verification._call_license_server") as mock_verify,
        ):
            key = "vw-pro-acme-testhash123"
            cache_key = _license_cache_key(key)

            # Pre-populate cache
            cache_data = {
                cache_key: {
                    "valid": True,
                    "license_type": "pro",
                    "tier": "pro",
                    "organization": "cached-org",
                    "expires_at": None,
                    "features": ["bulk_triage"],
                    "cached_at": datetime.now(UTC).isoformat(),
                }
            }
            _save_license_cache(cache_data)

            # Verify - should use cached result
            result = verify_license(key)

            assert result.valid is True
            assert result.organization == "cached-org"
            assert result.verified_online is False  # Cached result, not online
            mock_verify.assert_not_called()

    def test_cache_keys_do_not_collide_on_shared_prefixes(self) -> None:
        """Test online cache keys use the full license key digest, not a short prefix."""

        key_a = "vw-pro-acme-shared-prefix-aaaaaaaa"
        key_b = "vw-pro-acme-shared-prefix-bbbbbbbb"

        assert key_a[:20] == key_b[:20]
        assert _license_cache_key(key_a) != _license_cache_key(key_b)


class TestVerificationResult:
    """Test VerificationResult dataclass."""

    def test_verification_result_creation(self) -> None:
        """Test creating VerificationResult."""
        result = VerificationResult(
            valid=True,
            license_type=LicenseType.PRO,
            tier="pro",
            organization="test",
            expires_at=datetime.now(UTC),
            features=["feature1", "feature2"],
            verified_online=True,
        )

        assert result.valid is True
        assert result.license_type == LicenseType.PRO
        assert result.tier == "pro"
        assert result.organization == "test"
        assert len(result.features) == 2

    def test_verification_result_with_error(self) -> None:
        """Test VerificationResult with error message."""
        result = VerificationResult(
            valid=False,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message="License server unavailable",
            verified_online=False,
        )

        assert result.valid is False
        assert result.error_message == "License server unavailable"
