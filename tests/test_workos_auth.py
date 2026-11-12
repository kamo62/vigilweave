"""WorkOS tests using synthetic example.com accounts and test-only credentials."""

from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app.api.auth_workos import (
    _request_ip_address,
    _request_user_agent,
    _state_cookie_key,
    _upsert_user,
    _workos_cookie_password,
)
from app.core import database as database_module
from app.core.config import settings
from app.core.licensing import get_license
from app.core.token_encryption import decrypt_token, encrypt_token
from app.core.workos_session import (
    WorkOSCookieError,
    decode_workos_cookie,
    encode_workos_cookie,
)
from app.main import _validate_production_secrets
from app.models import (
    AuthProvider,
    PlatformRole,
    SaaSTenantLicense,
    SaaSTenantTier,
    Tenant,
    User,
    UserRole,
)
from app.services.tenants import upsert_tenant


def _csrf_headers(api_client) -> dict[str, str]:
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    token = response.json()["csrf_token"]
    api_client.cookies.set("vigilweave_csrf", token)
    return {"X-CSRF-Token": token}


def test_upsert_user_uses_org_tenant_and_first_user_admin(api_client) -> None:
    del api_client

    with Session(database_module.engine) as session:
        first_workos_user = SimpleNamespace(
            id="user_first",
            email="owner@example.com",
            first_name="Owner",
            name="Owner Example",
            organization_id="org_acme",
        )
        second_workos_user = SimpleNamespace(
            id="user_second",
            email="member@example.com",
            first_name="Member",
            name="Member Example",
            organization_id="org_acme",
        )

        _upsert_user(session, first_workos_user)
        _upsert_user(session, second_workos_user)

        owner = session.exec(select(User).where(User.workos_user_id == "user_first")).one()
        member = session.exec(select(User).where(User.workos_user_id == "user_second")).one()

    assert owner.tenant_slug == member.tenant_slug
    assert owner.tenant_slug != "default"
    assert owner.role == "admin"
    assert owner.platform_role == "none"
    assert owner.onboarding_completed is False
    assert member.role == "member"
    assert member.onboarding_completed is True


def test_upsert_user_without_org_gets_non_default_tenant(api_client) -> None:
    del api_client

    with Session(database_module.engine) as session:
        workos_user = SimpleNamespace(
            id="user_solo",
            email="solo@example.com",
            first_name="Solo",
            name="Solo Example",
            organization_id=None,
        )

        user = _upsert_user(session, workos_user)

    assert user.tenant_slug.startswith("workos-user-")
    assert user.tenant_slug != "default"
    assert user.role == UserRole.ADMIN


def test_upsert_user_maps_known_workos_org_to_existing_tenant(api_client) -> None:
    del api_client

    with Session(database_module.engine) as session:
        tenant = upsert_tenant(
            session,
            slug="acme-platform",
            display_name="Acme Platform",
            workos_org_id="org_acme",
        )
        session.add(tenant)
        session.add(
            User(
                email="owner@example.com",
                tenant_slug="acme-platform",
                auth_provider=AuthProvider.WORKOS,
                workos_user_id="user_owner",
                role=UserRole.ADMIN,
                onboarding_completed=False,
            )
        )
        session.commit()

        workos_user = SimpleNamespace(
            id="user_joiner",
            email="joiner@example.com",
            first_name="Joiner",
            name="Joiner Example",
            organization_id="org_acme",
        )

        user = _upsert_user(session, workos_user)

    assert user.tenant_slug == "acme-platform"
    assert user.role == UserRole.MEMBER


def test_existing_admin_role_is_preserved_on_subsequent_login(api_client) -> None:
    del api_client

    with Session(database_module.engine) as session:
        owner = SimpleNamespace(
            id="user_owner",
            email="owner@example.com",
            first_name="Owner",
            name="Owner Example",
            organization_id="org_acme",
        )
        teammate = SimpleNamespace(
            id="user_teammate",
            email="teammate@example.com",
            first_name="Teammate",
            name="Teammate Example",
            organization_id="org_acme",
        )

        _upsert_user(session, owner)
        _upsert_user(session, teammate)
        _upsert_user(session, owner)

        refreshed_owner = session.exec(
            select(User).where(User.workos_user_id == "user_owner")
        ).one()

    assert refreshed_owner.role == UserRole.ADMIN
    assert refreshed_owner.onboarding_completed is False


