"""CSRF helpers for browser-session mutation routes."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.core.workos_session import _session_secret, workos_cookie_secure

CSRF_COOKIE_NAME = "vigilweave_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
_CSRF_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def issue_csrf_cookie(response: Response, request: Request | None = None) -> str:
    """Set a signed CSRF cookie and return the token value."""

    existing = request.cookies.get(CSRF_COOKIE_NAME) if request else None
    token = existing if existing and _is_valid_token(existing) else _new_token()

    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=24 * 60 * 60,
        httponly=False,
        secure=workos_cookie_secure(),
        samesite="lax",
        domain=settings.workos_cookie_domain,
    )
    return token


def enforce_csrf(request: Request) -> None:
    """Enforce double-submit cookie CSRF for browser session mutations."""

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token required")
    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if not _is_valid_token(header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def enforce_csrf_if_session(request: Request) -> None:
    """Enforce CSRF only when browser session cookies are present."""

    if request.cookies.get("vigilweave_session"):
        enforce_csrf(request)


def should_enforce_csrf(request: Request) -> bool:
    """Return whether the request should run CSRF validation checks."""

    if request.method.upper() not in _CSRF_MUTATION_METHODS:
        return False

    path = request.url.path
    if not path.startswith(settings.api_v1_prefix):
        return False

    return path != f"{settings.api_v1_prefix}/auth/csrf"


def _new_token() -> str:
    nonce = secrets.token_urlsafe(32)
    signature = _sign(nonce)
    return f"{nonce}.{signature}"


def _is_valid_token(token: str) -> bool:
    try:
        nonce, provided_signature = token.split(".", 1)
    except ValueError:
        return False
    expected_signature = _sign(nonce)
    return hmac.compare_digest(provided_signature, expected_signature)


def _sign(value: str) -> str:
    digest = hmac.new(
        _session_secret().encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest
