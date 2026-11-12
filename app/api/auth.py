"""Authentication management endpoints."""

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.csrf import (
    CSRF_HEADER_NAME,
    enforce_csrf,
    enforce_csrf_if_session,
    issue_csrf_cookie,
)
from app.core.database import get_session
from app.core.local_auth import hash_password, set_local_session, verify_password
from app.core.rate_limiter import AUTH_ENDPOINT_RATE_LIMIT, check_rate_limit
from app.core.security import (
    bootstrap_registration_required,
    generate_api_key,
    get_principal,
    hash_api_key,
    require_scope,
)
from app.core.workos_session import clear_session_cookie
from app.models import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyPublic,
    ApiKeyRecord,
    AuthProvider,
    LocalUserLogin,
    LocalUserSetup,
    User,
    UserPublic,
    UserRole,
    UserRoleUpdate,
)
from app.services.policy_engine import write_audit_event
from app.services.tenants import upsert_tenant

router = APIRouter(prefix="/auth", tags=["auth"])


def _expected_web_origin() -> str | None:
    parsed = urlparse(settings.vigilweave_web_base_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _enforce_same_origin_post(request: Request) -> None:
    """Block cross-site cookie-auth POSTs when an Origin header is present."""

    expected_origin = _expected_web_origin()
    origin = request.headers.get("origin")
    if expected_origin and origin and origin != expected_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site request blocked",
        )


def _require_local_provider() -> None:
    if settings.resolved_session_auth_provider() != "local":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local user authentication is not enabled",
        )


@router.get("/api-keys", response_model=list[ApiKeyPublic])
def list_api_keys(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[ApiKeyRecord]:
    """List API keys for the current tenant."""

    statement = select(ApiKeyRecord).where(ApiKeyRecord.tenant_slug == principal.tenant_slug)
    return list(session.exec(statement).all())


@router.get("/csrf")
def csrf_token(request: Request, response: Response) -> dict[str, str]:
    """Issue a CSRF token cookie for browser-session mutation requests."""

    token = issue_csrf_cookie(response, request)
    return {
        "csrf_token": token,
        "header": CSRF_HEADER_NAME,
    }


@router.post("/local/setup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def setup_local_user(
    payload: LocalUserSetup,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> User:
    """Create the first local admin user for a self-hosted deployment."""

    _require_local_provider()
    _enforce_same_origin_post(request)
    enforce_csrf(request)
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="authentication")

    if not bootstrap_registration_required(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Local bootstrap registration is no longer available",
        )

    existing = session.exec(select(User.id).where(User.email == payload.email).limit(1)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        email=payload.email,
        name=payload.name,
        tenant_slug="default",
        auth_provider=AuthProvider.LOCAL,
        workos_user_id=None,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN,
        onboarding_completed=True,
    )
    upsert_tenant(
        session,
        slug="default",
        display_name="Default Tenant",
        billing_email=payload.email,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Local bootstrap registration is no longer available",
        ) from exc
    session.refresh(user)
    set_local_session(response, user_id=user.id)
    return user


@router.post("/local/login", response_model=UserPublic)
def login_local_user(
    payload: LocalUserLogin,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> User:
    """Authenticate a built-in local user and start a browser session."""

    _require_local_provider()
    _enforce_same_origin_post(request)
    enforce_csrf(request)
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="authentication")

    user = session.exec(
        select(User).where(
            User.email == payload.email,
            User.auth_provider == AuthProvider.LOCAL,
        )
    ).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user.last_login_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    session.refresh(user)
    set_local_session(response, user_id=user.id)
    return user


@router.post("/local/logout")
def logout_local_user(request: Request, response: Response) -> dict[str, str]:
    """Clear the local browser session cookie."""

    _enforce_same_origin_post(request)
    enforce_csrf_if_session(request)
    clear_session_cookie(response, "vigilweave_session")
    return {"status": "logged_out"}


@router.post(
    "/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(get_principal),
) -> ApiKeyCreateResponse:
    """Create a new API key, allowing bootstrap when no keys exist."""

    enforce_csrf_if_session(request)

    existing = session.exec(select(ApiKeyRecord).limit(1)).first()
    if existing and not principal.can("admin"):
        raise HTTPException(status_code=403, detail="Admin scope required")

    prefix, secret = generate_api_key()
    record = ApiKeyRecord(
        tenant_slug=principal.tenant_slug,
        name=payload.name,
        key_prefix=prefix,
        key_hash=hash_api_key(secret),
        scopes=payload.scopes,
    )
    try:
        session.add(record)
        session.flush()
        write_audit_event(
            session,
            tenant_slug=record.tenant_slug,
            actor=principal.actor,
            action="auth.api_key.created",
            entity_type="api_key",
            entity_id=str(record.id),
            details={"name": record.name, "scopes": record.scopes},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="API key already exists") from exc
    session.refresh(record)
    return ApiKeyCreateResponse(api_key=secret, record=ApiKeyPublic.model_validate(record))


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Deactivate an API key."""

    enforce_csrf_if_session(request)

    record = session.get(ApiKeyRecord, key_id)
    if record is None or record.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="API key not found")
    record.is_active = False
    session.add(record)
    write_audit_event(
        session,
        tenant_slug=record.tenant_slug,
        actor=principal.actor,
        action="auth.api_key.revoked",
        entity_type="api_key",
        entity_id=str(record.id),
        details={"name": record.name},
    )
    session.commit()


# ── User Management (admin-only) ──


@router.get("/users", response_model=list[UserPublic])
def list_users(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[User]:
    """List all users in the current tenant."""

    return list(
        session.exec(
            select(User).where(User.tenant_slug == principal.tenant_slug).order_by(User.created_at)
        ).all()
    )


@router.patch("/users/{user_id}/role", response_model=UserPublic)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> User:
    """Change a user's role (admin-only)."""

    enforce_csrf_if_session(request)

    user = session.get(User, user_id)
    if user is None or user.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent demoting yourself
    if user.id == principal.user_id and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote your own account",
        )

    old_role = user.role
    user.role = payload.role
    session.add(user)
    write_audit_event(
        session,
        tenant_slug=user.tenant_slug,
        actor=principal.actor,
        action="user.role_changed",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "old_role": old_role.value, "new_role": payload.role.value},
    )
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Remove a user from the tenant (admin-only)."""

    enforce_csrf_if_session(request)

    user = session.get(User, user_id)
    if user is None or user.tenant_slug != principal.tenant_slug:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    email = user.email
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="user.deleted",
        entity_type="user",
        entity_id=str(user_id),
        details={"email": email},
    )
    session.delete(user)
    session.commit()
