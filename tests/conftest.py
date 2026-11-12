"""Shared fixtures use synthetic accounts, passwords, tokens, and test licence keys only."""

import hashlib
import hmac
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.core import licensing as licensing_module
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.licensing import get_license
from app.main import app
from app.models import Finding, FindingSeverity, ToolExecutionStatus
from app.services import config_loader
from app.services import scanner as scanner_module
from app.services.license_verification import LicenseType, VerificationResult
from app.services.tool_adapters import ToolRunResult


@pytest.fixture(autouse=True)
def stub_native_tool_execution(monkeypatch) -> None:
    """Keep API tests deterministic without requiring local scanner binaries."""

    def _fake_run_tool(
        scan_id: int,
        repo_path: Path,
        tool: str,
        *,
        tool_config: dict[str, Any] | None = None,
    ) -> ToolRunResult:
        del repo_path, tool_config
        findings: list[Finding] = []

        if tool == "gitleaks":
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool=tool,
                    scan_source="native",
                    severity=FindingSeverity.MEDIUM,
                    title="Hardcoded secret",
                    message="Potential secret detected",
                    description="Synthetic fixture finding for test determinism.",
                    category="secret",
                    file_path="app.py",
                    line=1,
                    rule_id="test-secret",
                    fingerprint=_fingerprint(tool, scan_id, "secret"),
                )
            )

        if tool == "semgrep":
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool=tool,
                    scan_source="native",
                    severity=FindingSeverity.HIGH,
                    title="Unsafe code path",
                    message="Potential security issue detected",
                    description="https://example.com/rules/test-security",
                    category="security",
                    file_path="app.py",
                    line=2,
                    rule_id="test-security",
                    cwe_id="79",
                    owasp_category="A03:2021",
                    fingerprint=_fingerprint(tool, scan_id, "security"),
                )
            )

        status = ToolExecutionStatus.COMPLETED
        summary = f"{tool} fixture execution"
        return ToolRunResult(findings=findings, summary=summary, status=status, version="test")

    monkeypatch.setattr(scanner_module, "run_tool", _fake_run_tool)


@pytest.fixture(autouse=True)
def clear_tool_config_cache_between_tests() -> None:
    """Ensure per-test tool config state does not leak across suites."""

    config_loader.clear_tool_config_cache()
    yield
    config_loader.clear_tool_config_cache()


@pytest.fixture(autouse=True)
def force_legacy_api_key_auth_for_tests(monkeypatch) -> None:
    """Keep existing backend tests on the legacy API-key-only auth path by default."""

    monkeypatch.setattr(settings, "auth_mode", "api_key")
    monkeypatch.setattr(settings, "session_auth_provider", "local")
    monkeypatch.setattr(settings, "api_keys_enabled", True)


@pytest.fixture(autouse=True)
def configure_token_encryption_for_tests(monkeypatch) -> None:
    """Provide a deterministic encryption secret for SCM connection fixtures."""

    monkeypatch.setattr(settings, "token_encryption_key", "test-token-encryption-key")


@pytest.fixture(autouse=True)
def enable_file_repo_access_for_tests(tmp_path: Path, monkeypatch) -> None:
    """Keep file:// repository tests working under the tightened repo access policy."""

    monkeypatch.setattr(settings, "enable_file_repo_access", True)
    monkeypatch.setattr(settings, "host_repo_root", str(tmp_path))
    monkeypatch.setattr(settings, "container_repo_root", str(tmp_path))


@pytest.fixture(autouse=True)
def force_eager_scan_execution(monkeypatch) -> None:
    """Keep non-e2e tests off external brokers and result backends by default."""

    original_task_always_eager = celery_app.conf.task_always_eager
    monkeypatch.setattr(settings, "celery_task_always_eager", True)
    celery_app.conf.task_always_eager = True
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = original_task_always_eager


