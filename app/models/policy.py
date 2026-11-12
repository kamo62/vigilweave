"""Policy, waiver, and audit models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class PolicyKind(StrEnum):
    """Policy origin and mutability."""

    PRESET = "preset"
    CUSTOM = "custom"


class PolicyPresetKey(StrEnum):
    """Built-in preset identifiers."""

    LENIENT = "lenient"
    BALANCED = "balanced"
    STRICT = "strict"


class PolicyProfileBase(SQLModel):
    """Shared policy profile fields."""

    tenant_slug: str = Field(default="default", index=True)
    name: str = Field(index=True)
    description: str | None = None
    kind: PolicyKind = Field(default=PolicyKind.CUSTOM, index=True)
    preset_key: PolicyPresetKey | None = Field(default=None, index=True)
    repo_pattern: str | None = None
    branch_pattern: str | None = None
    is_default: bool = Field(default=False, index=True)
    max_critical_findings: int = 0
    max_high_findings: int = 5
    min_quality_score: float = 70.0


class PolicyProfile(PolicyProfileBase, table=True):
    """Persisted policy profile."""

    __tablename__ = "policy_profiles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_slug",
            "preset_key",
            name="uq_policy_profiles_tenant_preset_key",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyProfileCreate(SQLModel):
    """Policy creation payload."""

    name: str
    description: str | None = None
    kind: PolicyKind = PolicyKind.CUSTOM
    preset_key: PolicyPresetKey | None = None
    repo_pattern: str | None = None
    branch_pattern: str | None = None
    is_default: bool = False
    max_critical_findings: int = 0
    max_high_findings: int = 5
    min_quality_score: float = 70.0


class PolicyProfileUpdate(SQLModel):
    """Policy update payload."""

    name: str | None = None
    description: str | None = None
    repo_pattern: str | None = None
    branch_pattern: str | None = None
    is_default: bool | None = None
    max_critical_findings: int | None = None
    max_high_findings: int | None = None
    min_quality_score: float | None = None


class PolicyProfilePublic(PolicyProfileBase):
    """Policy response payload."""

    id: int
    created_at: datetime
    updated_at: datetime


class PolicyEvaluation(SQLModel):
    """Resolved policy outcome for a scan."""

    profile_id: int | None = None
    profile_name: str | None = None
    matched: bool = False
    passed: bool = False
    reasons: list[str] = Field(default_factory=list)
    thresholds: dict[str, float | int] = Field(default_factory=dict)


class WaiverBase(SQLModel):
    """Shared waiver fields."""

    tenant_slug: str = Field(default="default", index=True)
    repo_pattern: str | None = None
    branch_pattern: str | None = None
    rule_id: str | None = Field(default=None, index=True)
    fingerprint: str | None = Field(default=None, index=True)
    file_path: str | None = None
    category: str | None = Field(default=None, index=True)
    reason: str
    created_by: str | None = None
    expires_at: datetime | None = None
    is_active: bool = Field(default=True, index=True)


class Waiver(WaiverBase, table=True):
    """Persisted waiver."""

    __tablename__ = "waivers"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WaiverCreate(WaiverBase):
    """Waiver creation payload."""


class WaiverPublic(WaiverBase):
    """Waiver response payload."""

    id: int
    created_at: datetime


class AuditEvent(SQLModel, table=True):
    """Audit trail event."""

    __tablename__ = "audit_events"

    id: int | None = Field(default=None, primary_key=True)
    tenant_slug: str = Field(default="default", index=True)
    actor: str = Field(index=True)
    action: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class AuditEventPublic(SQLModel):
    """Audit trail response."""

    id: int
    tenant_slug: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