def test_bootstrap_platform_operator_email_is_persisted(api_client, monkeypatch) -> None:
    del api_client
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
    monkeypatch.setattr(settings, "saas_bootstrap_platform_admin_emails", ["owner@example.com"])

    with Session(database_module.engine) as session:
        operator = SimpleNamespace(
            id="user_platform_owner",
            email="owner@example.com",
            first_name="Owner",
            name="Owner Example",
            organization_id="org_vigilweave",
        )

        user = _upsert_user(session, operator)

    assert user.platform_role == "operator"


def test_request_ip_address_prefers_cloudflare_header(api_client) -> None:
    request = SimpleNamespace(
        headers={
            "cf-connecting-ip": "198.51.100.42",
            "x-forwarded-for": "203.0.113.10, 10.0.0.1",
        },
        client=SimpleNamespace(host="10.244.0.12"),
    )

    assert _request_ip_address(request) == "198.51.100.42"


def test_request_ip_address_falls_back_to_forwarded_for(api_client) -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10, 10.0.0.1"},
        client=SimpleNamespace(host="10.244.0.12"),
    )

    assert _request_ip_address(request) == "203.0.113.10"


def test_request_user_agent_reads_header(api_client) -> None:
    request = SimpleNamespace(
        headers={"user-agent": "Mozilla/5.0 Test Browser"},
        client=SimpleNamespace(host="10.244.0.12"),
    )

    assert _request_user_agent(request) == "Mozilla/5.0 Test Browser"


def test_state_cookie_key_is_derived_from_state(api_client) -> None:
    assert _state_cookie_key("abc-123") == "auth_state_abc-123"


def test_workos_cookie_password_prefers_session_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "primary-secret")
    monkeypatch.setattr(settings, "workos_session_secret", "secondary-secret")

    assert _workos_cookie_password() == "primary-secret"


def test_workos_cookie_password_falls_back_to_workos_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_secret", None)
    monkeypatch.setattr(settings, "workos_session_secret", "secondary-secret")

    assert _workos_cookie_password() == "secondary-secret"


def test_workos_cookies_are_encrypted_with_session_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "workos_session_secret", "test-session-secret")

    encoded = encode_workos_cookie("session", "token-value")

    assert decode_workos_cookie("session", encoded) == "token-value"
    with pytest.raises(WorkOSCookieError):
        decode_workos_cookie("refresh", encoded)


def test_capabilities_are_public_in_workos_mode(api_client, monkeypatch) -> None:
    get_license.cache_clear()
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "workos_session_secret", None)
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")

    response = api_client.get("/api/v1/system/capabilities")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authentication"]["auth_mode"] == "workos"
    assert body["authentication"]["saas_enabled"] is True
    assert body["authentication"]["workos_configured"] is True
    assert body["license"]["tier"] == "enterprise"
    get_license.cache_clear()


def test_capabilities_use_authenticated_tenant_license_override(api_client, monkeypatch) -> None:
    get_license.cache_clear()
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")

    with Session(database_module.engine) as session:
        session.add(SaaSTenantLicense(tenant_slug="workos-org-acme", tier=SaaSTenantTier.PRO))
        session.commit()

    user = SimpleNamespace(
        id=1,
        email="tenant-admin@example.com",
        tenant_slug="workos-org-acme",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.NONE,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: user)
    api_client.cookies.set("vigilweave_session", "test-session")

    response = api_client.get("/api/v1/system/capabilities")

    assert response.status_code == 200, response.text
    assert response.json()["license"]["tier"] == "pro"
    get_license.cache_clear()


