"""Focused regressions using synthetic data; never execute reference-folder code."""

from pathlib import Path

import httpx
import jwt
import pytest
from sqlmodel import Session

from app.core import auth_middleware, database
from app.core.config import settings
from app.core.security import AuthenticatedPrincipal, get_principal
from app.main import app
from app.models import (
    Finding,
    FindingSeverity,
    PolicyProfile,
    Project,
    Scan,
    TenantGitHubInstallation,
    ToolExecution,
)
from app.models.scm_connection import SCMConnection, SCMProvider
from app.services import scanner, scm_clone, scm_providers


def _finding(path: str, category: str = "security") -> Finding:
    return Finding(
        scan_id=1,
        tool="synthetic",
        severity=FindingSeverity.HIGH,
        title="Synthetic",
        message="Synthetic",
        category=category,
        fingerprint="synthetic",
        file_path=path,
        line=1,
    )


@pytest.mark.parametrize("outside", ["absolute", "symlink", "traversal"])
def test_context_cannot_read_outside_checkout(tmp_path: Path, outside: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    private = tmp_path / "private.txt"
    private.write_text("synthetic private value")
    (repo / "link.txt").symlink_to(private)
    path = {"absolute": str(private), "symlink": "link.txt", "traversal": "../private.txt"}
    finding = _finding(path[outside])
    scanner._attach_code_context(finding, repo)
    assert "code_context" not in (finding.tool_metadata or {})


def test_secret_context_is_omitted_but_safe_source_is_kept(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('synthetic')\n")
    secret = _finding("app.py", "secret")
    scanner._attach_code_context(secret, tmp_path)
    assert "code_context" not in (secret.tool_metadata or {})
    safe = _finding("app.py")
    scanner._attach_code_context(safe, tmp_path)
    assert safe.tool_metadata["code_context"]["lines"][0]["text"] == "print('synthetic')"


def test_first_key_still_requires_admin(api_client) -> None:
    app.dependency_overrides[get_principal] = lambda: AuthenticatedPrincipal(
        tenant_slug="default", actor="synthetic-member", scopes={"scan:read"}
    )
    try:
        response = api_client.post(
            "/api/v1/auth/api-keys", json={"name": "first", "scopes": ["admin"]}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_principal, None)


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://unrelated.example.com", "sub": "synthetic"},
        {"iss": "https://api.workos.com", "sub": "synthetic", "aud": "another-client"},
        {"iss": "https://api.workos.com"},
    ],
)
def test_jwt_rejects_unbound_claims(monkeypatch, claims) -> None:
    monkeypatch.setattr(settings, "workos_client_id", "client_synthetic")

    class Key:
        key = "unused"

    class Client:
        def get_signing_key_from_jwt(self, token):
            return Key()

    monkeypatch.setattr(auth_middleware, "get_workos_jwks_client", Client)
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: claims)
    with pytest.raises(auth_middleware.JWTVerificationError):
        auth_middleware.verify_workos_jwt("synthetic")


@pytest.mark.parametrize(
    "client",
    [
        scm_providers.GitHubClient("synthetic"),
        scm_providers.GitLabClient("synthetic"),
        scm_providers.BitbucketClient("synthetic"),
        scm_providers.AzureDevOpsClient("synthetic", extra_config={"organization": "acme"}),
    ],
)
def test_clone_credentials_cannot_leave_provider(client) -> None:
    with pytest.raises(ValueError):
        client.authenticated_clone_url("https://unrelated.example.com/acme/repo.git")


def test_azure_clone_uses_password_and_bound_organisation() -> None:
    client = scm_providers.AzureDevOpsClient(
        "synthetic:token", extra_config={"organization": "acme"}
    )
    assert client.authenticated_clone_url("https://dev.azure.com/acme/project/_git/repo") == (
        "https://pat:synthetic%3Atoken@dev.azure.com/acme/project/_git/repo"
    )
    with pytest.raises(ValueError):
        client.authenticated_clone_url("https://dev.azure.com/other/project/_git/repo")


