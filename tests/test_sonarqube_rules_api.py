import base64
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.core.config import settings
from app.main import app
from app.services import sonarqube as sonarqube_service


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "sonarqube-rules.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def _bootstrap_key(client: TestClient, tenant_slug: str = "acme") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "sonarqube-admin",
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


def test_sonarqube_rule_import_and_load(tmp_path: Path, monkeypatch, enterprise_license) -> None:
    del enterprise_license
    monkeypatch.setattr(settings, "rulepacks_path", str(tmp_path / "rulepacks"))
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    response = client.post(
        "/api/v1/integrations/sonarqube/rules/import",
        headers=headers,
        json={
            "language": "py",
            "profile_name": "VigilWeave Python",
            "rules": [
                {
                    "key": "python:S5332",
                    "name": "Credentials should not be hard-coded",
                    "lang": "py",
                    "repo": "python",
                    "severity": "BLOCKER",
                    "type": "VULNERABILITY",
                    "mdDesc": "Hard-coded credentials are unsafe.",
                    "tags": ["security", "cwe"],
                },
                {
                    "key": "python:S3776",
                    "name": "Cognitive Complexity should be low",
                    "lang": "py",
                    "repo": "python",
                    "severity": "MAJOR",
                    "type": "CODE_SMELL",
                    "mdDesc": "Refactor to reduce complexity.",
                    "tags": ["brain-overload"],
                },
            ],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["language"] == "python"
    assert payload["rules_imported"] == 2
    by_key = {rule["source_rule_key"]: rule for rule in payload["rules"]}
    assert by_key["python:S5332"]["severity"] == "Critical"
    assert by_key["python:S5332"]["category"] == "security"
    assert by_key["python:S3776"]["severity"] == "Medium"
    assert by_key["python:S3776"]["category"] == "maintainability"
    assert Path(payload["persisted_path"]).exists()

    persisted = client.get(
        "/api/v1/integrations/sonarqube/rules/python",
        headers=headers,
    )
    assert persisted.status_code == 200
    persisted_payload = persisted.json()
    assert persisted_payload["language"] == "python"
    assert len(persisted_payload["rules"]) == 2


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_sonarqube_rule_sync_fetches_pages(tmp_path: Path, monkeypatch, enterprise_license) -> None:
    del enterprise_license
    monkeypatch.setattr(settings, "rulepacks_path", str(tmp_path / "rulepacks"))
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    captured_headers: list[dict[str, str]] = []
    captured_params: list[dict[str, str | int]] = []

    def fake_get(
        url: str, *, headers: dict[str, str], params: dict[str, str | int], timeout: float
    ) -> _FakeResponse:
        assert url == "https://sonar.example.com/api/rules/search"
        assert timeout == 30.0
        captured_headers.append(headers)
        captured_params.append(params)
        page = int(params["p"])
        if page == 1:
            return _FakeResponse(
                {
                    "total": 2,
                    "rules": [
                        {
                            "key": "java:S2077",
                            "name": "SQL queries should be parameterized",
                            "lang": "java",
                            "repo": "java",
                            "severity": "CRITICAL",
                            "type": "VULNERABILITY",
                            "mdDesc": "Use prepared statements.",
                        }
                    ],
                }
            )
        return _FakeResponse(
            {
                "total": 2,
                "rules": [
                    {
                        "key": "java:S112",
                        "name": "Generic exceptions should not be thrown",
                        "lang": "java",
                        "repo": "java",
                        "severity": "MINOR",
                        "type": "CODE_SMELL",
                        "mdDesc": "Throw specific exceptions.",
                    }
                ],
            }
        )

    monkeypatch.setattr(sonarqube_service.httpx, "get", fake_get)

    response = client.post(
        "/api/v1/integrations/sonarqube/rules/sync",
        headers=headers,
        json={
            "base_url": "https://sonar.example.com",
            "token": "sonar-token",
            "auth_scheme": "basic-token",
            "language": "java",
            "quality_profile": "AU-TYI6wFhI7v1fV9q7I",
            "persist": True,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["language"] == "java"
    assert payload["rules_imported"] == 2
    assert payload["source_url"] == "https://sonar.example.com"
    assert len(captured_params) == 2
    assert captured_params[0]["qprofile"] == "AU-TYI6wFhI7v1fV9q7I"
    assert captured_params[0]["activation"] == "true"
    assert captured_params[0]["languages"] == "java"

    expected_auth = base64.b64encode(b"sonar-token:").decode("ascii")
    assert captured_headers[0]["Authorization"] == f"Basic {expected_auth}"
