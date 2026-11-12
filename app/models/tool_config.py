"""Tool configuration governance models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import ConfigDict, model_validator
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class ToolConfigItem(SQLModel):
    """Single tool configuration entry."""

    tool: str
    category: str
    languages: list[str]
    enabled: bool
    runtime_available: bool = False
    overridden: bool = False
    base_defined: bool = True
    raw: dict[str, Any] = Field(default_factory=dict)


class ScanTypeConfigItem(SQLModel):
    """Single scan-type configuration entry."""

    name: str
    categories: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class ToolConfigSnapshot(SQLModel):
    """Full tool configuration snapshot."""

    tools: list[ToolConfigItem] = Field(default_factory=list)
    scan_types: list[ScanTypeConfigItem] = Field(default_factory=list)


class ToolConfigPatch(SQLModel):
    """Patch payload for tool config updates."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    category: str | None = PydanticField(default=None, pattern=r"^[a-z0-9-]+$")
    languages: list[str] | None = None
    runner: str | None = PydanticField(default=None, pattern=r"^[a-z0-9-]+$")
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "ToolConfigPatch":
        if (
            self.enabled is None
            and self.category is None
            and self.languages is None
            and self.runner is None
            and self.rules is None
        ):
            raise ValueError("At least one field must be provided")
        if self.languages is not None:
            if not self.languages:
                raise ValueError("languages cannot be empty")
            normalized = [
                language.strip().lower() for language in self.languages if language.strip()
            ]
            if not normalized:
                raise ValueError("languages cannot be empty")
            self.languages = sorted(set(normalized))
        return self


class ToolConfigCreate(SQLModel):
    """Tenant-scoped custom tool configuration payload."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    category: str = PydanticField(pattern=r"^[a-z0-9-]+$")
    languages: list[str]
    runner: str | None = PydanticField(default=None, pattern=r"^[a-z0-9-]+$")
    rules: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_create(self) -> "ToolConfigCreate":
        normalized = [language.strip().lower() for language in self.languages if language.strip()]
        if not normalized:
            raise ValueError("languages cannot be empty")
        self.languages = sorted(set(normalized))
        return self


class TenantToolConfigOverride(SQLModel, table=True):
    """Tenant-level override for a tool definition."""

    __tablename__ = "tenant_tool_config_overrides"
    __table_args__ = (UniqueConstraint("tenant_slug", "tool", name="uq_tenant_tool_override"),)

    id: int | None = Field(default=None, primary_key=True)
    tenant_slug: str = Field(index=True)
    tool: str = Field(index=True)
    override: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantToolConfigOverridePublic(SQLModel):
    """Public response for one tenant-level tool override."""

    id: int
    tenant_slug: str
    tool: str
    override: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
