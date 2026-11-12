"""WorkOS authentication endpoints for SaaS platform.

Implements Section 15 of the specification:
- OAuth2 Authorization Code Flow
- JWT verification and session management
- User upsertion on login
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.core.auth_middleware import JWTVerificationError
from app.core.config import settings
from app.core.csrf import enforce_csrf, enforce_csrf_if_session
from app.core.database import get_session
from app.core.local_auth import LocalAuthError
from app.core.rate_limiter import AUTH_ENDPOINT_RATE_LIMIT, check_rate_limit
from app.core.security import get_authenticated_user, require_scope
from app.core.workos_session import (
    SessionCookieError,
    clear_workos_cookie,
    decode_workos_cookie,
    set_workos_cookie,
    workos_auth_configured,
)
from app.models import (
    AuthProvider,
    PlatformRole,
    SaaSTenantTier,
    Tenant,
    TenantBillingStatus,
    TenantDeploymentMode,
    User,
    UserPublic,
    UserRole,
    UserUpdate,
    WorkOSInvitationCreate,
    WorkOSInvitationPublic,
)
from app.services.tenants import upsert_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _state_cookie_key(state: str) -> str:
    return f"auth_state_{state}"


def _state_next_cookie_key(state: str) -> str:
    return f"auth_next_{state}"


def _state_invite_cookie_key(state: str) -> str:
    return f"auth_invite_{state}"


def _request_ip_address(request: Request) -> str | None:
    for header_name in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
        raw_value = (request.headers.get(header_name) or "").strip()
        if not raw_value:
            continue
        return raw_value.split(",", 1)[0].strip() or None

    if request.client and request.client.host:
        return request.client.host
    return None


def _request_user_agent(request: Request) -> str | None:
    user_agent = (request.headers.get("user-agent") or "").strip()
    return user_agent or None


def _workos_cookie_password() -> str:
    secret = (settings.session_secret or settings.workos_session_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SaaS authentication is not configured",
        )
    return secret


def _expected_web_origin() -> str | None:
    parsed = urlparse(settings.vigilweave_web_base_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _enforce_same_origin_post(request: Request) -> None:
    """Block cross-site cookie-auth POSTs when the browser sends an Origin header."""

    expected_origin = _expected_web_origin()
    origin = request.headers.get("origin")
    if expected_origin and origin and origin != expected_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site request blocked",
        )


def _callback_error_redirect(
    error: str, description: str, state: str | None = None
) -> RedirectResponse:
    query = urlencode({"error": error, "error_description": description})
    response = RedirectResponse(url=f"{settings.vigilweave_web_base_url}/auth/callback?{query}")
    clear_workos_cookie(response, "auth_state")
    if state:
        clear_workos_cookie(response, _state_cookie_key(state))
        clear_workos_cookie(response, _state_next_cookie_key(state))
        clear_workos_cookie(response, _state_invite_cookie_key(state))
    return response


def _normalize_next_path(value: str | None, fallback: str = "/projects") -> str:
    candidate = (value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return fallback
    if candidate in {"/login", "/signup", "/setup"}:
        return fallback
    if candidate.startswith("/auth/callback") or candidate.startswith("/onboarding"):
        return fallback
    return candidate


def _post_auth_redirect_url(*, onboarding_completed: bool, next_path: str) -> str:
    if not onboarding_completed:
        query = urlencode({"next": next_path})
        return f"{settings.vigilweave_web_base_url}/onboarding?{query}"
    return f"{settings.vigilweave_web_base_url}{next_path}"


def _get_workos_client() -> Any:
    if settings.resolved_session_auth_provider() != "workos":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WorkOS authentication is not enabled",
        )
    if not workos_auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SaaS authentication is not configured",
        )

    try:
        from workos import WorkOSClient
    except ImportError as exc:
        logger.warning("workos package not installed, SaaS auth disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SaaS authentication is not configured",
        ) from exc

    client = WorkOSClient(
        api_key=settings.workos_api_key,
        client_id=settings.workos_client_id,
    )
    return client


def _get_user_management() -> Any:
    client = _get_workos_client()
    return client.user_management


def _get_workos_organizations() -> Any:
    client = _get_workos_client()
    return client.organizations


def _require_authenticated_user(session: Session, request: Request) -> User:
    session_cookie = request.cookies.get("vigilweave_session")
    if not session_cookie:
        logger.warning(
            "Browser session cookie missing on %s (origin=%s referer=%s cookie_header_present=%s)",
            request.url.path,
            request.headers.get("origin"),
            request.headers.get("referer"),
            bool(request.headers.get("cookie")),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        user = get_authenticated_user(session, session_cookie)
    except (JWTVerificationError, SessionCookieError, LocalAuthError) as exc:
        logger.warning("Browser session verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user


@router.get("/login")
def login(request: Request, next: str | None = None, invite: str | None = None) -> RedirectResponse:
    """Redirect to WorkOS AuthKit hosted login page."""

    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="authentication")
    user_management = _get_user_management()

    # Generate state for CSRF protection
    state = str(uuid.uuid4())

    # Build authorization URL
    authorization_url = user_management.get_authorization_url(
        provider="authkit",
        redirect_uri=settings.workos_redirect_uri,
        state=state,
        screen_hint="sign-in",
    )

    # Set state cookie (short-lived)
    response = RedirectResponse(url=authorization_url)
    set_workos_cookie(
        key=_state_cookie_key(state),
        purpose="state",
        response=response,
        value=state,
        max_age=300,  # 5 minutes
    )
    set_workos_cookie(
        key=_state_next_cookie_key(state),
        purpose="next",
        response=response,
        value=_normalize_next_path(next),
        max_age=300,
    )
    if invite and invite.strip():
        set_workos_cookie(
            key=_state_invite_cookie_key(state),
            purpose="invite",
            response=response,
            value=invite.strip(),
            max_age=300,
        )

    return response


@router.get("/callback")
def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle WorkOS OAuth callback, exchange code for tokens, upsert user."""

    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="authentication")

    if error:
        logger.error("WorkOS auth error: %s - %s", error, error_description)
        return _callback_error_redirect(error, error_description or error)

    if not code:
        return _callback_error_redirect("invalid_request", "Authorization code is required")

    # Verify state to prevent CSRF
    try:
        cookie_state = decode_workos_cookie(
            "state",
            request.cookies.get(_state_cookie_key(state or ""))
            or request.cookies.get("auth_state"),
        )
    except SessionCookieError:
        return _callback_error_redirect(
            "invalid_state", "State cookie is missing or invalid", state=state
        )

    if not cookie_state or cookie_state != state:
        return _callback_error_redirect("invalid_state", "Invalid state parameter", state=state)

    try:
        next_path = _normalize_next_path(
            decode_workos_cookie("next", request.cookies.get(_state_next_cookie_key(state)))
        )
    except SessionCookieError:
        next_path = "/projects"

    user_management = _get_user_management()

    # Exchange code for user authentication response
    try:
        auth_response = user_management.authenticate_with_code(
            code=code,
            ip_address=_request_ip_address(request),
            user_agent=_request_user_agent(request),
        )
    except Exception as exc:
        error_code = str(getattr(exc, "error", "") or "authentication_failed")
        description = str(
            getattr(exc, "error_description", "") or "Failed to authenticate with WorkOS"
        )
        logger.exception(
            "WorkOS token exchange failed: %s (%s: %s)",
            exc.__class__.__name__,
            error_code,
            description,
        )
        return _callback_error_redirect(
            error_code,
            description,
            state=state,
        )

    # Upsert user in database
    user = _upsert_user(session, auth_response.user)

    access_token = getattr(auth_response, "access_token", None)
    refresh_token = getattr(auth_response, "refresh_token", None)
    sealed_session = getattr(auth_response, "sealed_session", None)
    logger.info(
        (
            "WorkOS callback authenticated user %s "
            "(redirect=%s access_token_len=%s refresh_token_len=%s sealed_session_len=%s)"
        ),
        user.email,
        "onboarding" if not user.onboarding_completed else "dashboard",
        len(access_token) if isinstance(access_token, str) else None,
        len(refresh_token) if isinstance(refresh_token, str) else None,
        len(sealed_session) if isinstance(sealed_session, str) else None,
    )

    # Set session cookies
    redirect_response = RedirectResponse(
        url=_post_auth_redirect_url(
            onboarding_completed=user.onboarding_completed,
            next_path=next_path,
        )
    )

    # Clear state cookie
    clear_workos_cookie(redirect_response, "auth_state")
    clear_workos_cookie(redirect_response, _state_cookie_key(state))
    clear_workos_cookie(redirect_response, _state_next_cookie_key(state))
    clear_workos_cookie(redirect_response, _state_invite_cookie_key(state))

    # Set session cookies (long-lived)
    set_workos_cookie(
        response=redirect_response,
        key="vigilweave_session",
        purpose="session",
        value=auth_response.access_token,
        max_age=86400,  # 24 hours
    )

    if auth_response.refresh_token:
        set_workos_cookie(
            response=redirect_response,
            key="vigilweave_refresh",
            purpose="refresh",
            value=auth_response.refresh_token,
            max_age=7 * 86400,  # 7 days
        )

    logger.info(
        "WorkOS callback set %s Set-Cookie headers for %s",
        len(redirect_response.headers.getlist("set-cookie")),
        user.email,
    )

    return redirect_response