@pytest.mark.parametrize(
    "client,url,expected",
    [
        (
            scm_providers.AzureDevOpsClient("synthetic", extra_config={"organization": "acme"}),
            "https://acme@dev.azure.com/acme/project/_git/repo",
            "https://pat:synthetic@dev.azure.com/",
        ),
        (
            scm_providers.BitbucketClient("synthetic", extra_config={"username": "account"}),
            "https://account@bitbucket.org/acme/repo.git",
            "https://account:synthetic@bitbucket.org/",
        ),
    ],
)
def test_provider_clone_username_is_replaced_safely(client, url, expected):
    assert client.authenticated_clone_url(url).startswith(expected)


def test_private_scm_opt_in_never_allows_metadata_or_url_credentials(monkeypatch):
    from fastapi import HTTPException

    from app.api.scm_connections import _validate_scm_base_url

    monkeypatch.setattr(settings, "allow_private_scm_base_urls", True)
    for url in [
        "https://169.254.169.254",
        "https://metadata.google.internal",
        "https://[fd00:ec2::254]",
        "https://[fe80::1]",
        "https://224.0.0.1",
        "https://user:pass@gitlab.local",
    ]:
        with pytest.raises(HTTPException):
            _validate_scm_base_url(SCMProvider.GITLAB, url)


def test_bitbucket_rejects_foreign_continuation_before_sending_credentials(monkeypatch) -> None:
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        assert len(calls) == 1
        return httpx.Response(
            200,
            json={"values": [], "next": "https://unrelated.example.com/next"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(scm_providers.httpx, "get", get)
    with pytest.raises(ValueError):
        scm_providers.BitbucketClient("synthetic").list_organizations()
    assert len(calls) == 1


def test_scm_resolver_rejects_another_tenants_connection(api_client, monkeypatch) -> None:
    with Session(database.engine) as session:
        conn = SCMConnection(
            tenant_slug="other",
            name="synthetic",
            provider=SCMProvider.GITHUB,
            base_url="https://api.github.com",
            encrypted_token="unused",
        )
        session.add(conn)
        session.commit()
        monkeypatch.setattr(
            scm_clone, "decrypt_token", lambda value: pytest.fail("must not decrypt")
        )
        with pytest.raises(ValueError):
            scm_clone.resolve_clone_url(
                session,
                "https://github.com/acme/repo.git",
                {"scm_connection_id": conn.id},
                tenant_slug="default",
            )


def test_assigned_policy_controls_gate_and_failed_tool_blocks_pass(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_high_findings", 0)
    with Session(database.engine) as session:
        policy = PolicyProfile(name="Assigned", max_high_findings=10)
        session.add(policy)
        session.flush()
        project = Project(key="synthetic", name="Synthetic", quality_gate_policy_id=policy.id)
        session.add(project)
        session.flush()
        scan = Scan(repo="https://example.com/repo.git", project_id=project.id)
        session.add(scan)
        session.flush()
        finding = _finding("app.py")
        finding.scan_id = scan.id
        session.add(finding)
        session.commit()
        scanner.finalize_scan(session, scan.id, {}, [], [])
        session.refresh(scan)
        assert scan.quality_gate_passed is True
        assert scan.scan_metadata["policy"]["profile_id"] == policy.id
        session.add(ToolExecution(scan_id=scan.id, tool="synthetic", status="failed"))
        session.commit()
        scanner.finalize_scan(session, scan.id, {}, ["synthetic"], [])
        session.refresh(scan)
        assert scan.quality_gate_passed is False
        assert scan.scan_metadata["incomplete_tools"] == ["synthetic"]


@pytest.mark.parametrize(
    "case", ["unconfigured", "foreign-tenant", "foreign-owner", "foreign-host"]
)
def test_github_app_binding_is_checked_before_minting(api_client, monkeypatch, case):
    monkeypatch.setattr(scm_clone, "github_app_configured", lambda: case != "unconfigured")
    monkeypatch.setattr(
        scm_clone, "_github_installation_token", lambda value: pytest.fail("must not mint")
    )
    with Session(database.engine) as session:
        session.add(
            TenantGitHubInstallation(
                tenant_slug="other" if case == "foreign-tenant" else "default",
                installation_id=17,
                account_login="acme",
            )
        )
        session.commit()
        repo = {
            "foreign-owner": "https://github.com/other/repo.git",
            "foreign-host": "https://unrelated.example.com/acme/repo.git",
        }.get(case, "https://github.com/acme/repo.git")
        with pytest.raises(ValueError):
            scm_clone.resolve_clone_url(
                session, repo, {"github": {"installation_id": 17}}, tenant_slug="default"
            )
