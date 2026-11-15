"""Regression checks for application-enforced browser session lifetimes."""

import pytest
from sqlmodel import Session

from app.core import database, workos_session
from app.core.config import settings
from app.core.local_auth import get_local_user_from_session
from app.models import AuthProvider, User


@pytest.mark.parametrize(
    "purpose, ttl",
    [
        ("state", 300),
        ("next", 300),
        ("invite", 300),
        ("github-app-install", 600),
        ("local_session", 86400),
        ("session", 86400),
        ("refresh", 604800),
    ],
)
def test_purpose_expiry(monkeypatch, purpose, ttl):
    monkeypatch.setattr(settings, "session_secret", "synthetic-session-secret")
    cipher = workos_session._build_cipher("synthetic-session-secret")
    payload = __import__("json").dumps({"purpose": purpose, "value": "example"}).encode()
    monkeypatch.setattr(workos_session, "_build_cipher", lambda secret: cipher)
    monkeypatch.setattr("time.time", lambda: 1000)
    token = cipher.encrypt_at_time(payload, 1000).decode()
    assert workos_session.decode_session_cookie(purpose, token) == "example"
    monkeypatch.setattr("time.time", lambda: 1001 + ttl)
    with pytest.raises(workos_session.SessionCookieError):
        workos_session.decode_session_cookie(purpose, token)


def test_development_secret_is_not_public_default(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "session_secret", None)
    monkeypatch.setattr(settings, "workos_session_secret", None)
    assert workos_session._session_secret() != "vigilweave-dev-session-secret"
    assert workos_session._session_secret() == workos_session._session_secret()


def test_logout_revokes_all_local_cookies(api_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "session_auth_provider", "local")
    csrf = api_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    setup = api_client.post(
        "/api/v1/auth/local/setup",
        json={"email": "owner@example.com", "password": "synthetic-password"},
        headers=headers,
    )
    assert setup.status_code == 201
    first = api_client.cookies.get("vigilweave_session")
    assert (
        api_client.post(
            "/api/v1/auth/local/login",
            json={"email": "owner@example.com", "password": "synthetic-password"},
            headers=headers,
        ).status_code
        == 200
    )
    second = api_client.cookies.get("vigilweave_session")
    assert api_client.post("/api/v1/auth/local/logout", headers=headers).status_code == 200
    with Session(database.engine) as session:
        for captured in (first, second):
            with pytest.raises(ValueError):
                get_local_user_from_session(session, captured)


@pytest.mark.parametrize(
    "field, value",
    [
        ("role", "admin"),
        ("platform_role", "operator"),
        ("password_hash", "new-hash"),
        ("tenant_slug", "other"),
    ],
)
def test_security_change_invalidates_local_cookie(api_client, field, value):
    from fastapi import Response

    from app.core.local_auth import set_local_session

    with Session(database.engine) as session:
        user = User(email="member@example.com", auth_provider=AuthProvider.LOCAL)
        session.add(user)
        session.commit()
        session.refresh(user)
        response = Response()
        set_local_session(response, user_id=user.id, session_version=user.session_version)
        cookie = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
        setattr(user, field, value)
        session.commit()
        with pytest.raises(ValueError):
            get_local_user_from_session(session, cookie)


def test_workos_session_requires_current_binding(api_client, monkeypatch):
    import json

    from app.core import auth_middleware

    with Session(database.engine) as session:
        user = User(email="workos@example.com", workos_user_id="user_example")
        session.add(user)
        session.commit()
        session.refresh(user)
        monkeypatch.setattr(
            auth_middleware, "verify_workos_jwt", lambda token: {"sub": "user_example"}
        )
        bound = json.dumps(
            {"user_id": user.id, "version": user.session_version, "token": "provider-token"}
        )
        assert auth_middleware.get_user_from_jwt(session, bound).id == user.id
        user.session_version = "changed"
        session.commit()
        assert auth_middleware.get_user_from_jwt(session, bound) is None


def test_workos_refresh_rejects_revoked_cookie_before_provider_call(api_client, monkeypatch):
    from unittest.mock import Mock

    from app.api import auth_workos
    from app.core.local_auth import make_session_binding

    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "auth_mode", None)
    provider = Mock()
    monkeypatch.setattr(auth_workos, "_get_user_management", lambda: provider)
    with Session(database.engine) as session:
        user = User(email="workos@example.com", workos_user_id="user_example")
        session.add(user)
        session.commit()
        session.refresh(user)
        binding = make_session_binding(user.id, user.session_version, "refresh-token")
        user.session_version = "revoked"
        session.commit()
    api_client.cookies.set(
        "vigilweave_refresh", workos_session.encode_workos_cookie("refresh", binding)
    )
    csrf = api_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    result = api_client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert result.status_code == 401
    provider.authenticate_with_refresh_token.assert_not_called()


def test_workos_refresh_and_logout_revoke_every_browser(api_client, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.api import auth_workos
    from app.core import auth_middleware
    from app.core.local_auth import make_session_binding

    monkeypatch.setattr(settings, "auth_mode", None)
    monkeypatch.setattr(settings, "session_auth_provider", "workos")
    monkeypatch.setattr(settings, "workos_api_key", "synthetic")
    monkeypatch.setattr(settings, "workos_client_id", "synthetic")
    monkeypatch.setattr(settings, "session_secret", "synthetic-secret")
    monkeypatch.setattr(auth_middleware, "verify_workos_jwt", lambda token: {"sub": "workos-id"})
    provider = Mock()
    provider.authenticate_with_refresh_token.return_value = SimpleNamespace(
        access_token="new-access", refresh_token="new-refresh"
    )
    monkeypatch.setattr(auth_workos, "_get_user_management", lambda: provider)
    with Session(database.engine) as session:
        user = User(email="workos@example.com", workos_user_id="workos-id")
        session.add(user)
        session.commit()
        session.refresh(user)
        access = workos_session.encode_workos_cookie(
            "session", make_session_binding(user.id, user.session_version, "access")
        )
        refresh = workos_session.encode_workos_cookie(
            "refresh", make_session_binding(user.id, user.session_version, "refresh")
        )
    api_client.cookies.set("vigilweave_refresh", refresh)
    csrf = api_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    assert api_client.post("/api/v1/auth/refresh").status_code == 403
    assert api_client.post("/api/v1/auth/refresh", headers=headers).status_code == 200
    assert api_client.get("/api/v1/auth/me").status_code == 200
    assert api_client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    with Session(database.engine) as session:
        assert (
            auth_middleware.get_user_from_jwt(
                session, workos_session.decode_workos_cookie("session", access)
            )
            is None
        )
    api_client.cookies.set("vigilweave_refresh", refresh)
    assert api_client.post("/api/v1/auth/refresh", headers=headers).status_code == 401
    assert provider.authenticate_with_refresh_token.call_count == 1


def test_configured_secret_is_used(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "stable-synthetic-key")
    assert workos_session._session_secret() == "stable-synthetic-key"
    token = workos_session.encode_session_cookie("state", "state-value")
    workos_session._build_cipher.cache_clear()
    assert workos_session.decode_session_cookie("state", token) == "state-value"