def _slugify_tenant_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized or "default"


def _resolve_tenant_slug(
    session: Session,
    workos_user: Any,
    existing_user: User | None = None,
) -> str:
    organization_id = getattr(workos_user, "organization_id", None)
    if organization_id:
        tenant = session.exec(select(Tenant).where(Tenant.workos_org_id == organization_id)).first()
        if tenant and tenant.slug:
            return tenant.slug
        return f"workos-org-{_slugify_tenant_part(str(organization_id))}"
    if existing_user and existing_user.tenant_slug and existing_user.tenant_slug != "default":
        return existing_user.tenant_slug
    return f"workos-user-{_slugify_tenant_part(str(workos_user.id))}"


def _resolve_user_role(
    session: Session,
    tenant_slug: str,
    workos_user: Any,
    existing_user: User | None = None,
) -> UserRole:
    if existing_user and existing_user.role in {UserRole.ADMIN, UserRole.MEMBER}:
        return existing_user.role

    # Don't trust the WorkOS role claim directly — it can be set by anyone
    # with dashboard access.  Only use it for "member" (downgrade is safe).
    claimed_role = str(getattr(workos_user, "role", "") or "").lower()
    if claimed_role == UserRole.MEMBER.value:
        return UserRole.MEMBER

    # First user in the tenant gets admin, everyone else is a member.
    statement = select(User.id).where(User.tenant_slug == tenant_slug)
    existing_tenant_user = session.exec(statement.limit(1)).first()
    return UserRole.MEMBER if existing_tenant_user is not None else UserRole.ADMIN


