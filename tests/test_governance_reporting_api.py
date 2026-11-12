from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.core import database as database_module
from app.core.token_encryption import encrypt_token
from app.models import TenantGitHubInstallation
from app.models.project import Project, ProjectRepository
from app.models.scm_connection import SCMConnection, SCMProvider


def _create_scan(
    api_client: TestClient,
    headers: dict[str, str],
    repo_url: str,
) -> dict:
    response = api_client.post(
        "/api/v1/scans/",
        headers=headers,
        json={
            "repo": repo_url,
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_community_policy_presets_are_seeded_and_selectable(
    api_client: TestClient,
    bootstrap_api_key,
    community_license,
) -> None:
    del community_license
    headers = bootstrap_api_key(tenant_slug="acme", name="community-admin")

    policies = api_client.get("/api/v1/policies/", headers=headers)
    assert policies.status_code == 200
    payload = policies.json()
    assert len(payload) == 3
    assert {item["preset_key"] for item in payload} == {"lenient", "balanced", "strict"}
    assert any(item["is_default"] and item["preset_key"] == "balanced" for item in payload)

    strict = next(item for item in payload if item["preset_key"] == "strict")
    activate = api_client.post(f"/api/v1/policies/{strict['id']}/activate", headers=headers)
    assert activate.status_code == 200

    refreshed = api_client.get("/api/v1/policies/", headers=headers)
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()
    assert any(item["is_default"] and item["preset_key"] == "strict" for item in refreshed_payload)
    assert (
        api_client.post(
            "/api/v1/policies/",
            headers=headers,
            json={
                "name": "custom-denied",
                "is_default": False,
                "max_critical_findings": 0,
                "max_high_findings": 0,
                "min_quality_score": 95,
            },
        ).status_code
        == 403
    )


def test_tier_gates_for_governance_reporting_and_portfolios(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    set_license_key,
    monkeypatch,
) -> None:
    repo_path = git_repo_factory(name="tier-gates")
    repo_url = f"file://{repo_path}"

    set_license_key(None)
    community_headers = bootstrap_api_key(tenant_slug="acme", name="community-admin")
    community_scan = _create_scan(api_client, community_headers, repo_url)
    community_findings = api_client.get(
        f"/api/v1/scans/{community_scan['id']}/findings",
        headers=community_headers,
    ).json()
    assert (
        api_client.post(
            f"/api/v1/scans/{community_scan['id']}/findings/bulk-triage",
            headers=community_headers,
            json={
                "finding_ids": [item["id"] for item in community_findings],
                "review_status": "acknowledged",
            },
        ).status_code
        == 403
    )
    assert (
        api_client.get(
            f"/api/v1/scans/{community_scan['id']}/report/pdf",
            headers=community_headers,
        ).status_code
        == 403
    )
    assert (
        api_client.get(
            f"/api/v1/scans/{community_scan['id']}/findings/export",
            headers=community_headers,
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/policies/audit", headers=community_headers).status_code == 403
    assert (
        api_client.post(
            "/api/v1/policies/waivers",
            headers=community_headers,
            json={"reason": "deny"},
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/portfolios/", headers=community_headers).status_code == 403

    set_license_key("vw-pro-tests-acme")
    pro_headers = bootstrap_api_key(
        tenant_slug="acme",
        name="pro-admin",
        actor_headers=community_headers,
    )
    pro_scan = _create_scan(api_client, pro_headers, repo_url)
    pro_findings = api_client.get(
        f"/api/v1/scans/{pro_scan['id']}/findings",
        headers=pro_headers,
    ).json()
    bulk = api_client.post(
        f"/api/v1/scans/{pro_scan['id']}/findings/bulk-triage",
        headers=pro_headers,
        json={
            "finding_ids": [item["id"] for item in pro_findings],
            "review_status": "acknowledged",
        },
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated"] == len(pro_findings)
    assert (
        api_client.post(
            "/api/v1/policies/",
            headers=pro_headers,
            json={
                "name": "pro-custom",
                "is_default": False,
                "max_critical_findings": 0,
                "max_high_findings": 1,
                "min_quality_score": 75,
            },
        ).status_code
        == 201
    )
    assert api_client.get("/api/v1/policies/audit", headers=pro_headers).status_code == 200
    monkeypatch.setattr("app.api.scans.generate_scan_report_pdf", lambda **_: b"%PDF-1.7 test")
    pdf = api_client.get(f"/api/v1/scans/{pro_scan['id']}/report/pdf", headers=pro_headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF-1.7")
    assert (
        api_client.post(
            "/api/v1/policies/waivers",
            headers=pro_headers,
            json={"reason": "still denied"},
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/portfolios/", headers=pro_headers).status_code == 403

    set_license_key("vw-ent-tests-acme")
    ent_headers = bootstrap_api_key(
        tenant_slug="acme",
        name="ent-admin",
        actor_headers=pro_headers,
    )
    assert (
        api_client.post(
            "/api/v1/policies/waivers",
            headers=ent_headers,
            json={"reason": "enterprise waiver"},
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            "/api/v1/portfolios/",
            headers=ent_headers,
            json={"key": "exec", "name": "Executive", "selection_mode": "manual"},
        ).status_code
        == 201
    )


def test_reporting_export_respects_filters_and_review_status(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    pro_license,
    monkeypatch,
) -> None:
    del pro_license
    headers = bootstrap_api_key(tenant_slug="acme", name="report-admin")
    repo_path = git_repo_factory(name="reporting")
    scan = _create_scan(api_client, headers, f"file://{repo_path}")

    findings = api_client.get(f"/api/v1/scans/{scan['id']}/findings", headers=headers)
    assert findings.status_code == 200
    finding_payload = findings.json()
    security_finding = next(item for item in finding_payload if item["category"] == "security")

    triaged = api_client.patch(
        f"/api/v1/scans/{scan['id']}/findings/{security_finding['id']}/triage",
        headers=headers,
        json={"review_status": "fixed"},
    )
    assert triaged.status_code == 200

    csv_export = api_client.get(
        f"/api/v1/scans/{scan['id']}/findings/export",
        headers=headers,
        params={"category": "security", "review_status": "fixed"},
    )
    assert csv_export.status_code == 200
    lines = csv_export.text.strip().splitlines()
    assert len(lines) == 2
    assert "security" in lines[1]
    assert "fixed" in lines[1]

    monkeypatch.setattr("app.api.scans.generate_scan_report_pdf", lambda **_: b"%PDF-filtered")
    pdf = api_client.get(
        f"/api/v1/scans/{scan['id']}/report/pdf",
        headers=headers,
        params={"category": "security"},
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-filtered")


def test_integrations_setup_endpoint_reports_webhook_status(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")
    monkeypatch.setattr("app.api.integrations.settings.github_app_id", "12345")
    monkeypatch.setattr("app.api.integrations.settings.github_app_slug", "vigilweave-cloud")
    monkeypatch.setattr("app.api.integrations.settings.github_app_private_key", "test-private-key")
    monkeypatch.setattr("app.api.integrations.settings.github_webhook_secret", "github-secret")
    monkeypatch.setattr("app.api.integrations.settings.github_check_name", "VigilWeave PR Gate")
    monkeypatch.setattr("app.api.integrations.settings.azure_webhook_secret", "azure-secret")
    monkeypatch.setattr(
        "app.api.integrations.settings.vigilweave_api_base_url",
        "https://public-api.vigilweave.example",
    )

    response = api_client.get(
        "/api/v1/integrations/setup",
        headers={**headers, "Host": "attacker.example"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["github"]["configured"] is True
    assert payload["github"]["app_slug"] == "vigilweave-cloud"
    assert (
        payload["github"]["install_url"]
        == "https://github.com/apps/vigilweave-cloud/installations/new"
    )
    assert (
        payload["github"]["setup_url"]
        == "https://public-api.vigilweave.example/api/v1/integrations/github-app/callback"
    )
    assert (
        payload["github"]["webhook_url"]
        == "https://public-api.vigilweave.example/api/v1/webhooks/github"
    )
    assert payload["github"]["tenant_slug"] == "acme"
    assert payload["github"]["check_name"] == "VigilWeave PR Gate"
    assert (
        payload["azure_devops"]["webhook_url"]
        == "https://public-api.vigilweave.example/api/v1/webhooks/azure-devops"
    )
    assert payload["azure_devops"]["tenant_slug"] == "acme"


def test_github_app_install_callback_binds_installation_to_tenant(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")
    monkeypatch.setattr("app.api.integrations.settings.github_app_id", "12345")
    monkeypatch.setattr("app.api.integrations.settings.github_app_slug", "vigilweave-cloud")
    monkeypatch.setattr("app.api.integrations.settings.github_app_private_key", "test-private-key")
    monkeypatch.setattr(
        "app.api.integrations.get_installation",
        lambda installation_id: {
            "id": installation_id,
            "account": {
                "login": "acme-org",
                "type": "Organization",
                "avatar_url": "https://avatars.example/acme.png",
            },
        },
    )

    install_link = api_client.get("/api/v1/integrations/github-app/install-url", headers=headers)
    assert install_link.status_code == 200, install_link.text
    install_url = install_link.json()["install_url"]
    assert "state=" in install_url
    state = install_url.split("state=", 1)[1]

    callback = api_client.get(
        f"/api/v1/integrations/github-app/callback?installation_id=4242&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code in {302, 307}
    assert "githubAppConnected=1" in callback.headers["location"]

    installations = api_client.get("/api/v1/integrations/github-app/installations", headers=headers)
    assert installations.status_code == 200, installations.text
    payload = installations.json()
    assert len(payload) == 1
    assert payload[0]["installation_id"] == 4242
    assert payload[0]["account_login"] == "acme-org"
    assert payload[0]["linked_repo_count"] == 0


def test_github_app_install_callback_redirects_back_to_projects_when_requested(
    api_client: TestClient,
    bootstrap_api_key,
    monkeypatch,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")
    monkeypatch.setattr("app.api.integrations.settings.github_app_id", "12345")
    monkeypatch.setattr("app.api.integrations.settings.github_app_slug", "vigilweave-cloud")
    monkeypatch.setattr("app.api.integrations.settings.github_app_private_key", "test-private-key")
    monkeypatch.setattr(
        "app.api.integrations.get_installation",
        lambda installation_id: {
            "id": installation_id,
            "account": {
                "login": "acme-org",
                "type": "Organization",
                "avatar_url": "https://avatars.example/acme.png",
            },
        },
    )

    install_link = api_client.get(
        "/api/v1/integrations/github-app/install-url",
        headers=headers,
        params={"return_to": "/projects/demo?foo=bar"},
    )
    assert install_link.status_code == 200, install_link.text
    install_url = install_link.json()["install_url"]
    state = install_url.split("state=", 1)[1]

    callback = api_client.get(
        f"/api/v1/integrations/github-app/callback?installation_id=4242&state={state}",
        follow_redirects=False,
    )

    assert callback.status_code in {302, 307}
    assert callback.headers["location"].startswith(
        "http://localhost:5173/projects/demo?foo=bar&githubAppConnected=1"
    )
    assert "githubAppMessage=GitHub+App+connected+for+acme-org." in callback.headers["location"]


def test_github_app_installation_can_be_unlinked_when_unused(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")

    with DBSession(database_module.engine) as session:
        session.add(
            TenantGitHubInstallation(
                tenant_slug="acme",
                installation_id=4242,
                account_login="acme-org",
                account_type="Organization",
            )
        )
        session.commit()

    response = api_client.delete(
        "/api/v1/integrations/github-app/installations/4242", headers=headers
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["installation_id"] == 4242
    assert payload["linked_repo_count"] == 0

    installations = api_client.get("/api/v1/integrations/github-app/installations", headers=headers)
    assert installations.status_code == 200, installations.text
    assert installations.json() == []


def test_github_app_installation_unlink_is_blocked_when_project_repos_still_depend_on_it(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        installation = TenantGitHubInstallation(
            tenant_slug="acme",
            installation_id=4242,
            account_login="acme-org",
            account_type="Organization",
        )
        session.add(project)
        session.add(installation)
        session.commit()
        session.refresh(project)
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo="https://github.com/acme/private-repo.git",
                github_installation_id=installation.installation_id,
            )
        )
        session.commit()

    response = api_client.delete(
        "/api/v1/integrations/github-app/installations/4242", headers=headers
    )

    assert response.status_code == 409, response.text
    assert "still linked to 1 project repository" in response.text


def test_github_app_installation_lists_linked_project_repos(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        installation = TenantGitHubInstallation(
            tenant_slug="acme",
            installation_id=4242,
            account_login="acme-org",
            account_type="Organization",
        )
        session.add(project)
        session.add(installation)
        session.commit()
        session.refresh(project)
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo="https://github.com/acme/private-repo.git",
                github_installation_id=installation.installation_id,
            )
        )
        session.commit()

    response = api_client.get(
        "/api/v1/integrations/github-app/installations/4242/linked-repos",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == [
        {
            "project_key": "acme-project",
            "project_name": "Acme Project",
            "repo": "https://github.com/acme/private-repo.git",
        }
    ]


def test_github_app_installation_reassigns_linked_repos_to_scm_connection(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        installation = TenantGitHubInstallation(
            tenant_slug="acme",
            installation_id=4242,
            account_login="acme-org",
            account_type="Organization",
        )
        connection = SCMConnection(
            tenant_slug="acme",
            name="acme-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("secret-token"),
            created_by="setup-admin",
        )
        session.add(project)
        session.add(installation)
        session.add(connection)
        session.commit()
        session.refresh(project)
        session.refresh(connection)
        connection_id = connection.id
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo="https://github.com/acme/private-repo.git",
                github_installation_id=installation.installation_id,
            )
        )
        session.commit()

    response = api_client.post(
        "/api/v1/integrations/github-app/installations/4242/reassign",
        headers=headers,
        json={"target_scm_connection_id": connection_id},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"reassigned_count": 1}

    with DBSession(database_module.engine) as session:
        repo_link = session.exec(select(ProjectRepository)).one()
        assert repo_link.github_installation_id is None
        assert repo_link.scm_connection_id == connection_id


def test_github_app_installation_reassign_rejects_non_github_scm_connection(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="setup-admin")

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        installation = TenantGitHubInstallation(
            tenant_slug="acme",
            installation_id=4242,
            account_login="acme-org",
            account_type="Organization",
        )
        connection = SCMConnection(
            tenant_slug="acme",
            name="acme-gitlab",
            provider=SCMProvider.GITLAB,
            base_url="https://gitlab.com",
            encrypted_token=encrypt_token("secret-token"),
            created_by="setup-admin",
        )
        session.add(project)
        session.add(installation)
        session.add(connection)
        session.commit()
        session.refresh(project)
        session.refresh(connection)
        connection_id = connection.id
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo="https://github.com/acme/private-repo.git",
                github_installation_id=installation.installation_id,
            )
        )
        session.commit()

    response = api_client.post(
        "/api/v1/integrations/github-app/installations/4242/reassign",
        headers=headers,
        json={"target_scm_connection_id": connection_id},
    )

    assert response.status_code == 400, response.text
    assert (
        response.json()["detail"]
        == "Linked GitHub repositories can only be reassigned to a GitHub SCM connection"
    )


def test_portfolio_cycle_updates_are_rejected(
    api_client: TestClient,
    bootstrap_api_key,
    enterprise_license,
) -> None:
    del enterprise_license
    headers = bootstrap_api_key(tenant_slug="acme", name="portfolio-admin")

    parent = api_client.post(
        "/api/v1/portfolios/",
        headers=headers,
        json={"key": "parent", "name": "Parent", "selection_mode": "manual"},
    )
    assert parent.status_code == 201
    child = api_client.post(
        "/api/v1/portfolios/",
        headers=headers,
        json={
            "key": "child",
            "name": "Child",
            "selection_mode": "manual",
            "parent_id": parent.json()["id"],
        },
    )
    assert child.status_code == 201

    response = api_client.patch(
        "/api/v1/portfolios/parent",
        headers=headers,
        json={"parent_id": child.json()["id"]},
    )
    assert response.status_code == 400
    assert "circular" in response.text.lower()


def test_project_and_portfolio_rollups_stay_tenant_isolated(
    api_client: TestClient,
    bootstrap_api_key,
    cross_tenant_api_key,
    git_repo_factory,
    enterprise_license,
) -> None:
    del enterprise_license
    repo_path = git_repo_factory(name="shared-rollup")
    repo_url = f"file://{repo_path}"

    acme_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    beta_headers = cross_tenant_api_key(tenant_slug="beta", name="beta-admin")

    _create_scan(api_client, acme_headers, repo_url)

    for headers, tenant_key in [(acme_headers, "acme"), (beta_headers, "beta")]:
        project = api_client.post(
            "/api/v1/projects/",
            headers=headers,
            json={
                "key": f"{tenant_key}-project",
                "name": f"{tenant_key.title()} Project",
                "repos": [repo_url],
            },
        )
        assert project.status_code == 201
        portfolio = api_client.post(
            "/api/v1/portfolios/",
            headers=headers,
            json={
                "key": f"{tenant_key}-portfolio",
                "name": f"{tenant_key.title()} Portfolio",
                "selection_mode": "manual",
            },
        )
        assert portfolio.status_code == 201
        linked = api_client.post(
            f"/api/v1/portfolios/{tenant_key}-portfolio/projects",
            headers=headers,
            json={"project_keys": [f"{tenant_key}-project"]},
        )
        assert linked.status_code == 200

    acme_metrics = api_client.get("/api/v1/projects/acme-project", headers=acme_headers)
    beta_metrics = api_client.get("/api/v1/projects/beta-project", headers=beta_headers)
    assert acme_metrics.status_code == 200
    assert beta_metrics.status_code == 200
    assert acme_metrics.json()["total_findings"] >= 1
    assert beta_metrics.json()["total_findings"] == 0

    acme_portfolio = api_client.get("/api/v1/portfolios/acme-portfolio", headers=acme_headers)
    beta_portfolio = api_client.get("/api/v1/portfolios/beta-portfolio", headers=beta_headers)
    assert acme_portfolio.status_code == 200
    assert beta_portfolio.status_code == 200
    assert acme_portfolio.json()["total_findings"] >= 1
    assert beta_portfolio.json()["total_findings"] == 0
