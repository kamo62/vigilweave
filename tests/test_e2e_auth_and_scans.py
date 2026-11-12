from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

pytestmark = pytest.mark.e2e


def _csrf_headers(api_client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    response = api_client.get("/api/v1/auth/csrf", headers=headers)
    assert response.status_code == 200, response.text
    token = response.json()["csrf_token"]
    return {**headers, "X-CSRF-Token": token}


def test_e2e_auth_bootstrap_scope_tenant_and_revoke(
    api_client: TestClient,
    bootstrap_api_key,
    cross_tenant_api_key,
    pro_license,
) -> None:
    del pro_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    bootstrap_locked = api_client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "anonymous-bootstrap-attempt",
            "scopes": ["scan:read"],
        },
    )
    assert bootstrap_locked.status_code == 401

    list_keys = api_client.get("/api/v1/auth/api-keys", headers=admin_headers)
    assert list_keys.status_code == 200
    assert len(list_keys.json()) == 1
    assert list_keys.json()[0]["tenant_slug"] == "acme"

    readonly_create = api_client.post(
        "/api/v1/auth/api-keys",
        headers=_csrf_headers(api_client, admin_headers),
        json={
            "name": "acme-readonly",
            "scopes": ["scan:read"],
        },
    )
    assert readonly_create.status_code == 201
    readonly_payload = readonly_create.json()
    readonly_headers = {
        "Authorization": f"Bearer {readonly_payload['api_key']}",
        "X-VigilWeave-Tenant": "acme",
    }

    denied = api_client.post(
        "/api/v1/policies/",
        headers=readonly_headers,
        json={
            "name": "readonly-denied",
            "is_default": False,
            "max_critical_findings": 0,
            "max_high_findings": 0,
            "min_quality_score": 90,
        },
    )
    assert denied.status_code == 403

    revoked = api_client.delete(
        f"/api/v1/auth/api-keys/{readonly_payload['record']['id']}",
        headers=_csrf_headers(api_client, admin_headers),
    )
    assert revoked.status_code == 204

    revoked_request = api_client.get("/api/v1/scans/", headers=readonly_headers)
    assert revoked_request.status_code == 401

    # Cross-tenant key creation through the API is correctly blocked —
    # the tenant_slug field was removed from ApiKeyCreate to prevent
    # admins minting keys for arbitrary tenants.
    cross_tenant_attempt = api_client.post(
        "/api/v1/auth/api-keys",
        headers={
            **_csrf_headers(api_client, admin_headers),
            "X-VigilWeave-Tenant": "other",
        },
        json={
            "name": "other-admin",
            "scopes": ["admin", "scan:read", "scan:write"],
        },
    )
    assert cross_tenant_attempt.status_code == 403

    # Cross-tenant isolation still works — keys created directly in
    # separate tenants only see their own data.
    other_headers = cross_tenant_api_key(tenant_slug="other", name="other-admin")

    other_keys = api_client.get("/api/v1/auth/api-keys", headers=other_headers)
    assert other_keys.status_code == 200
    assert other_keys.json()
    assert all(item["tenant_slug"] == "other" for item in other_keys.json())


def test_e2e_api_key_mutation_requires_csrf(
    api_client: TestClient,
    bootstrap_api_key,
    pro_license,
) -> None:
    del pro_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    create_without_csrf = api_client.post(
        "/api/v1/auth/api-keys",
        headers=admin_headers,
        json={
            "name": "csrf-missing",
            "scopes": ["scan:read"],
        },
    )
    assert create_without_csrf.status_code == 201

    me = api_client.get("/api/v1/auth/me")
    assert me.status_code == 401

    create_with_csrf = api_client.post(
        "/api/v1/auth/api-keys",
        headers=_csrf_headers(api_client, admin_headers),
        json={
            "name": "csrf-present",
            "scopes": ["scan:read"],
        },
    )
    assert create_with_csrf.status_code == 201


def test_e2e_session_cookie_mutation_requires_csrf_on_project_routes(
    api_client: TestClient,
    cross_tenant_api_key,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "session_auth_provider", "local")
    monkeypatch.setattr(settings, "api_keys_enabled", True)
    monkeypatch.setattr(settings, "saas_enabled", False)
    admin_headers = cross_tenant_api_key(tenant_slug="default", name="default-admin")

    csrf = api_client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200

    setup = api_client.post(
        "/api/v1/auth/local/setup",
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
    )
    assert setup.status_code == 201

    blocked = api_client.post(
        "/api/v1/projects/",
        headers=admin_headers,
        json={
            "key": "csrf-guarded-project",
            "name": "CSRF Guarded Project",
            "repos": [],
        },
    )
    assert blocked.status_code == 403
    assert "CSRF token" in blocked.text

    allowed = api_client.post(
        "/api/v1/projects/",
        headers=_csrf_headers(api_client, admin_headers),
        json={
            "key": "csrf-guarded-project",
            "name": "CSRF Guarded Project",
            "repos": [],
        },
    )
    assert allowed.status_code == 201


