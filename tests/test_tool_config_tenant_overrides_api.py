from fastapi.testclient import TestClient


def test_tenant_tool_overrides_are_isolated(
    api_client: TestClient, bootstrap_api_key, cross_tenant_api_key
) -> None:
    acme_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    beta_headers = cross_tenant_api_key(tenant_slug="beta", name="beta-admin")

    acme_patch = api_client.patch(
        "/api/v1/tool-configs/tools/semgrep",
        headers=acme_headers,
        json={
            "languages": ["python"],
            "rules": {"config": ["p/python"], "exclude": ["tests/**"]},
        },
    )
    assert acme_patch.status_code == 200
    assert acme_patch.json()["overridden"] is True
    assert acme_patch.json()["raw"]["rules"]["config"] == ["p/python"]

    acme_custom = api_client.put(
        "/api/v1/tool-configs/tenant/tools/semgrep-strict",
        headers=acme_headers,
        json={
            "enabled": True,
            "category": "security",
            "languages": ["python"],
            "runner": "semgrep",
            "rules": {"config": ["p/python"], "jobs": 2},
        },
    )
    assert acme_custom.status_code == 200
    assert acme_custom.json()["tool"] == "semgrep-strict"
    assert acme_custom.json()["raw"]["runner"] == "semgrep"

    acme_snapshot = api_client.get("/api/v1/tool-configs/", headers=acme_headers)
    assert acme_snapshot.status_code == 200
    acme_tools = {item["tool"]: item for item in acme_snapshot.json()["tools"]}
    assert acme_tools["semgrep"]["languages"] == ["python"]
    assert acme_tools["semgrep"]["raw"]["rules"]["exclude"] == ["tests/**"]
    assert "semgrep-strict" in acme_tools
    assert acme_tools["semgrep-strict"]["overridden"] is True

    beta_snapshot = api_client.get("/api/v1/tool-configs/", headers=beta_headers)
    assert beta_snapshot.status_code == 200
    beta_tools = {item["tool"]: item for item in beta_snapshot.json()["tools"]}
    assert beta_tools["semgrep"]["languages"] == ["all"]
    assert "rules" not in beta_tools["semgrep"]["raw"]
    assert "semgrep-strict" not in beta_tools

    acme_overrides = api_client.get("/api/v1/tool-configs/tenant/overrides", headers=acme_headers)
    assert acme_overrides.status_code == 200
    assert {item["tool"] for item in acme_overrides.json()} == {"semgrep", "semgrep-strict"}

    beta_overrides = api_client.get("/api/v1/tool-configs/tenant/overrides", headers=beta_headers)
    assert beta_overrides.status_code == 200
    assert beta_overrides.json() == []

    delete_custom = api_client.delete(
        "/api/v1/tool-configs/tenant/tools/semgrep-strict",
        headers=acme_headers,
    )
    assert delete_custom.status_code == 204
