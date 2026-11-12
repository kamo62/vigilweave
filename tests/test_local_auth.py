from sqlmodel import Session

from app.api import auth as auth_module
from app.core import database as database_module
from app.core.config import settings
from app.core.local_auth import hash_password
from app.core.rate_limiter import RateLimitConfig, RateLimiter
from app.models import AuthProvider, User, UserRole


def _enable_local_auth(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "session_auth_provider", "local")
    monkeypatch.setattr(settings, "api_keys_enabled", True)
    monkeypatch.setattr(settings, "saas_enabled", False)


def _csrf_headers(api_client) -> dict[str, str]:
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    token = response.json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_local_bootstrap_registration_is_required_before_first_login(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    capabilities = api_client.get("/api/v1/system/capabilities")

    assert capabilities.status_code == 200, capabilities.text
    body = capabilities.json()
    assert body["authentication"]["session_auth_provider"] == "local"
    assert body["authentication"]["bootstrap_registration_required"] is True
    assert body["authentication"]["anonymous_bootstrap"] is False


def test_local_setup_creates_admin_session_and_allows_api_key_management(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    response = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
        headers=_csrf_headers(api_client),
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["email"] == "owner@example.com"
    assert payload["role"] == "admin"
    assert payload["auth_provider"] == "local"

    me_response = api_client.get("/api/v1/auth/me")
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == "owner@example.com"

    create_key = api_client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "automation",
            "scopes": ["admin", "scan:read", "scan:write"],
        },
        headers=_csrf_headers(api_client),
    )
    assert create_key.status_code == 201, create_key.text
    assert create_key.json()["record"]["name"] == "automation"

    capabilities = api_client.get("/api/v1/system/capabilities")
    assert capabilities.status_code == 200, capabilities.text
    assert capabilities.json()["authentication"]["bootstrap_registration_required"] is False


def test_local_setup_disables_legacy_api_key_bootstrap(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    response = api_client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "legacy-bootstrap",
            "scopes": ["admin"],
        },
    )

    assert response.status_code == 401, response.text


def test_local_setup_can_only_run_once(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    first = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
        headers=_csrf_headers(api_client),
    )
    assert first.status_code == 201, first.text

    second = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "other@example.com",
            "password": "super-secret-password",
            "name": "Other",
        },
        headers=_csrf_headers(api_client),
    )

    assert second.status_code == 409, second.text


def test_local_login_restores_session_after_logout(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    setup_response = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
        headers=_csrf_headers(api_client),
    )
    assert setup_response.status_code == 201, setup_response.text

    logout_response = api_client.post(
        "/api/v1/auth/local/logout", headers=_csrf_headers(api_client)
    )
    assert logout_response.status_code == 200, logout_response.text

    me_response = api_client.get("/api/v1/auth/me")
    assert me_response.status_code == 401, me_response.text

    login_response = api_client.post(
        "/api/v1/auth/local/login",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
        },
        headers=_csrf_headers(api_client),
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["auth_provider"] == "local"

    restored_session = api_client.get("/api/v1/auth/me")
    assert restored_session.status_code == 200, restored_session.text
    assert restored_session.json()["email"] == "owner@example.com"


def test_local_login_is_rate_limited(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)
    RateLimiter._instance = None
    RateLimiter._initialized = False
    monkeypatch.setattr(
        auth_module,
        "AUTH_ENDPOINT_RATE_LIMIT",
        RateLimitConfig(max_requests=2, window_seconds=60),
    )

    setup_response = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
        headers=_csrf_headers(api_client),
    )
    assert setup_response.status_code == 201, setup_response.text

    logout_response = api_client.post(
        "/api/v1/auth/local/logout", headers=_csrf_headers(api_client)
    )
    assert logout_response.status_code == 200, logout_response.text

    invalid_payload = {
        "email": "owner@example.com",
        "password": "wrong-password",
    }
    first = api_client.post(
        "/api/v1/auth/local/login", json=invalid_payload, headers=_csrf_headers(api_client)
    )
    second = api_client.post(
        "/api/v1/auth/local/login", json=invalid_payload, headers=_csrf_headers(api_client)
    )
    third = api_client.post(
        "/api/v1/auth/local/login", json=invalid_payload, headers=_csrf_headers(api_client)
    )

    assert first.status_code == 401, first.text
    assert second.status_code == 401, second.text
    assert third.status_code == 429, third.text


def test_local_setup_returns_conflict_if_bootstrap_race_loses(
    api_client,
    monkeypatch,
) -> None:
    _enable_local_auth(monkeypatch)

    with Session(database_module.engine) as session:
        session.add(
            User(
                email="owner@example.com",
                name="Owner",
                tenant_slug="default",
                auth_provider=AuthProvider.LOCAL,
                password_hash=hash_password("super-secret-password"),
                role=UserRole.ADMIN,
                onboarding_completed=True,
            )
        )
        session.commit()

    monkeypatch.setattr(auth_module, "bootstrap_registration_required", lambda session: True)

    response = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "other@example.com",
            "password": "super-secret-password",
            "name": "Other",
        },
        headers=_csrf_headers(api_client),
    )

    assert response.status_code == 409, response.text


def test_local_mutation_endpoints_require_csrf(api_client, monkeypatch) -> None:
    _enable_local_auth(monkeypatch)

    setup = api_client.post(
        "/api/v1/auth/local/setup",
        json={
            "email": "owner@example.com",
            "password": "super-secret-password",
            "name": "Owner",
        },
    )
    assert setup.status_code == 403
    assert "CSRF token" in setup.text


def test_csrf_endpoint_issues_token(api_client, monkeypatch) -> None:
    _enable_local_auth(monkeypatch)

    response = api_client.get("/api/v1/auth/csrf")

    assert response.status_code == 200
    payload = response.json()
    assert payload["csrf_token"]
    assert payload["header"] == "X-CSRF-Token"
