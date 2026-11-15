"""JWT verification middleware for SaaS authentication.

Provides centralized JWT verification and user extraction for WorkOS sessions.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from jwt import PyJWKClient
from sqlmodel import Session

from app.core.config import settings
from app.models import User

logger = logging.getLogger(__name__)


class JWTVerificationError(Exception):
    """Raised when JWT verification fails."""

    pass


def verify_workos_jwt(access_token: str) -> dict[str, Any]:
    """Verify a WorkOS JWT access token.

    Validates the token signature using WorkOS JWKS endpoint
    and returns the decoded claims.

    Args:
        access_token: The JWT access token from the cookie

    Returns:
        Dictionary of JWT claims (sub, email, org_id, etc.)

    Raises:
        JWTVerificationError: If token is invalid or expired
    """
    if not settings.workos_client_id:
        raise JWTVerificationError("WorkOS not configured")

    try:
        import jwt

        # Get signing key
        signing_key = get_workos_jwks_client().get_signing_key_from_jwt(access_token)

        # Verify token
        claims = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_iss": False, "verify_aud": False},
        )

        allowed_issuers = {
            "https://api.workos.com",
            f"https://api.workos.com/user_management/{settings.workos_client_id}",
        }
        if claims.get("iss") not in allowed_issuers:
            raise JWTVerificationError("Unexpected token issuer")
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            raise JWTVerificationError("Token subject is required")
        audience = claims.get("aud")
        if audience is not None:
            audiences = audience if isinstance(audience, list) else [audience]
            if settings.workos_client_id not in audiences:
                raise JWTVerificationError("Unexpected token audience")

        return claims
    except JWTVerificationError:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise JWTVerificationError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        logger.debug("WorkOS token rejected (%s)", type(exc).__name__)
        raise JWTVerificationError("Invalid token") from exc
    except Exception as exc:
        logger.warning("WorkOS verification failed (%s)", type(exc).__name__)
        raise JWTVerificationError("Token verification failed") from exc


@lru_cache(maxsize=1)
def get_workos_jwks_client() -> PyJWKClient:
    """Return a shared JWKS client with server-side caching enabled."""

    if not settings.workos_client_id:
        raise JWTVerificationError("WorkOS client id is not configured")

    return PyJWKClient(
        f"https://api.workos.com/sso/jwks/{settings.workos_client_id}",
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=settings.workos_jwks_cache_seconds,
        timeout=int(settings.external_api_timeout_seconds),
    )


def get_user_from_jwt(session: Session, access_token: str) -> User | None:
    """Get user from database using JWT claims.

    Args:
        session: Database session
        access_token: JWT access token

    Returns:
        User if found, None otherwise
    """
    from sqlmodel import select

    from app.core.local_auth import resolve_session_binding
    from app.core.workos_session import SessionCookieError

    try:
        bound_user, token = resolve_session_binding(session, access_token)
    except SessionCookieError:
        return None
    claims = verify_workos_jwt(token)
    workos_user_id = claims.get("sub")

    if not workos_user_id:
        return None

    user = session.exec(select(User).where(User.workos_user_id == workos_user_id)).first()

    return user if user is not None and user.id == bound_user.id else None
