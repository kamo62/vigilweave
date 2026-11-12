"""Authentication and request-context helpers."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.auth_middleware import JWTVerificationError, get_user_from_jwt
from app.core.config import settings
from app.core.database import get_session
from app.core.local_auth import LocalAuthError, get_local_user_from_session
from app.core.workos_session import SessionCookieError, decode_workos_cookie, workos_auth_configured
from app.models import ApiKeyRecord, AuthProvider, PlatformRole, User


@dataclass(slots=True)
class AuthenticatedPrincipal:
    """Resolved caller identity."""

    tenant_slug: str
    actor: str
    scopes: set[str]
    api_key_id: int | None = None
    user_id: int | None = None  # Added for SaaS user tracking
    auth_method: str = "api_key"  # "api_key" | "workos"
    is_platform_operator: bool = False

    def can(self, scope: str) -> bool:
        """Return whether the principal has a given scope."""

        return "admin" in self.scopes or scope in self.scopes


def hash_api_key(secret: str) -> str:
    """Hash an API key for storage and comparison."""

    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate an API key and return its prefix and full secret."""

    secret = f"vw_{secrets.token_urlsafe(24)}"
    return secret[:12], secret


def _extract_bearer_token(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _verify_workos_token(session: Session, access_token: str) -> User | None:
    """Verify WorkOS JWT and return user.

    Delegates to auth_middleware.get_user_from_jwt which performs full
    JWKS signature verification via WorkOS's endpoint.
    """
    if not workos_auth_configured():
        return None

    decoded_token = decode_workos_cookie("session", access_token)
    if decoded_token is None:
        return None
    return get_user_from_jwt(session, decoded_token)


def _verify_local_session(session: Session, session_cookie: str) -> User | None:
    """Verify a local-user browser session and return the matching user."""

    user = get_local_user_from_session(session, session_cookie)
    return user


def anonymous_bootstrap_enabled(session: Session) -> bool:
    """Return whether unauthenticated API-key bootstrap should be allowed."""

    if settings.resolved_session_auth_provider() != "none":
        return False
    if not settings.resolved_api_keys_enabled():
        return False
    return session.exec(select(ApiKeyRecord.id).limit(1)).first() is None


def bootstrap_registration_required(session: Session) -> bool:
    """Return whether the local self-hosted admin setup flow is still required."""

    if settings.resolved_session_auth_provider() != "local":
        return False
    return (
        session.exec(
            select(User.id).where(User.auth_provider == AuthProvider.LOCAL).limit(1)
        ).first()
        is None
    )


def _scopes_for_user(user: User) -> set[str]:
    scopes = {"scan:read", "scan:write", "project:read", "project:write"}
    if user.role == "admin":
        scopes.add("admin")
    return scopes


def _apply_platform_operator_bootstrap(session: Session, user: User) -> User:
    """Persist the platform operator role for bootstrap emails on VigilWeave cloud."""

    if not settings.is_vigilweave_cloud():
        return user
    if user.platform_role == PlatformRole.OPERATOR:
        return user
    if (user.email or "").strip().lower() not in settings.platform_admin_bootstrap_emails():
        return user

    user.platform_role = PlatformRole.OPERATOR
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_authenticated_user(
    session: Session,
    vigilweave_session: str | None,
) -> User | None:
    """Resolve the current browser-session user for the configured provider."""

    if not vigilweave_session:
        return None

    provider = settings.resolved_session_auth_provider()
    if provider == "local":
        return _verify_local_session(session, vigilweave_session)
    if provider == "workos":
        user = _verify_workos_token(session, vigilweave_session)
        if user is not None:
            return _apply_platform_operator_bootstrap(session, user)
        return None
    return None


def get_principal(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_vigilweave_tenant: str | None = Header(default=None, alias="X-VigilWeave-Tenant"),
    x_vigilweave_actor: str | None = Header(default=None, alias="X-VigilWeave-Actor"),
    vigilweave_session: str | None = Cookie(default=None),
) -> AuthenticatedPrincipal:
    """Resolve the current API principal.

    Supports dual auth mode:
    - Checks WorkOS JWT cookie first (for browser/SaaS users)
    - Falls back to API key (for CI/CD, API clients)
    - Bootstrap mode if no API keys exist
    """

    tenant_slug = x_vigilweave_tenant or "default"
    actor = x_vigilweave_actor or "anonymous"
    token = _extract_bearer_token(authorization, x_api_key)

    session_auth_provider = settings.resolved_session_auth_provider()
    api_keys_enabled = settings.resolved_api_keys_enabled()

    # Browser session auth takes precedence for interactive users.
    if session_auth_provider in {"local", "workos"} and vigilweave_session:
        try:
            user = get_authenticated_user(session, vigilweave_session)
        except (JWTVerificationError, SessionCookieError, LocalAuthError) as exc:
            if token is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired session",
                ) from exc
            user = None
        if user:
            if x_vigilweave_tenant and user.tenant_slug != x_vigilweave_tenant:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant header does not match authenticated user",
                )

            return AuthenticatedPrincipal(
                tenant_slug=user.tenant_slug or tenant_slug,
                actor=user.email or actor,
                scopes=_scopes_for_user(user),
                user_id=user.id,
                auth_method=user.auth_provider.value,
                is_platform_operator=user.platform_role == PlatformRole.OPERATOR,
            )

    # Header-based API auth remains available for automation and integrations.
    if api_keys_enabled:
        # Bootstrap mode: no keys exist yet
        if anonymous_bootstrap_enabled(session) and token is None:
            return AuthenticatedPrincipal(
                tenant_slug=tenant_slug,
                actor=actor,
                scopes={"admin"},
                auth_method="api_key",
            )

        if token:
            record = session.exec(
                select(ApiKeyRecord).where(
                    ApiKeyRecord.key_hash == hash_api_key(token),
                    ApiKeyRecord.is_active,
                )
            ).first()

            if record:
                if x_vigilweave_tenant and x_vigilweave_tenant != record.tenant_slug:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Tenant header does not match API key",
                    )

                record.last_used_at = datetime.now(UTC)
                session.add(record)
                session.commit()

                return AuthenticatedPrincipal(
                    tenant_slug=record.tenant_slug,
                    actor=record.name,
                    scopes=set(record.scopes),
                    api_key_id=record.id,
                    auth_method="api_key",
                )

    # No valid auth found
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def maybe_get_principal(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_vigilweave_tenant: str | None = Header(default=None, alias="X-VigilWeave-Tenant"),
    x_vigilweave_actor: str | None = Header(default=None, alias="X-VigilWeave-Actor"),
    vigilweave_session: str | None = Cookie(default=None),
) -> AuthenticatedPrincipal | None:
    """Return the current principal when authenticated, else None."""

    try:
        return get_principal(
            request=request,
            session=session,
            authorization=authorization,
            x_api_key=x_api_key,
            x_vigilweave_tenant=x_vigilweave_tenant,
            x_vigilweave_actor=x_vigilweave_actor,
            vigilweave_session=vigilweave_session,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def require_scope(scope: str):
    """Create a dependency that enforces a scope."""

    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_principal),
    ) -> AuthenticatedPrincipal:
        if not principal.can(scope):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")
        return principal

    return dependency


def require_platform_operator():
    """Create a dependency that restricts access to configured SaaS operators."""

    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_principal),
    ) -> AuthenticatedPrincipal:
        if not principal.is_platform_operator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform operator access is required",
            )
        return principal

    return dependency