def test_platform_operator_can_assign_tenant_license(api_client, monkeypatch) -> None:
    get_license.cache_clear()
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "saas_operator_emails", ["owner@example.com"])

    with Session(database_module.engine) as session:
        tenant_user = User(
            email="member@example.com",
            tenant_slug="workos-org-acme",
            auth_provider="workos",
            workos_user_id="user_acme",
            role="member",
        )
        session.add(tenant_user)
        session.commit()

    operator = SimpleNamespace(
        id=1,
        email="owner@example.com",
        tenant_slug="workos-org-owner",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.OPERATOR,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: operator)
    api_client.cookies.set("vigilweave_session", "test-session")

    update = api_client.put(
        "/api/v1/saas-admin/tenant-licenses/workos-org-acme",
        json={"tier": "pro", "note": "Partner plan"},
        headers=_csrf_headers(api_client),
    )

    assert update.status_code == 200, update.text
    payload = update.json()
    assert payload["tenant_slug"] == "workos-org-acme"
    assert payload["tier"] == "pro"
    assert payload["source"] == "override"
    assert payload["assigned_by"] == "owner@example.com"

    listing = api_client.get("/api/v1/saas-admin/tenant-licenses")

    assert listing.status_code == 200, listing.text
    acme = next(item for item in listing.json() if item["tenant_slug"] == "workos-org-acme")
    assert acme["tier"] == "pro"
    assert acme["user_count"] == 1
    get_license.cache_clear()


def test_platform_operator_can_promote_another_operator(api_client, monkeypatch) -> None:
    get_license.cache_clear()
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "saas_operator_emails", [])

    with Session(database_module.engine) as session:
        target_user = User(
            email="ops2@example.com",
            tenant_slug="workos-org-vigilweave",
            auth_provider="workos",
            workos_user_id="user_ops2",
            role="admin",
        )
        session.add(target_user)
        session.commit()
        session.refresh(target_user)
        target_user_id = target_user.id

    operator = SimpleNamespace(
        id=1,
        email="owner@example.com",
        tenant_slug="workos-org-owner",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.OPERATOR,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: operator)
    api_client.cookies.set("vigilweave_session", "test-session")

    response = api_client.patch(
        f"/api/v1/saas-admin/users/{target_user_id}/platform-role",
        json={"platform_role": "operator"},
        headers=_csrf_headers(api_client),
    )

    assert response.status_code == 200, response.text
    assert response.json()["platform_role"] == "operator"


def test_anonymous_bootstrap_is_disabled_in_dual_mode(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "dual")

    response = api_client.get("/api/v1/system/capabilities")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authentication"]["anonymous_bootstrap"] is False


def test_api_key_tenant_header_mismatch_is_rejected(api_client, bootstrap_api_key) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    mismatched_headers = {
        **headers,
        "X-VigilWeave-Tenant": "other",
    }

    response = api_client.get("/api/v1/auth/api-keys", headers=mismatched_headers)

    assert response.status_code == 403, response.text


def test_production_secret_validation_accepts_legacy_workos_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "session_secret", None)
    monkeypatch.setattr(settings, "token_encryption_key", None)
    monkeypatch.setattr(settings, "workos_session_secret", "legacy-session-secret")

    _validate_production_secrets()


def test_token_encryption_uses_legacy_workos_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "session_secret", None)
    monkeypatch.setattr(settings, "token_encryption_key", None)
    monkeypatch.setattr(settings, "workos_session_secret", "legacy-session-secret")

    ciphertext = encrypt_token("scm-token")

    assert decrypt_token(ciphertext) == "scm-token"


def test_api_key_creation_requires_csrf_for_session_requests(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "session_auth_provider", "local")
    monkeypatch.setattr(settings, "api_keys_enabled", True)

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

    create_without_csrf = api_client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "missing-csrf",
            "scopes": ["scan:read"],
        },
    )
    assert create_without_csrf.status_code == 403

    refreshed_csrf = api_client.get("/api/v1/auth/csrf")
    create_with_csrf = api_client.post(
        "/api/v1/auth/api-keys",
        headers={"X-CSRF-Token": refreshed_csrf.json()["csrf_token"]},
        json={
            "name": "with-csrf",
            "scopes": ["scan:read"],
        },
    )
    assert create_with_csrf.status_code == 201


