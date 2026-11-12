import hashlib
import hmac
import json as json_module
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.core.config import settings
from app.main import app
from app.services import azure_marketplace
from app.tasks import scan_tasks


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "devops-integrations.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def _bootstrap_key(client: TestClient, tenant_slug: str = "acme") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "integration-admin",
            "scopes": ["admin", "scan:read", "scan:write"],
        },
        headers={"X-VigilWeave-Tenant": tenant_slug},
    )
    assert response.status_code == 201
    api_key = response.json()["api_key"]
    return {
        "Authorization": f"Bearer {api_key}",
        "X-VigilWeave-Tenant": tenant_slug,
    }


def _create_project(client: TestClient, headers: dict[str, str], *, key: str, repo: str) -> None:
    response = client.post(
        "/api/v1/projects/",
        headers=headers,
        json={"key": key, "name": key.title(), "repos": [repo]},
    )
    assert response.status_code == 201, response.text


def test_github_webhook_creates_scan(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client, tenant_slug="acme")
    repo_url = "https://github.com/octo/example.git"
    _create_project(client, headers, key="github-example", repo=repo_url)

    monkeypatch.setattr(settings, "github_webhook_secret", "test-secret")
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(scan_tasks.run_scan, "delay", lambda scan_id: None)

    payload = {
        "action": "opened",
        "installation": {"id": 99},
        "repository": {
            "clone_url": repo_url,
            "name": "example",
            "owner": {"login": "octo"},
        },
        "pull_request": {
            "number": 12,
            "head": {
                "sha": "abcdef123456",
                "ref": "feature/ci",
            },
            "html_url": "https://github.com/octo/example/pull/12",
        },
    }
    raw = json_module.dumps(payload).encode("utf-8")
    signature = (
        "sha256="
        + hmac.new(
            b"test-secret",
            raw,
            hashlib.sha256,
        ).hexdigest()
    )

    response = client.post(
        "/api/v1/webhooks/github",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    webhook_result = response.json()
    assert webhook_result["accepted"] is True
    assert webhook_result["scan_id"] is not None

    scans = client.get("/api/v1/scans/", headers=headers)
    assert scans.status_code == 200
    assert scans.json()
    assert scans.json()[0]["source"] == "github-app"
    assert scans.json()[0]["project_key"] == "github-example"

    replay = client.post(
        "/api/v1/webhooks/github",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": signature,
        },
    )
    assert replay.status_code == 200
    assert replay.json()["scan_id"] == webhook_result["scan_id"]

    scans_after_replay = client.get("/api/v1/scans/", headers=headers)
    assert scans_after_replay.status_code == 200
    assert len(scans_after_replay.json()) == 1


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_azure_onboard_project_creates_subscriptions(
    tmp_path: Path,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> _FakeResponse:
        assert "api-version=7.1-preview.4" in url
        assert timeout == 20.0
        assert headers["Authorization"].startswith("Bearer ")
        return _FakeResponse({"id": "project-id-123"})

    def fake_post(
        url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: float
    ) -> _FakeResponse:
        assert "api-version=7.1" in url
        assert timeout == 20.0
        assert json["publisherId"] == "tfs"
        assert json["consumerId"] == "webHooks"
        assert json["consumerInputs"]["httpHeaders"] == json_module.dumps(
            {"X-VigilWeave-Webhook-Secret": 'quoted"value'}
        )
        event_type = json["eventType"]
        return _FakeResponse({"id": f"subscription-{event_type}", "status": "enabled"})

    monkeypatch.setattr(azure_marketplace.httpx, "get", fake_get)
    monkeypatch.setattr(azure_marketplace.httpx, "post", fake_post)

    response = client.post(
        "/api/v1/integrations/azure-devops/onboard-project",
        headers=headers,
        json={
            "organization_url": "https://dev.azure.com/example-org",
            "project": "Payments",
            "access_token": "ado-token",
            "auth_scheme": "bearer",
            "webhook_url": "https://vigilweave.example.com/api/v1/webhooks/azure-devops",
            "events": ["git.pullrequest.created", "git.pullrequest.updated"],
            "secret": 'quoted"value',
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["subscriptions_created"] == 2
    assert payload["subscriptions"][0]["id"] == "subscription-git.pullrequest.created"


def test_webhook_payload_too_large_returns_413(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)

    monkeypatch.setattr(settings, "github_webhook_secret", "test-secret")
    monkeypatch.setattr(settings, "webhook_max_request_body_bytes", 10)

    response = client.post(
        "/api/v1/webhooks/github",
        content=b'{"payload": "this is larger than ten bytes"}',
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )

    assert response.status_code == 413


def test_scans_list_enforces_limit_bounds(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)

    response = client.get("/api/v1/scans/?limit=100000")

    assert response.status_code == 422


def test_azure_onboard_rejects_non_azure_hosts(
    tmp_path: Path,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    response = client.post(
        "/api/v1/integrations/azure-devops/onboard-project",
        headers=headers,
        json={
            "organization_url": "https://example.com/not-azure",
            "project": "Payments",
            "access_token": "ado-token",
            "auth_scheme": "bearer",
            "webhook_url": "https://vigilweave.example.com/api/v1/webhooks/azure-devops",
            "events": ["git.pullrequest.created"],
        },
    )

    assert response.status_code == 422
    assert "Azure DevOps" in response.text
