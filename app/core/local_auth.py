"""Built-in local-user authentication helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
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
    return f"{_LOCAL_PASSWORD_ALGORITHM}${_LOCAL_PASSWORD_ITERATIONS}${salt}${derived.hex()}"


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


def set_local_session(
    response, *, user_id: int | None, session_version: str, max_age: int = 86400
) -> None:
    """Set the local-user browser session cookie."""

    set_session_cookie(
        response=response,
        key="vigilweave_session",
        purpose="local_session",
        value=make_session_binding(user_id, session_version),
        max_age=max_age,
    )


def get_local_user_from_session(session: Session, session_cookie: str | None) -> User | None:
    """Resolve a local user from the encrypted browser session cookie."""

    user_id_value = decode_session_cookie("local_session", session_cookie)
    if user_id_value is None:
        return None

    user, _ = resolve_session_binding(session, user_id_value)
    if user.auth_provider != "local":
        raise LocalAuthError("Local session does not reference an active local user")
    return user


def make_session_binding(user_id: int | None, version: str, token: str = "") -> str:
    """Bind a browser credential to a particular account generation."""
    if user_id is None:
        raise SessionCookieError("Cannot bind an unpersisted user")
    return json.dumps({"user_id": user_id, "version": version, "token": token})


def resolve_session_binding(session: Session, value: str) -> tuple[User, str]:
    """Resolve only a current application-issued browser credential."""
    try:
        data = json.loads(value)
        user_id, version, token = data["user_id"], data["version"], data["token"]
        if type(user_id) is not int or not isinstance(version, str) or not isinstance(token, str):
            raise ValueError
    except (ValueError, TypeError, KeyError) as exc:
        raise SessionCookieError("Invalid session binding") from exc
    user = session.get(User, user_id, populate_existing=True)
    if user is None or not hmac.compare_digest(user.session_version, version):
        raise SessionCookieError("Revoked session")
    return user, token
