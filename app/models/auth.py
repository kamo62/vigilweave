"""Authentication and access-key models."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ApiKeyRecordBase(SQLModel):
    """Shared API key fields."""

    tenant_slug: str = Field(default="default", index=True)
    name: str = Field(index=True)
    key_prefix: str = Field(index=True)
    is_active: bool = Field(default=True, index=True)
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class ApiKeyRecord(ApiKeyRecordBase, table=True):
    """Persisted API key record."""

    __tablename__ = "api_keys"

    id: int | None = Field(default=None, primary_key=True)
    key_hash: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None


class ApiKeyPublic(ApiKeyRecordBase):
    """Safe API key response."""

    id: int
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeyCreate(SQLModel):
    """API key creation request."""

    name: str
    scopes: list[str] = Field(default_factory=lambda: ["scan:read", "scan:write"])


class ApiKeyCreateResponse(SQLModel):
    """API key creation response containing the secret once."""

    api_key: str
    record: ApiKeyPublic
