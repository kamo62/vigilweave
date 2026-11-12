from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import azure_marketplace, sonarqube
from app.tasks import scan_tasks

pytestmark = pytest.mark.e2e


def _create_project(
    api_client: TestClient, headers: dict[str, str], *, key: str, repo: str
) -> None:
    response = api_client.post(
        "/api/v1/projects/",
        headers=headers,
        json={"key": key, "name": key.title(), "repos": [repo]},
    )
    assert response.status_code == 201, response.text


def test_e2e_github_webhook_signature_action_and_queue(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
    sign_github_webhook,
) -> None:
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_url = "https://github.com/octo/example.git"
    _create_project(api_client, admin_headers, key="github-example", repo=repo_url)
    monkeypatch.setattr(settings, "github_webhook_secret", "gh-secret")
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(settings, "rate_limit_webhook_max_requests", 1000)
    monkeypatch.setattr(settings, "rate_limit_webhook_window_seconds", 60)
    monkeypatch.setattr(scan_tasks.run_scan, "delay", lambda scan_id: None)

    invalid = api_client.post(
        "/api/v1/webhooks/github",
        content=b'{"invalid": true}',
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=bad",
        },
    )
    assert invalid.status_code == 401

    ignored_payload = {
        "action": "closed",
        "installation": {"id": 2},
        "repository": {
            "clone_url": "https://github.com/octo/ignored.git",
            "name": "ignored",
            "owner": {"login": "octo"},
        },
        "pull_request": {
            "number": 5,
            "head": {"sha": "abc123", "ref": "feature/ignored"},
        },
    }
    ignored_raw, ignored_sig = sign_github_webhook("gh-secret", ignored_payload)
    ignored = api_client.post(
        "/api/v1/webhooks/github",
        content=ignored_raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": ignored_sig,
        },
    )
    assert ignored.status_code == 200
    assert ignored.json()["scan_id"] is None
    assert ignored.json()["accepted"] is True

    accepted_payload = {
        "action": "opened",
        "installation": {"id": 2},
        "repository": {
            "clone_url": repo_url,
            "name": "example",
            "owner": {"login": "octo"},
        },
        "pull_request": {
            "number": 9,
            "head": {"sha": "abcdef", "ref": "feature/auth"},
            "html_url": "https://github.com/octo/example/pull/9",
        },
    }
    accepted_raw, accepted_sig = sign_github_webhook("gh-secret", accepted_payload)
    accepted = api_client.post(
        "/api/v1/webhooks/github",
        content=accepted_raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-e2e",
            "X-Hub-Signature-256": accepted_sig,
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["scan_id"] is not None

    unsafe_payload = {
        "action": "opened",
        "installation": {"id": 2},
        "repository": {
            "clone_url": "ssh://github.com/octo/example.git",
            "name": "example",
            "owner": {"login": "octo"},
        },
        "pull_request": {
            "number": 10,
            "head": {"sha": "abcdef", "ref": "feature/unsafe"},
        },
    }
    unsafe_raw, unsafe_sig = sign_github_webhook("gh-secret", unsafe_payload)
    unsafe = api_client.post(
        "/api/v1/webhooks/github",
        content=unsafe_raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": unsafe_sig,
        },
    )
    assert unsafe.status_code == 400

    scans = api_client.get("/api/v1/scans/", headers=admin_headers)
    assert scans.status_code == 200
    assert any(
        scan["source"] == "github-app" and scan["project_key"] == "github-example"
        for scan in scans.json()
    )


