"""Built-in local-user authentication helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlmodel import Session

from app.core.workos_session import SessionCookieError, decode_session_cookie, set_session_cookie
from app.models import User

_LOCAL_PASSWORD_ALGORITHM = "pbkdf2_sha256"
_LOCAL_PASSWORD_ITERATIONS = 600_000


class LocalAuthError(ValueError):
    """Raised when local-user authentication fails."""


def hash_password(password: str) -> str:
    """Hash a local-user password using PBKDF2-SHA256."""

    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _LOCAL_PASSWORD_ITERATIONS,
    )
    return (
        f"{_LOCAL_PASSWORD_ALGORITHM}${_LOCAL_PASSWORD_ITERATIONS}"
        f"${salt}${derived.hex()}"
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Verify a password against a stored PBKDF2-SHA256 hash."""

    if not stored_hash:
        return False

    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != _LOCAL_PASSWORD_ALGORITHM:
        return False

    try:
        rounds = int(iterations)
    except ValueError:
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        rounds,
    ).hex()
    return hmac.compare_digest(candidate, digest)


def set_local_session(response, *, user_id: int, max_age: int = 86400) -> None:
    """Set the local-user browser session cookie."""

    set_session_cookie(
        response=response,
        key="vigilweave_session",
        purpose="local_session",
        value=str(user_id),
        max_age=max_age,
    )


def get_local_user_from_session(session: Session, session_cookie: str | None) -> User | None:
    """Resolve a local user from the encrypted browser session cookie."""

    user_id_value = decode_session_cookie("local_session", session_cookie)
    if user_id_value is None:
        return None

    try:
        user_id = int(user_id_value)
    except ValueError as exc:
        raise SessionCookieError("Invalid local session cookie") from exc

    user = session.get(User, user_id)
    if user is None or user.auth_provider != "local":
        raise LocalAuthError("Local session does not reference an active local user")

    return user