def test_e2e_scan_policy_match_waiver_and_reporting(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_path = git_repo_factory(
        name="scan-policy-repo",
        initial_files={
            "app.py": "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
            "main.tf": 'resource "aws_security_group" "open" {\n  name = "open"\n}\n',
        },
    )
    repo_url = f"file://{repo_path}"

    policy = api_client.post(
        "/api/v1/policies/",
        headers=admin_headers,
        json={
            "name": "strict-default",
            "description": "Block high findings",
            "is_default": True,
            "max_critical_findings": 0,
            "max_high_findings": 0,
            "min_quality_score": 40,
        },
    )
    assert policy.status_code == 201

    waiver = api_client.post(
        "/api/v1/policies/waivers",
        headers=admin_headers,
        json={
            "repo_pattern": repo_url,
            "category": "secret",
            "reason": "Accepted temporary secret during migration",
            "created_by": "acme-admin",
        },
    )
    assert waiver.status_code == 201

    created = api_client.post(
        "/api/v1/scans/",
        headers=admin_headers,
        json={
            "repo": repo_url,
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert created.status_code == 201
    scan = created.json()
    assert scan["status"] == "completed"
    assert scan["scan_metadata"]["policy"]["matched"] is True
    assert scan["scan_metadata"]["policy"]["passed"] is False
    assert any("High findings" in reason for reason in scan["scan_metadata"]["policy"]["reasons"])
    assert scan["suppressed_findings"] >= 1

    findings = api_client.get(f"/api/v1/scans/{scan['id']}/findings", headers=admin_headers)
    assert findings.status_code == 200
    assert findings.json()
    categories = {item["category"] for item in findings.json()}
    assert "secret" not in categories
    assert "security" in categories

    suppressed = api_client.get(
        f"/api/v1/scans/{scan['id']}/findings",
        headers=admin_headers,
        params={"include_suppressed": "true"},
    )
    assert suppressed.status_code == 200
    assert any(item["is_suppressed"] for item in suppressed.json())

    stats = api_client.get(f"/api/v1/scans/{scan['id']}/findings/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert stats.json()["total_findings"] >= 1

    quality = api_client.get(f"/api/v1/scans/{scan['id']}/quality-metrics", headers=admin_headers)
    assert quality.status_code == 200
    assert quality.json()["files"]

    sarif = api_client.get(f"/api/v1/scans/{scan['id']}/sarif", headers=admin_headers)
    assert sarif.status_code == 200
    sarif_payload = sarif.json()
    assert sarif_payload["version"] == "2.1.0"
    run = sarif_payload["runs"][0]
    assert any(rule.get("helpUri") for rule in run["tool"]["driver"]["rules"])
    assert any(rule.get("properties", {}).get("tags") for rule in run["tool"]["driver"]["rules"])

    summary = api_client.get("/api/v1/repositories/summary", headers=admin_headers)
    assert summary.status_code == 200
    assert any(item["repo"] == repo_url for item in summary.json())

    audit = api_client.get("/api/v1/policies/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert any(item["action"] == "waiver.applied" for item in audit.json())


def test_e2e_scan_policy_no_match_metadata(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    pro_license,
) -> None:
    del pro_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_path = git_repo_factory(name="scan-no-match-repo")
    repo_url = f"file://{repo_path}"

    policy = api_client.post(
        "/api/v1/policies/",
        headers=admin_headers,
        json={
            "name": "non-default-mismatch",
            "repo_pattern": "https://example.invalid/*",
            "is_default": False,
            "max_critical_findings": 0,
            "max_high_findings": 0,
            "min_quality_score": 90,
        },
    )
    assert policy.status_code == 201

    created = api_client.post(
        "/api/v1/scans/",
        headers=admin_headers,
        json={
            "repo": repo_url,
            "scan_type": "fast",
            "include_quality_metrics": True,
        },
    )
    assert created.status_code == 201
    scan = created.json()
    assert scan["status"] == "completed"
    assert scan["scan_metadata"]["policy"]["matched"] is True
    assert scan["scan_metadata"]["policy"]["profile_name"] in {"Balanced", "Lenient", "Strict"}