def _upsert_user(session: Session, workos_user: Any) -> User:
    """Create or update user from WorkOS user data."""

    # Try to find existing user
    user = session.exec(select(User).where(User.workos_user_id == workos_user.id)).first()
    tenant_slug = _resolve_tenant_slug(session, workos_user, user)
    role = _resolve_user_role(
        session,
        tenant_slug,
        workos_user,
        existing_user=user,
    )
    avatar_url = getattr(workos_user, "profile_picture_url", None) or getattr(
        workos_user, "avatar_url", None
    )
    should_bootstrap_platform_role = (
        settings.is_vigilweave_cloud()
        and workos_user.email.strip().lower() in settings.platform_admin_bootstrap_emails()
    )
    tenant_display_name = (
        getattr(workos_user, "organization_name", None)
        or getattr(workos_user, "organization", None)
        or getattr(workos_user, "first_name", None)
        or getattr(workos_user, "name", None)
        or tenant_slug
    )
    upsert_tenant(
        session,
        slug=tenant_slug,
        display_name=str(tenant_display_name),
        billing_email=workos_user.email,
        deployment_mode=TenantDeploymentMode.SAAS,
        plan_tier=(SaaSTenantTier.ENTERPRISE if settings.is_vigilweave_cloud() else None),
        billing_status=TenantBillingStatus.MANUAL if settings.is_vigilweave_cloud() else None,
        workos_org_id=getattr(workos_user, "organization_id", None),
    )

    if user:
        # Update existing user
        user.email = workos_user.email
        user.name = getattr(workos_user, "first_name", None) or getattr(workos_user, "name", None)
        user.avatar_url = avatar_url
        user.tenant_slug = tenant_slug
        user.auth_provider = AuthProvider.WORKOS
        user.role = role
        if should_bootstrap_platform_role:
            user.platform_role = PlatformRole.OPERATOR
        if role != UserRole.ADMIN:
            user.onboarding_completed = True
        user.last_login_at = datetime.now(UTC)
        if getattr(workos_user, "organization_id", None):
            user.workos_org_id = workos_user.organization_id
    else:
        # Create new user
        user = User(
            workos_user_id=workos_user.id,
            email=workos_user.email,
            name=getattr(workos_user, "first_name", None) or getattr(workos_user, "name", None),
            avatar_url=avatar_url,
            tenant_slug=tenant_slug,
            auth_provider=AuthProvider.WORKOS,
            workos_org_id=getattr(workos_user, "organization_id", None),
            role=role,
            platform_role=(
                PlatformRole.OPERATOR if should_bootstrap_platform_role else PlatformRole.NONE
            ),
            onboarding_completed=role != UserRole.ADMIN,
            created_at=datetime.now(UTC),
            last_login_at=datetime.now(UTC),
        )
        session.add(user)

    session.commit()
    session.refresh(user)
    return user


