"""SCM connection models for PAT-based repository access."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SCMProvider(StrEnum):
    """Supported SCM providers."""

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure_devops"


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------


class SCMConnection(SQLModel, table=True):
    """A stored SCM connection with encrypted PAT."""

    __tablename__ = "scm_connections"

    id: int | None = Field(default=None, primary_key=True)
    tenant_slug: str = Field(default="default", index=True)
    name: str
    provider: SCMProvider
    base_url: str
    encrypted_token: str
    token_masked: str = ""
    extra_config: dict | None = Field(default=None, sa_column=Column(JSON))
    is_active: bool = Field(default=True)
    last_tested_at: datetime | None = None
    last_test_ok: bool | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------


class SCMConnectionCreate(SQLModel):
    """Payload to create an SCM connection."""

    name: str
    provider: SCMProvider
    base_url: str
    token: str  # plaintext — encrypted before storage
    extra_config: dict | None = None


class SCMConnectionUpdate(SQLModel):
    """Payload to update an SCM connection."""

    name: str | None = None
    base_url: str | None = None
    token: str | None = None  # plaintext — re-encrypted if provided
    extra_config: dict | None = None
    is_active: bool | None = None


class SCMConnectionPublic(SQLModel):
    """SCM connection response — token is always masked."""

    id: int
    tenant_slug: str
    name: str
    provider: SCMProvider
    base_url: str
    token_masked: str  # e.g. "ghp_****abcd"
    extra_config: dict | None = None
    is_active: bool
    last_tested_at: datetime | None = None
    last_test_ok: bool | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


class SCMConnectionTestResult(SQLModel):
    """Result of testing an SCM connection."""

    ok: bool
    message: str
    username: str | None = None


class SCMOrganization(SQLModel):
    """An organization/group/workspace from an SCM provider."""

    id: str
    name: str
    avatar_url: str | None = None


class SCMRepository(SQLModel):
    """A repository listed from an SCM provider."""

    id: str
    name: str
    full_name: str
    clone_url: str
    default_branch: str | None = None
    description: str | None = None
    language: str | None = None
    is_private: bool = False
    updated_at: str | None = None


class SCMImportReposRequest(SQLModel):
    """Payload to import selected repos from an SCM connection."""

    project_key: str
    repos: list[str]  # clone URLs to import