def test_e2e_azure_marketplace_onboarding_bearer_and_basic(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    seen_auth_headers: list[str] = []

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> _FakeResponse:
        assert "api-version=7.1-preview.4" in url
        assert timeout == 20.0
        seen_auth_headers.append(headers["Authorization"])
        return _FakeResponse({"id": "project-id-1"})

    def fake_post(
        url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float
    ) -> _FakeResponse:
        assert "api-version=7.1" in url
        assert json["publisherId"] == "tfs"
        assert json["consumerId"] == "webHooks"
        assert timeout == 20.0
        seen_auth_headers.append(headers["Authorization"])
        return _FakeResponse({"id": f"subscription-{json['eventType']}", "status": "enabled"})

    monkeypatch.setattr(azure_marketplace.httpx, "get", fake_get)
    monkeypatch.setattr(azure_marketplace.httpx, "post", fake_post)

    bearer = api_client.post(
        "/api/v1/integrations/azure-devops/onboard-project",
        headers=admin_headers,
        json={
            "organization_url": "https://dev.azure.com/example-org",
            "project": "Payments",
            "access_token": "ado-bearer-token",
            "auth_scheme": "bearer",
            "webhook_url": "https://vigilweave.example.com/api/v1/webhooks/azure-devops",
            "events": ["git.pullrequest.created", "git.pullrequest.updated"],
        },
    )
    assert bearer.status_code == 201
    assert bearer.json()["subscriptions_created"] == 2

    basic = api_client.post(
        "/api/v1/integrations/azure-devops/onboard-project",
        headers=admin_headers,
        json={
            "organization_url": "https://dev.azure.com/example-org",
            "project": "Payments",
            "access_token": "ado-basic-token",
            "auth_scheme": "basic",
            "webhook_url": "https://vigilweave.example.com/api/v1/webhooks/azure-devops",
            "events": ["git.pullrequest.created"],
        },
    )
    assert basic.status_code == 201
    assert basic.json()["subscriptions_created"] == 1

    basic_prefix = "Basic " + base64.b64encode(b":ado-basic-token").decode("ascii")
    assert any(header == "Bearer ado-bearer-token" for header in seen_auth_headers)
    assert any(header == basic_prefix for header in seen_auth_headers)


def test_e2e_azure_webhook_security_and_event_handling(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
) -> None:
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_url = "https://dev.azure.com/example-org/payments/_git/repo"
    _create_project(api_client, admin_headers, key="azure-payments", repo=repo_url)
    monkeypatch.setattr(settings, "azure_webhook_secret", "az-secret")
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(settings, "rate_limit_webhook_max_requests", 1000)
    monkeypatch.setattr(settings, "rate_limit_webhook_window_seconds", 60)
    monkeypatch.setattr(scan_tasks.run_scan, "delay", lambda scan_id: None)

    unauthorized = api_client.post(
        "/api/v1/webhooks/azure-devops",
        json={"eventType": "git.pullrequest.created", "resource": {}},
    )
    assert unauthorized.status_code == 401

    ignored = api_client.post(
        "/api/v1/webhooks/azure-devops",
        headers={"X-VigilWeave-Webhook-Secret": "az-secret"},
        json={"eventType": "build.complete", "resource": {}},
    )
    assert ignored.status_code == 200
    assert ignored.json()["message"] == "Event ignored"

    missing_repo = api_client.post(
        "/api/v1/webhooks/azure-devops",
        headers={"X-CodeGuard-Webhook-Secret": "az-secret"},
        json={"eventType": "git.pullrequest.updated", "resource": {"repository": {}}},
    )
    assert missing_repo.status_code == 200
    assert missing_repo.json()["accepted"] is False

    accepted = api_client.post(
        "/api/v1/webhooks/azure-devops",
        headers={"X-VigilWeave-Webhook-Secret": "az-secret"},
        json={
            "eventType": "git.pullrequest.created",
            "resource": {
                "pullRequestId": 12,
                "sourceRefName": "refs/heads/feature/e2e",
                "repository": {
                    "remoteUrl": repo_url,
                    "project": {"id": "proj-1"},
                },
                "sourceCommit": {"commitId": "123abc"},
            },
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["scan_id"] is not None

    unsupported = api_client.post(
        "/api/v1/webhooks/azure-devops",
        headers={"X-VigilWeave-Webhook-Secret": "az-secret"},
        json={
            "eventType": "git.pullrequest.created",
            "resource": {
                "pullRequestId": 13,
                "sourceRefName": "refs/heads/feature/unsafe",
                "repository": {
                    "remoteUrl": "ssh://dev.azure.com/example-org/payments/_git/repo",
                    "project": {"id": "proj-1"},
                },
                "sourceCommit": {"commitId": "123abc"},
            },
        },
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["accepted"] is False

    scans = api_client.get("/api/v1/scans/", headers=admin_headers)
    assert scans.status_code == 200
    assert any(
        scan["source"] == "azure-service-hook" and scan["project_key"] == "azure-payments"
        for scan in scans.json()
    )


def test_e2e_sonar_sync_error_path(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    def fake_get(*args: Any, **kwargs: Any):  # noqa: ANN401
        raise httpx.ConnectError("sonarqube unavailable")

    monkeypatch.setattr(sonarqube.httpx, "get", fake_get)

    failed = api_client.post(
        "/api/v1/integrations/sonarqube/rules/sync",
        headers=admin_headers,
        json={
            "base_url": "https://sonarqube.example.com",
            "token": "token",
            "language": "python",
        },
    )
    assert failed.status_code == 500
