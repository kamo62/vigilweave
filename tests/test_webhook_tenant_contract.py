"""Synthetic installation ownership regressions."""

from sqlmodel import Session, SQLModel, create_engine

from app.models import Project, ProjectRepository, TenantGitHubInstallation
from app.services.github_app import handle_github_event


def test_installation_routes_only_its_tenant(monkeypatch):
    monkeypatch.setattr("app.services.github_app.settings.celery_task_always_eager", False)
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        a = Project(tenant_slug="a", key="a", name="A")
        b = Project(tenant_slug="b", key="b", name="B")
        session.add_all([a, b])
        session.commit()
        url = "https://github.com/org/repo.git"
        session.add_all(
            [
                TenantGitHubInstallation(tenant_slug="a", installation_id=101, account_login="org"),
                TenantGitHubInstallation(tenant_slug="b", installation_id=102, account_login="org"),
                ProjectRepository(project_id=a.id, repo=url, github_installation_id=101),
                ProjectRepository(project_id=b.id, repo=url, github_installation_id=102),
            ]
        )
        session.commit()
        monkeypatch.setattr("app.services.github_app.github_app_configured", lambda: False)
        monkeypatch.setattr("app.tasks.scan_tasks.run_scan.delay", lambda *a: None)
        payload = {
            "action": "opened",
            "installation": {"id": 101},
            "repository": {"clone_url": url, "owner": {"login": "org"}, "name": "repo"},
            "pull_request": {"number": 1, "head": {"sha": "a" * 40, "ref": "main"}},
        }
        result = handle_github_event(
            session, event="pull_request", payload=payload, delivery_id="x"
        )
        assert result["accepted"] is True
        from app.models import Scan

        assert session.get(Scan, result["scan_id"]).tenant_slug == "a"
        payload["installation"]["id"] = 999
        assert not handle_github_event(
            session, event="pull_request", payload=payload, delivery_id="y"
        )["accepted"]
        payload["installation"]["id"] = 101
        payload["pull_request"]["head"]["ref"] = "--help"
        invalid = handle_github_event(
            session, event="pull_request", payload=payload, delivery_id="z"
        )
        assert not invalid["accepted"] and "branch" in invalid["message"].lower()
        payload["pull_request"]["head"]["ref"] = "main"
        payload["pull_request"]["head"]["sha"] = "HEAD~1"
        invalid = handle_github_event(
            session, event="pull_request", payload=payload, delivery_id="z2"
        )
        assert not invalid["accepted"] and "commit" in invalid["message"].lower()


def test_azure_shared_secret_has_no_tenant_authority(api_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "azure_webhook_secret", "synthetic-secret")
    response = api_client.post(
        "/api/v1/webhooks/azure-devops",
        headers={"X-VigilWeave-Webhook-Secret": "synthetic-secret"},
        json={
            "eventType": "git.pullrequest.created",
            "resource": {
                "repository": {"remoteUrl": "https://dev.azure.com/org/project/_git/repo"}
            },
        },
    )
    assert response.status_code == 503
    assert "tenant" in response.json()["detail"].lower()
