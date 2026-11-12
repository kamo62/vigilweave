from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services import config_loader, sonarqube

pytestmark = pytest.mark.e2e


def test_e2e_system_metrics_telemetry_and_tool_config(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = Path(__file__).resolve().parents[1] / "tools_config.yaml"
    temp_config_path = tmp_path / "tools_config.yaml"
    temp_config_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", temp_config_path)
    config_loader.clear_tool_config_cache()

    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    read_headers = bootstrap_api_key(
        tenant_slug="acme",
        name="acme-read",
        scopes=["scan:read"],
        actor_headers=admin_headers,
    )
    repo_path = git_repo_factory(name="observability-repo")

    created = api_client.post(
        "/api/v1/scans/",
        headers=admin_headers,
        json={"repo": f"file://{repo_path}", "scan_type": "comprehensive"},
    )
    assert created.status_code == 201

    capabilities = api_client.get("/api/v1/system/capabilities", headers=read_headers)
    assert capabilities.status_code == 200
    assert capabilities.json()["integrations"]["sonarqube"] is True
    assert "python" in capabilities.json()["languages"]
    assert capabilities.json()["tooling"]["android-lint"] is False
    assert capabilities.json()["tooling"]["dotnet-analyzers"] is False

    metrics = api_client.get("/api/v1/system/metrics", headers=admin_headers)
    assert metrics.status_code == 200
    assert "scan_runs_total" in metrics.json()["counters"]

    telemetry = api_client.get("/api/v1/system/tool-telemetry", headers=read_headers)
    assert telemetry.status_code == 200
    assert telemetry.json()
    assert any(row["tool"] == "semgrep" for row in telemetry.json())

    snapshot = api_client.get("/api/v1/tool-configs/", headers=read_headers)
    assert snapshot.status_code == 200
    assert any(tool["tool"] == "semgrep" for tool in snapshot.json()["tools"])

    patched = api_client.patch(
        "/api/v1/tool-configs/tools/semgrep",
        headers=admin_headers,
        json={"enabled": False, "languages": ["python", "go"]},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["languages"] == ["go", "python"]

    invalid_patch = api_client.patch(
        "/api/v1/tool-configs/tools/semgrep",
        headers=admin_headers,
        json={},
    )
    assert invalid_patch.status_code == 422


def test_e2e_sonarqube_import_sync_list_and_empty(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    imported = api_client.post(
        "/api/v1/integrations/sonarqube/rules/import",
        headers=admin_headers,
        json={
            "language": "py",
            "rules": [
                {
                    "key": "python:S100",
                    "name": "Functions should have descriptive names",
                    "lang": "py",
                    "repo": "python",
                    "severity": "MAJOR",
                    "type": "CODE_SMELL",
                    "tags": ["convention"],
                    "sysTags": ["brain-overload"],
                }
            ],
            "persist": True,
        },
    )
    assert imported.status_code == 201
    assert imported.json()["rules_imported"] == 1
    assert imported.json()["language"] == "python"

    listed = api_client.get("/api/v1/integrations/sonarqube/rules/python", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["rules"]
    assert listed.json()["rules"][0]["severity"] == "Medium"

    empty = api_client.get("/api/v1/integrations/sonarqube/rules/rust", headers=admin_headers)
    assert empty.status_code == 200
    assert empty.json()["rules"] == []

    class _FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    calls: list[dict[str, Any]] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        assert url.endswith("/api/rules/search")
        assert headers["Authorization"].startswith("Basic ")
        assert timeout == 30.0
        calls.append({"params": params})
        if params["p"] == 1:
            return _FakeResponse(
                {
                    "total": 2,
                    "rules": [
                        {
                            "key": "go:S200",
                            "name": "Go rule one",
                            "repo": "go",
                            "severity": "CRITICAL",
                            "type": "BUG",
                            "tags": ["bug"],
                            "sysTags": [],
                        }
                    ],
                }
            )
        return _FakeResponse(
            {
                "total": 2,
                "rules": [
                    {
                        "key": "go:S201",
                        "name": "Go rule two",
                        "repo": "go",
                        "severity": "MINOR",
                        "type": "CODE_SMELL",
                        "tags": ["maintainability"],
                        "sysTags": [],
                    }
                ],
            }
        )

    monkeypatch.setattr(sonarqube.httpx, "get", fake_get)

    synced = api_client.post(
        "/api/v1/integrations/sonarqube/rules/sync",
        headers=admin_headers,
        json={
            "base_url": "https://sonarqube.example.com",
            "token": "sonar-token",
            "language": "go",
            "auth_scheme": "basic-token",
            "persist": True,
            "page_size": 1,
        },
    )
    assert synced.status_code == 201
    assert synced.json()["rules_imported"] == 2
    assert len(calls) >= 2


def test_e2e_sonarqube_sync_rejects_localhost(
    api_client: TestClient,
    bootstrap_api_key,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    response = api_client.post(
        "/api/v1/integrations/sonarqube/rules/sync",
        headers=admin_headers,
        json={
            "base_url": "https://localhost",
            "token": "token",
            "language": "python",
        },
    )

    assert response.status_code == 422