def _fingerprint(tool: str, scan_id: int, finding_type: str) -> str:
    return hashlib.sha1(f"{tool}:{scan_id}:{finding_type}".encode("utf-8")).hexdigest()


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch) -> TestClient:
    """Return a TestClient wired to an isolated SQLite database."""

    db_path = tmp_path / "api-e2e.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def bootstrap_api_key(api_client: TestClient) -> Callable[..., dict[str, str]]:
    """Create API keys via the API and return standard auth headers.

    All keys created through this fixture belong to the authenticated
    principal's tenant.  For cross-tenant test scenarios use the
    ``cross_tenant_api_key`` fixture instead.
    """

    def _bootstrap(
        *,
        tenant_slug: str = "acme",
        name: str = "e2e-admin",
        scopes: list[str] | None = None,
        actor_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        payload = {
            "name": name,
            "scopes": scopes or ["admin", "scan:read", "scan:write"],
        }
        bootstrap_headers = dict(actor_headers) if actor_headers else {}
        bootstrap_headers["X-VigilWeave-Tenant"] = tenant_slug
        response = api_client.post(
            "/api/v1/auth/api-keys",
            json=payload,
            headers=bootstrap_headers,
        )
        assert response.status_code == 201, response.text
        api_key = response.json()["api_key"]
        return {
            "Authorization": f"Bearer {api_key}",
            "X-VigilWeave-Tenant": tenant_slug,
        }

    return _bootstrap


@pytest.fixture
def cross_tenant_api_key() -> Callable[..., dict[str, str]]:
    """Create an API key directly in the DB for a specific tenant.

    Use this for tests that verify cross-tenant isolation where the API
    correctly prevents one tenant's admin from minting keys for another.
    """
    from app.core.security import generate_api_key, hash_api_key
    from app.models import ApiKeyRecord

    def _create(
        *,
        tenant_slug: str,
        name: str = "cross-tenant-admin",
        scopes: list[str] | None = None,
    ) -> dict[str, str]:
        from sqlmodel import Session as DBSession

        scopes = scopes or ["admin", "scan:read", "scan:write"]
        prefix, secret = generate_api_key()
        record = ApiKeyRecord(
            tenant_slug=tenant_slug,
            name=name,
            key_prefix=prefix,
            key_hash=hash_api_key(secret),
            scopes=scopes,
        )
        with DBSession(database_module.engine) as session:
            session.add(record)
            session.commit()
        return {
            "Authorization": f"Bearer {secret}",
            "X-VigilWeave-Tenant": tenant_slug,
        }

    return _create


@pytest.fixture
def git_repo_factory(tmp_path: Path) -> Callable[..., Path]:
    """Create local git repositories with one or more commits."""

    def _create_repo(
        *,
        name: str = "sample-repo",
        initial_files: dict[str, str] | None = None,
        second_commit_files: dict[str, str] | None = None,
    ) -> Path:
        repo_path = tmp_path / name
        repo_path.mkdir(parents=True, exist_ok=True)
        files = initial_files or {
            "app.py": "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
            "Dockerfile": "FROM python:3.14.3-slim\nUSER root\n",
        }
        for file_path, content in files.items():
            target = repo_path / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.email", "e2e@example.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(["git", "config", "user.name", "E2E User"], cwd=repo_path, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, check=True)

        if second_commit_files:
            for file_path, content in second_commit_files.items():
                target = repo_path / file_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "second"], cwd=repo_path, check=True)

        return repo_path

    return _create_repo


@pytest.fixture
def sign_github_webhook() -> Callable[[str, dict[str, Any]], tuple[bytes, str]]:
    """Return encoded payload bytes and a matching GitHub webhook signature."""

    def _sign(secret: str, payload: dict[str, Any]) -> tuple[bytes, str]:
        raw = json.dumps(payload).encode("utf-8")
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        return raw, signature

    return _sign


@pytest.fixture
def set_license_key(monkeypatch) -> Callable[[str | None], None]:
    """Set the active license key for the duration of a test."""

    original = settings.license_key

    pro_features = [
        "bulk_triage",
        "custom_policies",
        "notifications",
        "scan_scheduling",
        "reporting",
        "audit_extended",
    ]
    enterprise_features = pro_features + [
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

    def _fake_verify_license(
        key: str | None = None,
        tenant_slug: str | None = None,
    ) -> VerificationResult:
        del tenant_slug
        active_key = settings.license_key if key is None else key

        if not active_key:
            return VerificationResult(
                valid=True,
                license_type=LicenseType.COMMUNITY,
                tier="community",
                organization=None,
                expires_at=None,
                features=[],
                verified_online=False,
            )

        if active_key.startswith("vw-pro-"):
            organization = active_key.removeprefix("vw-pro-").rsplit("-", 1)[0]
            return VerificationResult(
                valid=True,
                license_type=LicenseType.PRO,
                tier="pro",
                organization=organization,
                expires_at=None,
                features=pro_features,
                verified_online=True,
            )

        if active_key.startswith("vw-ent-offline-"):
            organization = active_key.removeprefix("vw-ent-offline-").rsplit("-", 1)[0]
            return VerificationResult(
                valid=True,
                license_type=LicenseType.ENTERPRISE_OFFLINE,
                tier="enterprise",
                organization=organization,
                expires_at=None,
                features=enterprise_features,
                verified_online=False,
            )

        if active_key.startswith("vw-ent-"):
            organization = active_key.removeprefix("vw-ent-").rsplit("-", 1)[0]
            return VerificationResult(
                valid=True,
                license_type=LicenseType.ENTERPRISE_STANDARD,
                tier="enterprise",
                organization=organization,
                expires_at=None,
                features=enterprise_features,
                verified_online=True,
            )

        return VerificationResult(
            valid=True,
            license_type=LicenseType.COMMUNITY,
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            verified_online=False,
        )

    monkeypatch.setattr(licensing_module, "verify_license", _fake_verify_license)

    def _set(value: str | None) -> None:
        monkeypatch.setattr(settings, "license_key", value)
        get_license.cache_clear()

    yield _set
    monkeypatch.setattr(settings, "license_key", original)
    get_license.cache_clear()


@pytest.fixture
def community_license(set_license_key) -> None:
    set_license_key(None)


@pytest.fixture
def pro_license(set_license_key) -> None:
    set_license_key("vw-pro-tests-acme")


@pytest.fixture
def enterprise_license(set_license_key) -> None:
    set_license_key("vw-ent-tests-acme")
