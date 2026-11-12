"""API tests using synthetic accounts, passwords, secrets, and locally issued licence keys."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

MODULE_PATH = Path(__file__).resolve().parents[1] / "main.py"


@pytest.fixture()
def license_server(tmp_path, monkeypatch):
    db_path = tmp_path / "license-server.db"
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("CONFIG_ENCRYPTION_KEY", "test-config-secret")
    monkeypatch.setenv("OFFLINE_SIGNING_SECRET", "test-offline-secret")
    monkeypatch.setenv("FULFILLMENT_SHARED_SECRET", "test-fulfillment-secret")

    module_name = f"license_server_main_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    with TestClient(module.app) as client:
        yield module, client

    sys.modules.pop(module_name, None)


def bootstrap_admin(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "admin@example.com",
            "password": "example-password-not-a-real-secret",
            "name": "Primary Admin",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_bootstrap_login_logout_and_audit_log(license_server):
    _, client = license_server

    bootstrap_required = client.get("/api/auth/bootstrap-required")
    assert bootstrap_required.status_code == 200
    assert bootstrap_required.json() == {"bootstrap_required": True}

    admin = bootstrap_admin(client)
    assert admin["email"] == "admin@example.com"
    assert admin["role"] == "admin"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "example-password-not-a-real-secret"},
    )
    assert login.status_code == 200

    audit = client.get("/api/admin/audit-logs")
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["items"]]
    assert "operator.bootstrap" in actions
    assert "operator.logout" in actions


def test_license_key_lifecycle_and_public_verification(license_server):
    _, client = license_server
    bootstrap_admin(client)

    generate = client.post(
        "/api/admin/keys/generate",
        json={
            "license_type": "pro",
            "organization": "Acme Corp",
            "expires_days": 30,
            "max_seats": 25,
            "notes": "Initial commercial key",
            "customer_metadata": {"plan": "pilot"},
        },
    )
    assert generate.status_code == 201
    generated_payload = generate.json()
    license_key = generated_payload["license_key"]
    record_id = generated_payload["record"]["id"]

    listed = client.get("/api/admin/keys?status=active")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == record_id

    verified = client.post(
        "/v1/verify",
        json={"license_key": license_key, "instance_id": "ci-runner-1"},
    )
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["organization"] == "Acme Corp"

    detail = client.get(f"/api/admin/keys/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["verification_count"] == 1

    revoked = client.post(
        f"/api/admin/keys/{record_id}/revoke",
        json={"reason": "billing hold"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    revoked_verify = client.post("/v1/verify", json={"license_key": license_key})
    assert revoked_verify.status_code == 200
    assert revoked_verify.json()["valid"] is False
    assert "revoked" in revoked_verify.json()["error_message"]

    reactivated = client.post(f"/api/admin/keys/{record_id}/reactivate")
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    replacement = client.post(f"/api/admin/keys/{record_id}/reissue", json={})
    assert replacement.status_code == 200
    replacement_key = replacement.json()["license_key"]
    replacement_id = replacement.json()["record"]["id"]

    old_key = client.get(f"/api/admin/keys/{record_id}")
    assert old_key.status_code == 200
    assert old_key.json()["status"] == "replaced"
    assert old_key.json()["replaced_by_license_id"] == replacement_id

    replaced_verify = client.post("/v1/verify", json={"license_key": license_key})
    assert replaced_verify.status_code == 200
    assert replaced_verify.json()["valid"] is False
    assert "replaced" in replaced_verify.json()["error_message"]

    replacement_verify = client.post("/v1/verify", json={"license_key": replacement_key})
    assert replacement_verify.status_code == 200
    assert replacement_verify.json()["valid"] is True


def test_license_key_parsing_supports_hyphenated_org_slugs(license_server):
    _, client = license_server
    bootstrap_admin(client)

    generate = client.post(
        "/api/admin/keys/generate",
        json={
            "license_type": "pro",
            "organization": "Acme Platform Team",
        },
    )
    assert generate.status_code == 201
    license_key = generate.json()["license_key"]

    verified = client.post(
        "/v1/verify",
        json={"license_key": license_key, "instance_id": "ci-runner-2"},
    )
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["organization"] == "Acme Platform Team"


def test_directory_configuration_encrypts_bind_password(license_server):
    module, client = license_server
    bootstrap_admin(client)

    update = client.put(
        "/api/admin/directory-config",
        json={
            "enabled": True,
            "server_uri": "ldaps://directory.example.com",
            "bind_dn": "cn=svc,dc=example,dc=com",
            "bind_password": "bind-password",
            "user_base_dn": "ou=Users,dc=example,dc=com",
            "user_filter": "(mail={email})",
            "group_base_dn": "ou=Groups,dc=example,dc=com",
            "admin_group_dn": "cn=admins,ou=Groups,dc=example,dc=com",
            "viewer_group_dn": "cn=viewers,ou=Groups,dc=example,dc=com",
            "use_ssl": True,
            "start_tls": False,
        },
    )
    assert update.status_code == 200
    assert update.json()["bind_password_configured"] is True

    fetch = client.get("/api/admin/directory-config")
    assert fetch.status_code == 200
    assert fetch.json()["bind_password_configured"] is True
    assert "bind_password" not in fetch.json()

    with module.SessionLocal() as session:
        record = session.query(module.DirectoryConfig).one()
        assert record.encrypted_bind_password is not None
        assert record.encrypted_bind_password != "bind-password"
        assert module.decrypt_config_value(record.encrypted_bind_password) == "bind-password"


def test_cannot_disable_last_active_admin(license_server):
    _, client = license_server
    admin = bootstrap_admin(client)

    disable = client.patch(
        f"/api/admin/operators/{admin['id']}",
        json={"is_active": False},
    )
    assert disable.status_code == 400
    assert "At least one active admin must remain" in disable.json()["detail"]


def test_machine_fulfillment_issue_revoke_and_reactivate(license_server):
    _, client = license_server

    issued = client.post(
        "/v1/fulfillment/issue",
        headers={"Authorization": "Bearer test-fulfillment-secret"},
        json={
            "license_type": "pro",
            "organization": "Acme Self Hosted",
            "customer_metadata": {"tenant_slug": "acme-self-hosted"},
        },
    )
    assert issued.status_code == 200, issued.text
    payload = issued.json()
    license_key = payload["license_key"]
    record_id = payload["record"]["id"]
    assert payload["record"]["status"] == "active"

    verified = client.post("/v1/verify", json={"license_key": license_key})
    assert verified.status_code == 200
    assert verified.json()["valid"] is True

    revoked = client.post(
        f"/v1/fulfillment/licenses/{record_id}/revoke",
        headers={"Authorization": "Bearer test-fulfillment-secret"},
        json={"reason": "subscription canceled"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"

    revoked_verify = client.post("/v1/verify", json={"license_key": license_key})
    assert revoked_verify.status_code == 200
    assert revoked_verify.json()["valid"] is False

    reactivated = client.post(
        f"/v1/fulfillment/licenses/{record_id}/reactivate",
        headers={"Authorization": "Bearer test-fulfillment-secret"},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["status"] == "active"

    reactivated_verify = client.post("/v1/verify", json={"license_key": license_key})
    assert reactivated_verify.status_code == 200
    assert reactivated_verify.json()["valid"] is True