def test_workos_profile_update_requires_csrf(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")

    with Session(database_module.engine) as session:
        user = User(
            email="workos@example.com",
            name="WorkOS User",
            tenant_slug="workos-org-acme",
            auth_provider="workos",
            workos_user_id="user_workos_1",
            role=UserRole.ADMIN,
            onboarding_completed=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    from app.core.workos_session import encode_workos_cookie

    token = encode_workos_cookie("session", "fake-workos-access-token")
    api_client.cookies.set("vigilweave_session", token)

    def fake_get_authenticated_user(session, cookie):  # noqa: ANN001
        del session, cookie
        with Session(database_module.engine) as db:
            return db.exec(select(User).where(User.email == "workos@example.com")).one()

    monkeypatch.setattr("app.api.auth_workos.get_authenticated_user", fake_get_authenticated_user)

    missing_csrf = api_client.patch(
        "/api/v1/auth/me",
        json={"name": "Updated Name"},
    )
    assert missing_csrf.status_code == 403

    csrf = api_client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    with_csrf = api_client.patch(
        "/api/v1/auth/me",
        headers={"X-CSRF-Token": csrf.json()["csrf_token"]},
        json={"name": "Updated Name"},
    )
    assert with_csrf.status_code == 200


def test_admin_can_send_workos_invitation_and_create_org(
    api_client, cross_tenant_api_key, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")

    with Session(database_module.engine) as session:
        tenant = upsert_tenant(session, slug="acme", display_name="Acme")
        session.add(tenant)
        session.commit()

    sent: dict[str, object] = {}

    class FakeOrganizations:
        @staticmethod
        def create_organization(**kwargs):  # noqa: ANN003
            return SimpleNamespace(id="org_created", **kwargs)

    class FakeUserManagement:
        @staticmethod
        def send_invitation(**kwargs):  # noqa: ANN003
            sent.update(kwargs)
            return SimpleNamespace(
                id="inv_123",
                email=kwargs["email"],
                state="pending",
                expires_at="2026-05-01T00:00:00Z",
                accepted_at=None,
                revoked_at=None,
                organization_id=kwargs.get("organization_id"),
                inviter_user_id=kwargs.get("inviter_user_id"),
                created_at="2026-04-01T00:00:00Z",
                updated_at="2026-04-01T00:00:00Z",
            )

    fake_client = SimpleNamespace(
        organizations=FakeOrganizations(),
        user_management=FakeUserManagement(),
    )
    monkeypatch.setattr("app.api.auth_workos._get_workos_client", lambda: fake_client)

    headers = cross_tenant_api_key(tenant_slug="acme", scopes=["admin"])
    response = api_client.post(
        "/api/v1/auth/invitations",
        json={"email": "Teammate@Example.com"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["email"] == "teammate@example.com"
    assert sent == {
        "email": "teammate@example.com",
        "organization_id": "org_created",
        "inviter_user_id": None,
    }

    with Session(database_module.engine) as session:
        acme = session.exec(select(Tenant).where(Tenant.slug == "acme")).one()
        assert acme.workos_org_id == "org_created"


def test_list_and_revoke_workos_invitations_are_tenant_scoped(
    api_client,
    cross_tenant_api_key,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")

    with Session(database_module.engine) as session:
        tenant = upsert_tenant(
            session,
            slug="acme",
            display_name="Acme",
            workos_org_id="org_acme",
        )
        session.add(tenant)
        session.commit()

    invitations = {
        "inv_acme": SimpleNamespace(
            id="inv_acme",
            email="acme@example.com",
            state="pending",
            expires_at="2026-05-01T00:00:00Z",
            accepted_at=None,
            revoked_at=None,
            organization_id="org_acme",
            inviter_user_id=None,
            created_at="2026-04-01T00:00:00Z",
            updated_at="2026-04-01T00:00:00Z",
        ),
        "inv_other": SimpleNamespace(
            id="inv_other",
            email="other@example.com",
            state="pending",
            expires_at="2026-05-01T00:00:00Z",
            accepted_at=None,
            revoked_at=None,
            organization_id="org_other",
            inviter_user_id=None,
            created_at="2026-04-01T00:00:00Z",
            updated_at="2026-04-01T00:00:00Z",
        ),
    }
    revoked: list[str] = []

    class FakeUserManagement:
        @staticmethod
        def list_invitations(**kwargs):  # noqa: ANN003
            assert kwargs["organization_id"] == "org_acme"
            return SimpleNamespace(data=[invitations["inv_acme"]])

        @staticmethod
        def get_invitation(invitation_id: str):
            return invitations[invitation_id]

        @staticmethod
        def revoke_invitation(invitation_id: str):
            revoked.append(invitation_id)
            invitation = invitations[invitation_id]
            invitation.state = "revoked"
            invitation.revoked_at = "2026-04-02T00:00:00Z"
            invitation.updated_at = "2026-04-02T00:00:00Z"
            return invitation

    fake_client = SimpleNamespace(
        user_management=FakeUserManagement(), organizations=SimpleNamespace()
    )
    monkeypatch.setattr("app.api.auth_workos._get_workos_client", lambda: fake_client)

    headers = cross_tenant_api_key(tenant_slug="acme", scopes=["admin"])

    list_response = api_client.get("/api/v1/auth/invitations", headers=headers)
    assert list_response.status_code == 200, list_response.text
    assert [item["id"] for item in list_response.json()] == ["inv_acme"]

    revoke_response = api_client.post("/api/v1/auth/invitations/inv_acme/revoke", headers=headers)
    assert revoke_response.status_code == 200, revoke_response.text
    assert revoke_response.json()["state"] == "revoked"
    assert revoked == ["inv_acme"]

    cross_tenant_response = api_client.post(
        "/api/v1/auth/invitations/inv_other/revoke", headers=headers
    )
    assert cross_tenant_response.status_code == 404


def test_workos_callback_surfaces_provider_error_details(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")

    class FakeWorkOSError(Exception):
        def __init__(self) -> None:
            super().__init__("invalid_grant")
            self.error = "invalid_grant"
            self.error_description = "The code has expired or is invalid."

    class FakeUserManagement:
        @staticmethod
        def authenticate_with_code(**kwargs):  # noqa: ANN003
            del kwargs
            raise FakeWorkOSError()

    monkeypatch.setattr("app.api.auth_workos._get_user_management", lambda: FakeUserManagement())

    state = "state-123"
    api_client.cookies.set(
        _state_cookie_key(state),
        encode_workos_cookie("state", state),
    )

    response = api_client.get(
        "/api/v1/auth/callback",
        params={"code": "code-123", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "https://app.vigilweave.com/auth/callback?error=invalid_grant&error_description=The+code+has+expired+or+is+invalid."
    )


def test_workos_callback_uses_access_refresh_token_flow(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "workos_api_key", "sk_test")
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.com")

    observed: dict[str, object] = {}

    class FakeUserManagement:
        @staticmethod
        def authenticate_with_code(**kwargs):  # noqa: ANN003
            observed.update(kwargs)
            return SimpleNamespace(
                user=SimpleNamespace(
                    id="user_test",
                    email="workos@example.com",
                    first_name="WorkOS",
                    name="WorkOS User",
                    organization_id=None,
                ),
                access_token="access-token",
                refresh_token="refresh-token",
                sealed_session=None,
            )

    monkeypatch.setattr("app.api.auth_workos._get_user_management", lambda: FakeUserManagement())

    state = "state-123"
    api_client.cookies.set(
        _state_cookie_key(state),
        encode_workos_cookie("state", state),
    )

    response = api_client.get(
        "/api/v1/auth/callback",
        params={"code": "code-123", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://app.vigilweave.com/onboarding?next=%2Fprojects"
    assert observed["code"] == "code-123"
    assert "session" not in observed
    set_cookie = response.headers.get("set-cookie", "")
    assert "vigilweave_session=" in set_cookie
    assert "vigilweave_refresh=" in set_cookie
