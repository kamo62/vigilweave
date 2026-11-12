"""Helpers for securing browser session cookies."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Response

from app.core.config import settings


class SessionCookieError(ValueError):
    """Raised when an encrypted browser cookie cannot be decoded."""


WorkOSCookieError = SessionCookieError


def workos_auth_configured() -> bool:
    """Return whether browser-based WorkOS auth is fully configured."""

    return bool(
        settings.workos_api_key
        and settings.workos_client_id
        and (settings.session_secret or settings.workos_session_secret)
    )


def session_secret_configured() -> bool:
    """Return whether a browser-session secret is available."""

    if settings.session_secret or settings.workos_session_secret:
        return True
    return settings.environment in {"development", "test"}


def workos_cookie_secure() -> bool:
    """Return whether session cookies should require HTTPS."""

    if settings.environment not in {"development", "test"}:
        return True

    configured_urls = (settings.vigilweave_web_base_url, settings.workos_redirect_uri)
    return any(urlparse(url).scheme.lower() == "https" for url in configured_urls if url)


def _session_secret() -> str:
    secret = (settings.session_secret or settings.workos_session_secret or "").strip()
    if not secret:
        if settings.environment in {"development", "test"}:
            return "vigilweave-dev-session-secret"
        raise SessionCookieError("Session secret is not configured")
    return secret


@lru_cache(maxsize=8)
def _build_cipher(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encode_workos_cookie(purpose: str, value: str) -> str:
    """Encrypt a cookie payload for the given purpose."""

    payload = json.dumps({"purpose": purpose, "value": value}).encode("utf-8")
    return _build_cipher(_session_secret()).encrypt(payload).decode("utf-8")


def decode_workos_cookie(purpose: str, value: str | None) -> str | None:
    """Decrypt and validate a cookie payload for the given purpose."""

    if not value:
        return None

    try:
        payload = _build_cipher(_session_secret()).decrypt(value.encode("utf-8"))
    except InvalidToken as exc:
        raise SessionCookieError(f"Invalid {purpose} cookie") from exc

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionCookieError(f"Malformed {purpose} cookie payload") from exc

    if decoded.get("purpose") != purpose:
        raise SessionCookieError(f"Unexpected cookie purpose for {purpose}")

    raw_value = decoded.get("value")
    if not isinstance(raw_value, str) or not raw_value:
        raise SessionCookieError(f"Missing value in {purpose} cookie")

    return raw_value


def set_workos_cookie(
    response: Response,
    *,
    key: str,
    purpose: str,
    value: str,
    max_age: int,
) -> None:
    """Set a signed and encrypted WorkOS cookie."""

    response.set_cookie(
        key=key,
        value=encode_workos_cookie(purpose, value),
        max_age=max_age,
        httponly=True,
        secure=workos_cookie_secure(),
        samesite="lax",
        domain=settings.workos_cookie_domain,
    )


def clear_workos_cookie(response: Response, key: str) -> None:
    """Delete a WorkOS cookie using the configured cookie domain."""

    response.delete_cookie(key=key, domain=settings.workos_cookie_domain)


def encode_session_cookie(purpose: str, value: str) -> str:
    """Encrypt a generic browser-session cookie payload."""

    return encode_workos_cookie(purpose, value)


def decode_session_cookie(purpose: str, value: str | None) -> str | None:
    """Decrypt a generic browser-session cookie payload."""

    return decode_workos_cookie(purpose, value)


def set_session_cookie(
    response: Response,
    *,
    key: str,
    purpose: str,
    value: str,
    max_age: int,
) -> None:
    """Set a signed and encrypted browser-session cookie."""

    set_workos_cookie(
        response=response,
        key=key,
        purpose=purpose,
        value=value,
        max_age=max_age,
    )


def clear_session_cookie(response: Response, key: str) -> None:
    """Delete a browser-session cookie."""

    clear_workos_cookie(response, key)