def _to_invitation_public(invitation: Any) -> WorkOSInvitationPublic:
    return WorkOSInvitationPublic(
        id=str(invitation.id),
        email=str(invitation.email),
        state=str(invitation.state),
        expires_at=str(invitation.expires_at),
        accepted_at=(
            str(invitation.accepted_at) if getattr(invitation, "accepted_at", None) else None
        ),
        revoked_at=(
            str(invitation.revoked_at) if getattr(invitation, "revoked_at", None) else None
        ),
        organization_id=(
            str(invitation.organization_id)
            if getattr(invitation, "organization_id", None)
            else None
        ),
        inviter_user_id=(
            str(invitation.inviter_user_id)
            if getattr(invitation, "inviter_user_id", None)
            else None
        ),
        created_at=str(invitation.created_at),
        updated_at=str(invitation.updated_at),
    )


def _tenant_workos_org_id(session: Session, tenant_slug: str) -> str | None:
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    return tenant.workos_org_id if tenant else None


def _ensure_tenant_workos_org(session: Session, tenant_slug: str) -> str:
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None:
        tenant = upsert_tenant(session, slug=tenant_slug, display_name=tenant_slug)

    if tenant.workos_org_id:
        return tenant.workos_org_id

    organization = _get_workos_organizations().create_organization(
        name=tenant.display_name or tenant.slug,
        external_id=tenant.slug,
    )
    tenant.workos_org_id = str(organization.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant.workos_org_id


def _require_invitation_in_tenant(session: Session, tenant_slug: str, invitation_id: str) -> Any:
    organization_id = _tenant_workos_org_id(session, tenant_slug)
    if not organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    invitation = _get_user_management().get_invitation(invitation_id)
    if getattr(invitation, "organization_id", None) != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


@router.post("/refresh")
def refresh_token(request: Request, response: Response) -> dict[str, str]:
    """Refresh access token using refresh token."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="authentication")

    try:
        refresh_token = decode_workos_cookie("refresh", request.cookies.get("vigilweave_refresh"))
    except SessionCookieError as exc:
        clear_workos_cookie(response, "vigilweave_session")
        clear_workos_cookie(response, "vigilweave_refresh")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token found"
        )

    user_management = _get_user_management()

    try:
        # Refresh the session
        auth_response = user_management.authenticate_with_refresh_token(
            refresh_token=refresh_token,
            ip_address=_request_ip_address(request),
            user_agent=_request_user_agent(request),
        )

        # Update cookies
        set_workos_cookie(
            response=response,
            key="vigilweave_session",
            purpose="session",
            value=auth_response.access_token,
            max_age=86400,
        )
        if auth_response.refresh_token:
            set_workos_cookie(
                response=response,
                key="vigilweave_refresh",
                purpose="refresh",
                value=auth_response.refresh_token,
                max_age=7 * 86400,
            )

        return {"status": "refreshed"}
    except Exception as exc:
        logger.error("Token refresh failed: %s", exc)
        clear_workos_cookie(response, "vigilweave_session")
        clear_workos_cookie(response, "vigilweave_refresh")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to refresh token"
        ) from exc


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    """Clear session cookies."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)
    clear_workos_cookie(response, "vigilweave_session")
    clear_workos_cookie(response, "vigilweave_refresh")
    clear_workos_cookie(response, "auth_state")

    return {"status": "logged_out"}


@router.get("/invitations", response_model=list[WorkOSInvitationPublic])
def list_invitations(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[WorkOSInvitationPublic]:
    """List tenant invitations backed by WorkOS email invites."""

    organization_id = _tenant_workos_org_id(session, principal.tenant_slug)
    if not organization_id:
        return []

    invitations = _get_user_management().list_invitations(
        organization_id=organization_id, limit=100
    )
    return [_to_invitation_public(invitation) for invitation in invitations.data]


@router.post(
    "/invitations", response_model=WorkOSInvitationPublic, status_code=status.HTTP_201_CREATED
)
def create_invitation(
    payload: WorkOSInvitationCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> WorkOSInvitationPublic:
    """Send a WorkOS email invitation for the current tenant."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)

    organization_id = _ensure_tenant_workos_org(session, principal.tenant_slug)
    inviter = session.get(User, principal.user_id) if principal.user_id is not None else None
    invitation = _get_user_management().send_invitation(
        email=payload.email.strip().lower(),
        organization_id=organization_id,
        inviter_user_id=inviter.workos_user_id if inviter and inviter.workos_user_id else None,
    )
    return _to_invitation_public(invitation)


@router.post("/invitations/{invitation_id}/resend", response_model=WorkOSInvitationPublic)
def resend_invitation(
    invitation_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> WorkOSInvitationPublic:
    """Resend a tenant invitation email through WorkOS."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)
    _require_invitation_in_tenant(session, principal.tenant_slug, invitation_id)
    invitation = _get_user_management().resend_invitation(invitation_id)
    return _to_invitation_public(invitation)


@router.post("/invitations/{invitation_id}/revoke", response_model=WorkOSInvitationPublic)
def revoke_invitation(
    invitation_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> WorkOSInvitationPublic:
    """Revoke a pending tenant invitation."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)
    _require_invitation_in_tenant(session, principal.tenant_slug, invitation_id)
    invitation = _get_user_management().revoke_invitation(invitation_id)
    return _to_invitation_public(invitation)


@router.get("/me", response_model=UserPublic)
def get_me(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """Get current user profile."""

    return _require_authenticated_user(session, request)


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UserUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """Update current user profile."""

    _enforce_same_origin_post(request)
    enforce_csrf(request)
    user = _require_authenticated_user(session, request)

    # Update allowed fields
    if payload.name is not None:
        user.name = payload.name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.onboarding_completed is not None:
        user.onboarding_completed = payload.onboarding_completed

    session.add(user)
    session.commit()
    session.refresh(user)

    return user
