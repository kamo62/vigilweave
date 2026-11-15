"""User model for SaaS authentication."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Index, event, inspect, text
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    """Supported SaaS user roles."""

    MEMBER = "member"
    ADMIN = "admin"


class PlatformRole(str, Enum):
    """Platform-wide SaaS operator roles."""

    NONE = "none"
    OPERATOR = "operator"


class AuthProvider(str, Enum):
    """Supported user authentication providers."""

    LOCAL = "local"
    WORKOS = "workos"


class UserBase(SQLModel):
    """Shared user fields."""

    email: str = Field(index=True, unique=True)
    name: str | None = None
    avatar_url: str | None = None
    tenant_slug: str = Field(default="default", index=True)
    auth_provider: AuthProvider = Field(default=AuthProvider.WORKOS)
    workos_org_id: str | None = Field(default=None, index=True)
    role: UserRole = Field(default=UserRole.MEMBER)
    platform_role: PlatformRole = Field(default=PlatformRole.NONE)
    onboarding_completed: bool = Field(default=False)


class User(UserBase, table=True):
    """Persisted user entity for SaaS authentication."""

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_single_local_account",
            "auth_provider",
            unique=True,
            sqlite_where=text("auth_provider = 'LOCAL'"),
            postgresql_where=text("auth_provider = 'LOCAL'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    workos_user_id: str | None = Field(default=None, index=True, unique=True)
    password_hash: str | None = None
    session_version: str = Field(default_factory=lambda: secrets.token_urlsafe(32), nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = Field(default=None)


class UserPublic(UserBase):
    """User schema for API responses."""

    id: int
    created_at: datetime
    last_login_at: datetime | None


class UserUpdate(SQLModel):
    """User update payload."""

    name: str | None = None
    avatar_url: str | None = None
    onboarding_completed: bool | None = None


class UserRoleUpdate(SQLModel):
    """Admin payload for changing a user's role."""

    role: UserRole


class WorkOSInvitationCreate(SQLModel):
    """Admin payload for sending a WorkOS invitation email."""

    email: str


class WorkOSInvitationPublic(SQLModel):
    """Tenant-scoped WorkOS invitation summary."""

    id: str
    email: str
    state: str
    expires_at: str
    accepted_at: str | None = None
    revoked_at: str | None = None
    organization_id: str | None = None
    inviter_user_id: str | None = None
    created_at: str
    updated_at: str


class UserPlatformRoleUpdate(SQLModel):
    """Operator payload for changing a user's platform role."""

    platform_role: PlatformRole


class LocalUserSetup(SQLModel):
    """Initial self-hosted admin registration payload."""

    email: str
    password: str = Field(min_length=8)
    name: str | None = None


class LocalUserLogin(SQLModel):
    """Local email/password login payload."""

    email: str
    password: str


@event.listens_for(User, "before_update")
def _revoke_on_security_change(mapper, connection, target: User) -> None:
    """Invalidate browser credentials when account authority or identity changes."""
    del mapper, connection
    state = inspect(target)
    assert state is not None
    fields = (
        "role",
        "platform_role",
        "password_hash",
        "auth_provider",
        "tenant_slug",
        "workos_user_id",
        "workos_org_id",
    )
    if any(state.attrs[name].history.has_changes() for name in fields):
        target.session_version = secrets.token_urlsafe(32)
