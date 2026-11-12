"""Project and portfolio organizational models."""

import re
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import model_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SelectionMode(StrEnum):
    """Portfolio project-selection strategy."""

    MANUAL = "manual"
    TAGS = "tags"
    REGEX = "regex"
    ALL = "all"


# ---------------------------------------------------------------------------
# Link tables
# ---------------------------------------------------------------------------


class ProjectRepository(SQLModel, table=True):
    """Join table linking projects to repositories (by URL)."""

    __tablename__ = "project_repositories"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True, ondelete="CASCADE")
    repo: str = Field(index=True)
    scm_connection_id: int | None = Field(
        default=None, foreign_key="scm_connections.id", ondelete="SET NULL"
    )
    github_installation_id: int | None = Field(default=None, index=True)
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioProject(SQLModel, table=True):
    """Join table linking portfolios to projects (manual mode)."""

    __tablename__ = "portfolio_projects"

    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolios.id", index=True, ondelete="CASCADE")
    project_id: int = Field(foreign_key="projects.id", index=True, ondelete="CASCADE")
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectBase(SQLModel):
    """Shared project fields."""

    tenant_slug: str = Field(default="default", index=True)
    key: str = Field(index=True)
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    default_branch: str = "main"
    quality_gate_policy_id: int | None = Field(
        default=None, foreign_key="policy_profiles.id", ondelete="SET NULL"
    )
    azure_devops_project: str | None = None


class Project(ProjectBase, table=True):
    """Persisted project entity."""

    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    repo_links: list[ProjectRepository] = Relationship()
    portfolio_links: list[PortfolioProject] = Relationship()


class ProjectCreate(SQLModel):
    """Project creation payload."""

    key: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    default_branch: str = "main"
    quality_gate_policy_id: int | None = None
    azure_devops_project: str | None = None
    repos: list[str] = Field(default_factory=list)
    scm_connection_id: int | None = None
    github_installation_id: int | None = None

    @model_validator(mode="after")
    def validate_create(self) -> "ProjectCreate":
        self.key = self.key.strip()
        self.name = self.name.strip()
        if not self.key:
            raise ValueError("Project key is required")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", self.key):
            raise ValueError("Project key may only contain letters, numbers, and hyphens")
        if not self.name:
            raise ValueError("Project name is required")
        return self


class ProjectUpdate(SQLModel):
    """Project patch payload — all fields optional."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    default_branch: str | None = None
    quality_gate_policy_id: int | None = None
    azure_devops_project: str | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "ProjectUpdate":
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Project name is required")
        return self


class ProjectPublic(SQLModel):
    """Project response payload."""

    id: int
    tenant_slug: str
    key: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    default_branch: str
    quality_gate_policy_id: int | None = None
    azure_devops_project: str | None = None
    repos: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProjectAggregateMetrics(SQLModel):
    """Computed aggregate metrics for a project."""

    project_id: int
    project_key: str
    project_name: str
    repo_count: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    quality_gate_passed: bool | None = None
    avg_quality_score: float | None = None


class ProjectRepoAdd(SQLModel):
    """Payload to add repositories to a project."""

    repos: list[str]
    scm_connection_id: int | None = None
    github_installation_id: int | None = None


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class PortfolioBase(SQLModel):
    """Shared portfolio fields."""

    tenant_slug: str = Field(default="default", index=True)
    key: str = Field(index=True)
    name: str
    description: str | None = None
    parent_id: int | None = Field(default=None, foreign_key="portfolios.id")
    selection_mode: SelectionMode = SelectionMode.MANUAL
    selection_value: str | None = None
    azure_devops_org: str | None = None


class Portfolio(PortfolioBase, table=True):
    """Persisted portfolio entity."""

    __tablename__ = "portfolios"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project_links: list[PortfolioProject] = Relationship()
    children: list["Portfolio"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Portfolio.parent_id]"},
    )


class PortfolioCreate(SQLModel):
    """Portfolio creation payload."""

    key: str
    name: str
    description: str | None = None
    parent_id: int | None = None
    selection_mode: SelectionMode = SelectionMode.MANUAL
    selection_value: str | None = None
    azure_devops_org: str | None = None


class PortfolioUpdate(SQLModel):
    """Portfolio patch payload — all fields optional."""

    name: str | None = None
    description: str | None = None
    parent_id: int | None = None
    selection_mode: SelectionMode | None = None
    selection_value: str | None = None
    azure_devops_org: str | None = None


class PortfolioPublic(SQLModel):
    """Portfolio response payload."""

    id: int
    tenant_slug: str
    key: str
    name: str
    description: str | None = None
    parent_id: int | None = None
    selection_mode: SelectionMode
    selection_value: str | None = None
    azure_devops_org: str | None = None
    project_count: int = 0
    created_at: datetime
    updated_at: datetime


class PortfolioProjectAdd(SQLModel):
    """Payload to add projects to a portfolio (manual mode)."""

    project_keys: list[str]


class PortfolioDetail(SQLModel):
    """Portfolio response with nested project aggregates."""

    id: int
    tenant_slug: str
    key: str
    name: str
    description: str | None = None
    parent_id: int | None = None
    selection_mode: SelectionMode
    selection_value: str | None = None
    azure_devops_org: str | None = None
    projects: list[ProjectAggregateMetrics] = Field(default_factory=list)
    children: list["PortfolioPublic"] = Field(default_factory=list)
    total_findings: int = 0
    critical_findings: int = 0
    quality_gate_passed_pct: float | None = None
    created_at: datetime
    updated_at: datetime
