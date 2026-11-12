"""Project and portfolio CRUD endpoints."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import Feature, require_feature
from app.core.network_security import is_safe_repo_url
from app.core.security import require_scope
from app.models import TenantGitHubInstallation
from app.models.project import (
    Portfolio,
    PortfolioCreate,
    PortfolioDetail,
    PortfolioProject,
    PortfolioProjectAdd,
    PortfolioPublic,
    PortfolioUpdate,
    Project,
    ProjectAggregateMetrics,
    ProjectCreate,
    ProjectPublic,
    ProjectRepoAdd,
    ProjectRepository,
    ProjectUpdate,
    SelectionMode,
)
from app.models.scan import Scan, ScanStatus
from app.models.scm_connection import SCMConnection
from app.services.policy_engine import write_audit_event

router = APIRouter(tags=["projects"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_repos(session: Session, project_id: int) -> list[str]:
    links = session.exec(
        select(ProjectRepository).where(ProjectRepository.project_id == project_id)
    ).all()
    return [link.repo for link in links]


def _count_projects_for_repo(session: Session, tenant_slug: str, repo: str) -> int:
    return int(
        session.exec(
            select(func.count(func.distinct(Project.id)))
            .join(ProjectRepository, ProjectRepository.project_id == Project.id)
            .where(Project.tenant_slug == tenant_slug, ProjectRepository.repo == repo)
        ).one()
    )


def _backfill_unassigned_scans_for_repo(
    session: Session,
    *,
    tenant_slug: str,
    repo: str,
    project_id: int,
) -> None:
    """Assign historical scans only when the repo maps to exactly one project."""

    if _count_projects_for_repo(session, tenant_slug, repo) != 1:
        return
    for scan in session.exec(
        select(Scan).where(
            Scan.tenant_slug == tenant_slug,
            Scan.repo == repo,
            Scan.project_id.is_(None),
        )
    ).all():
        scan.project_id = project_id
        session.add(scan)


def _validate_repo_credential_source(
    session: Session,
    *,
    tenant_slug: str,
    scm_connection_id: int | None,
    github_installation_id: int | None,
) -> None:
    if scm_connection_id is not None and github_installation_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select either an SCM connection or a GitHub App installation",
        )

    if scm_connection_id is not None:
        connection = session.exec(
            select(SCMConnection).where(
                SCMConnection.id == scm_connection_id,
                SCMConnection.tenant_slug == tenant_slug,
            )
        ).first()
        if connection is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SCM connection not found for this tenant",
            )

    if github_installation_id is not None:
        installation = session.exec(
            select(TenantGitHubInstallation).where(
                TenantGitHubInstallation.tenant_slug == tenant_slug,
                TenantGitHubInstallation.installation_id == github_installation_id,
            )
        ).first()
        if installation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub App installation not found for this tenant",
            )


def _validate_project_repo_url(repo_url: str) -> str:
    candidate = repo_url.strip()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Repository URL is required",
        )
    if not is_safe_repo_url(candidate):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported repository URL. Only https:// and file:// repositories are allowed",
        )
    if candidate.startswith("file://") and not settings.enable_file_repo_access:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Local file:// repository access is disabled",
        )
    return candidate


def _validated_project_repo_urls(repos: list[str]) -> list[str]:
    return [_validate_project_repo_url(repo_url) for repo_url in repos]


def _get_tenant_project_by_id(
    session: Session, tenant_slug: str, project_id: int
) -> Project | None:
    return session.exec(
        select(Project).where(Project.tenant_slug == tenant_slug, Project.id == project_id)
    ).first()


def _delete_project_record(
    session: Session,
    *,
    project: Project,
    tenant_slug: str,
    actor: str,
    project_identifier: str,
    delete_scans: bool,
) -> None:
    deleted_scans = 0
    if delete_scans:
        scans = list(
            session.exec(
                select(Scan).where(
                    Scan.tenant_slug == tenant_slug,
                    Scan.project_id == project.id,
                )
            ).all()
        )
        deleted_scans = len(scans)
        for scan in scans:
            session.delete(scan)
    else:
        for scan in session.exec(
            select(Scan).where(
                Scan.tenant_slug == tenant_slug,
                Scan.project_id == project.id,
            )
        ).all():
            scan.project_id = None
            session.add(scan)

    for link in session.exec(
        select(ProjectRepository).where(ProjectRepository.project_id == project.id)
    ).all():
        session.delete(link)
    for link in session.exec(
        select(PortfolioProject).where(PortfolioProject.project_id == project.id)
    ).all():
        session.delete(link)

    write_audit_event(
        session,
        tenant_slug=tenant_slug,
        actor=actor,
        action="project.deleted",
        entity_type="project",
        entity_id=str(project.id),
        details={"identifier": project_identifier, "deleted_scans": deleted_scans},
    )
    session.delete(project)
    session.commit()


def _project_to_public(session: Session, project: Project) -> ProjectPublic:
    repos = _project_repos(session, project.id)  # type: ignore[arg-type]
    return ProjectPublic(
        **project.model_dump(exclude={"repo_links", "portfolio_links"}),
        repos=repos,
    )


def _compute_project_metrics(
    session: Session, project: Project, repos: list[str], tenant_slug: str
) -> ProjectAggregateMetrics:
    """Compute aggregate metrics for a project from its repos' latest scans."""

    if not repos:
        return ProjectAggregateMetrics(
            project_id=project.id,  # type: ignore[arg-type]
            project_key=project.key,
            project_name=project.name,
        )

    # Single query: latest completed scan per repo
    latest_ids_subq = (
        select(func.max(Scan.id).label("latest_id"))
        .where(
            Scan.tenant_slug == tenant_slug,
            Scan.project_id == project.id,
            Scan.status == ScanStatus.COMPLETED,
        )
        .group_by(Scan.repo)
        .subquery()
    )
    latest_scans = list(
        session.exec(select(Scan).where(Scan.id.in_(select(latest_ids_subq.c.latest_id)))).all()
    )

    total_findings = sum(s.total_findings for s in latest_scans)
    critical_findings = sum(s.critical_findings for s in latest_scans)
    high_findings = sum(s.high_findings for s in latest_scans)
    quality_scores = [s.quality_score for s in latest_scans if s.quality_score is not None]
    gates_with_data = [s for s in latest_scans if s.quality_gate_passed is not None]

    gate_passed: bool | None = None
    if gates_with_data:
        gate_passed = all(s.quality_gate_passed for s in gates_with_data)

    return ProjectAggregateMetrics(
        project_id=project.id,  # type: ignore[arg-type]
        project_key=project.key,
        project_name=project.name,
        repo_count=len(repos),
        total_findings=total_findings,
        critical_findings=critical_findings,
        high_findings=high_findings,
        quality_gate_passed=gate_passed,
        avg_quality_score=sum(quality_scores) / len(quality_scores) if quality_scores else None,
    )


def _resolve_portfolio_projects(
    session: Session, portfolio: Portfolio, tenant_slug: str
) -> list[Project]:
    """Resolve which projects belong to a portfolio based on selection mode."""

    if portfolio.selection_mode == SelectionMode.ALL:
        return list(session.exec(select(Project).where(Project.tenant_slug == tenant_slug)).all())

    if portfolio.selection_mode == SelectionMode.TAGS and portfolio.selection_value:
        tag_list = [t.strip() for t in portfolio.selection_value.split(",") if t.strip()]
        all_projects = session.exec(select(Project).where(Project.tenant_slug == tenant_slug)).all()
        return [p for p in all_projects if set(p.tags or []) & set(tag_list)]

    if portfolio.selection_mode == SelectionMode.REGEX and portfolio.selection_value:
        if len(portfolio.selection_value) > settings.max_regex_pattern_length:
            return []
        try:
            pattern = re.compile(portfolio.selection_value)
        except re.error:
            return []
        all_projects = session.exec(select(Project).where(Project.tenant_slug == tenant_slug)).all()
        return [p for p in all_projects if pattern.search(p.key)]

    # MANUAL mode — use join table
    links = session.exec(
        select(PortfolioProject).where(PortfolioProject.portfolio_id == portfolio.id)
    ).all()
    project_ids = [link.project_id for link in links]
    if not project_ids:
        return []
    return list(
        session.exec(
            select(Project).where(Project.tenant_slug == tenant_slug, Project.id.in_(project_ids))
        ).all()  # type: ignore[union-attr]
    )


def _portfolio_to_public(
    session: Session,
    portfolio: Portfolio,
    tenant_slug: str,
    *,
    projects: list[Project] | None = None,
) -> PortfolioPublic:
    resolved_projects = (
        projects
        if projects is not None
        else _resolve_portfolio_projects(session, portfolio, tenant_slug)
    )
    return PortfolioPublic(
        id=portfolio.id,  # type: ignore[arg-type]
        tenant_slug=portfolio.tenant_slug,
        key=portfolio.key,
        name=portfolio.name,
        description=portfolio.description,
        parent_id=portfolio.parent_id,
        selection_mode=portfolio.selection_mode,
        selection_value=portfolio.selection_value,
        azure_devops_org=portfolio.azure_devops_org,
        project_count=len(resolved_projects),
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
    )


def _get_portfolio_by_id(session: Session, tenant_slug: str, portfolio_id: int) -> Portfolio | None:
    return session.exec(
        select(Portfolio).where(Portfolio.tenant_slug == tenant_slug, Portfolio.id == portfolio_id)
    ).first()


def _validate_portfolio_parent(
    session: Session,
    *,
    tenant_slug: str,
    parent_id: int | None,
    portfolio_id: int | None = None,
) -> None:
    if parent_id is None:
        return

    parent = _get_portfolio_by_id(session, tenant_slug, parent_id)
    if parent is None:
        raise HTTPException(status_code=400, detail="Parent portfolio was not found")

    if portfolio_id is None:
        return

    if parent_id == portfolio_id:
        raise HTTPException(status_code=400, detail="A portfolio cannot be its own parent")

    seen: set[int] = set()
    current = parent
    while current is not None:
        if current.id == portfolio_id:
            raise HTTPException(
                status_code=400,
                detail="Portfolio parent would create a circular hierarchy",
            )
        if current.parent_id is None or current.id in seen:
            break
        seen.add(current.id)
        current = _get_portfolio_by_id(session, tenant_slug, current.parent_id)


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


@router.post("/projects/", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ProjectPublic:
    """Create a new project."""

    existing = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == payload.key
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Project key '{payload.key}' already exists")

    _validate_repo_credential_source(
        session,
        tenant_slug=principal.tenant_slug,
        scm_connection_id=payload.scm_connection_id,
        github_installation_id=payload.github_installation_id,
    )
    repo_urls = _validated_project_repo_urls(payload.repos)

    project = Project(
        tenant_slug=principal.tenant_slug,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
        default_branch=payload.default_branch,
        quality_gate_policy_id=payload.quality_gate_policy_id,
        azure_devops_project=payload.azure_devops_project,
    )
    session.add(project)
    session.flush()

    for repo_url in repo_urls:
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo=repo_url,
                scm_connection_id=payload.scm_connection_id,
                github_installation_id=payload.github_installation_id,
            )
        )
    session.flush()
    for repo_url in repo_urls:
        _backfill_unassigned_scans_for_repo(
            session,
            tenant_slug=principal.tenant_slug,
            repo=repo_url,
            project_id=project.id,  # type: ignore[arg-type]
        )

    session.flush()
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="project.created",
        entity_type="project",
        entity_id=str(project.id),
        details=payload.model_dump(),
    )
    session.commit()
    session.refresh(project)
    return _project_to_public(session, project)


@router.get("/projects/", response_model=list[ProjectPublic])
def list_projects(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("project:read")),
) -> list[ProjectPublic]:
    """List all projects for the current tenant."""

    projects = session.exec(
        select(Project).where(Project.tenant_slug == principal.tenant_slug)
    ).all()
    return [_project_to_public(session, p) for p in projects]


@router.get("/projects/{project_key}", response_model=ProjectAggregateMetrics)
def get_project(
    project_key: str,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("project:read")),
) -> ProjectAggregateMetrics:
    """Get project details with aggregate metrics."""

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    repos = _project_repos(session, project.id)  # type: ignore[arg-type]
    return _compute_project_metrics(session, project, repos, principal.tenant_slug)


@router.patch("/projects/{project_key}", response_model=ProjectPublic)
def update_project(
    project_key: str,
    payload: ProjectUpdate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ProjectPublic:
    """Update project metadata."""

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    project.updated_at = datetime.now(UTC)
    session.add(project)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="project.updated",
        entity_type="project",
        entity_id=str(project.id),
        details=updates,
    )
    session.commit()
    session.refresh(project)
    return _project_to_public(session, project)


@router.delete("/projects/{project_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_key: str,
    delete_scans: bool = Query(default=False),
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Delete a project. Optionally delete associated scans too."""

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    _delete_project_record(
        session,
        project=project,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        project_identifier=project_key,
        delete_scans=delete_scans,
    )


@router.delete("/projects/by-id/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_by_id(
    project_id: int,
    delete_scans: bool = Query(default=False),
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Delete a project by ID. Useful for repairing invalid legacy project keys."""

    project = _get_tenant_project_by_id(session, principal.tenant_slug, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    _delete_project_record(
        session,
        project=project,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        project_identifier=str(project_id),
        delete_scans=delete_scans,
    )


@router.post("/projects/{project_key}/repos", response_model=ProjectPublic)
def add_project_repos(
    project_key: str,
    payload: ProjectRepoAdd,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ProjectPublic:
    """Add repositories to a project."""

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    _validate_repo_credential_source(
        session,
        tenant_slug=principal.tenant_slug,
        scm_connection_id=payload.scm_connection_id,
        github_installation_id=payload.github_installation_id,
    )
    repo_urls = _validated_project_repo_urls(payload.repos)

    existing_links = {
        link.repo: link
        for link in session.exec(
            select(ProjectRepository).where(ProjectRepository.project_id == project.id)
        ).all()
    }
    existing_repos = set(existing_links)
    for repo_url in repo_urls:
        link = existing_links.get(repo_url)
        if link is None:
            session.add(
                ProjectRepository(
                    project_id=project.id,
                    repo=repo_url,
                    scm_connection_id=payload.scm_connection_id,
                    github_installation_id=payload.github_installation_id,
                )
            )
            continue
        if (
            payload.scm_connection_id is not None
            and link.scm_connection_id != payload.scm_connection_id
        ):
            link.scm_connection_id = payload.scm_connection_id
            link.github_installation_id = None
            session.add(link)
        if (
            payload.github_installation_id is not None
            and link.github_installation_id != payload.github_installation_id
        ):
            link.github_installation_id = payload.github_installation_id
            link.scm_connection_id = None
            session.add(link)
    session.flush()
    for repo_url in repo_urls:
        if repo_url in existing_repos:
            continue
        _backfill_unassigned_scans_for_repo(
            session,
            tenant_slug=principal.tenant_slug,
            repo=repo_url,
            project_id=project.id,  # type: ignore[arg-type]
        )
    session.commit()
    session.refresh(project)
    return _project_to_public(session, project)


@router.delete(
    "/projects/{project_key}/repos",
    response_model=ProjectPublic,
)
def remove_project_repo(
    project_key: str,
    repo: str = Query(..., description="Repository URL to remove"),
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ProjectPublic:
    """Remove a repository from a project."""

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    link = session.exec(
        select(ProjectRepository).where(
            ProjectRepository.project_id == project.id,
            ProjectRepository.repo == repo,
        )
    ).first()
    if link:
        for scan in session.exec(
            select(Scan).where(
                Scan.tenant_slug == principal.tenant_slug,
                Scan.project_id == project.id,
                Scan.repo == repo,
            )
        ).all():
            scan.project_id = None
            session.add(scan)
        session.delete(link)
        session.commit()
    session.refresh(project)
    return _project_to_public(session, project)


# ---------------------------------------------------------------------------
# Portfolio endpoints
# ---------------------------------------------------------------------------


@router.post("/portfolios/", response_model=PortfolioPublic, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> PortfolioPublic:
    """Create a new portfolio."""

    existing = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == payload.key
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Portfolio key '{payload.key}' already exists")

    _validate_portfolio_parent(
        session,
        tenant_slug=principal.tenant_slug,
        parent_id=payload.parent_id,
    )

    portfolio = Portfolio(
        tenant_slug=principal.tenant_slug,
        **payload.model_dump(),
    )
    session.add(portfolio)
    session.flush()
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="portfolio.created",
        entity_type="portfolio",
        entity_id=str(portfolio.id),
        details=payload.model_dump(),
    )
    session.commit()
    session.refresh(portfolio)
    return _portfolio_to_public(session, portfolio, principal.tenant_slug, projects=[])


@router.get("/portfolios/", response_model=list[PortfolioPublic])
def list_portfolios(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("project:read")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> list[PortfolioPublic]:
    """List all portfolios for the current tenant."""

    portfolios = session.exec(
        select(Portfolio).where(Portfolio.tenant_slug == principal.tenant_slug)
    ).all()
    return [_portfolio_to_public(session, p, principal.tenant_slug) for p in portfolios]


@router.get("/portfolios/{portfolio_key}", response_model=PortfolioDetail)
def get_portfolio(
    portfolio_key: str,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("project:read")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> PortfolioDetail:
    """Get portfolio with aggregate metrics."""

    portfolio = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == portfolio_key
        )
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    projects = _resolve_portfolio_projects(session, portfolio, principal.tenant_slug)
    project_metrics = []
    total_findings = 0
    critical_findings = 0
    gates_evaluated = 0
    gates_passed = 0

    for project in projects:
        repos = _project_repos(session, project.id)  # type: ignore[arg-type]
        metrics = _compute_project_metrics(session, project, repos, principal.tenant_slug)
        project_metrics.append(metrics)
        total_findings += metrics.total_findings
        critical_findings += metrics.critical_findings
        if metrics.quality_gate_passed is not None:
            gates_evaluated += 1
            if metrics.quality_gate_passed:
                gates_passed += 1

    gate_pct = (gates_passed / gates_evaluated * 100) if gates_evaluated else None

    child_portfolios = session.exec(
        select(Portfolio).where(
            Portfolio.parent_id == portfolio.id,
            Portfolio.tenant_slug == principal.tenant_slug,
        )
    ).all()
    child_publics = [
        _portfolio_to_public(session, child, principal.tenant_slug) for child in child_portfolios
    ]

    return PortfolioDetail(
        **portfolio.model_dump(exclude={"project_links", "children"}),
        projects=project_metrics,
        children=child_publics,
        total_findings=total_findings,
        critical_findings=critical_findings,
        quality_gate_passed_pct=gate_pct,
    )


@router.patch("/portfolios/{portfolio_key}", response_model=PortfolioPublic)
def update_portfolio(
    portfolio_key: str,
    payload: PortfolioUpdate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> PortfolioPublic:
    """Update portfolio metadata or selection rules."""

    portfolio = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == portfolio_key
        )
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    updates = payload.model_dump(exclude_unset=True)
    if "parent_id" in updates:
        _validate_portfolio_parent(
            session,
            tenant_slug=principal.tenant_slug,
            parent_id=updates["parent_id"],
            portfolio_id=portfolio.id,
        )
    for field, value in updates.items():
        setattr(portfolio, field, value)
    portfolio.updated_at = datetime.now(UTC)
    session.add(portfolio)
    projects = _resolve_portfolio_projects(session, portfolio, principal.tenant_slug)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="portfolio.updated",
        entity_type="portfolio",
        entity_id=str(portfolio.id),
        details=updates,
    )
    session.commit()
    session.refresh(portfolio)
    return _portfolio_to_public(session, portfolio, principal.tenant_slug, projects=projects)


@router.delete("/portfolios/{portfolio_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_key: str,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> None:
    """Delete a portfolio."""

    portfolio = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == portfolio_key
        )
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    for link in session.exec(
        select(PortfolioProject).where(PortfolioProject.portfolio_id == portfolio.id)
    ).all():
        session.delete(link)

    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="portfolio.deleted",
        entity_type="portfolio",
        entity_id=str(portfolio.id),
        details={"key": portfolio_key},
    )
    session.delete(portfolio)
    session.commit()


@router.post("/portfolios/{portfolio_key}/projects", response_model=PortfolioPublic)
def add_portfolio_projects(
    portfolio_key: str,
    payload: PortfolioProjectAdd,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> PortfolioPublic:
    """Add projects to a portfolio (manual mode)."""

    portfolio = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == portfolio_key
        )
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if portfolio.selection_mode != SelectionMode.MANUAL:
        raise HTTPException(
            status_code=400,
            detail="Can only manually add projects to portfolios with 'manual' selection mode",
        )

    existing_links = session.exec(
        select(PortfolioProject).where(PortfolioProject.portfolio_id == portfolio.id)
    ).all()
    existing_project_ids = {link.project_id for link in existing_links}

    for project_key in payload.project_keys:
        project = session.exec(
            select(Project).where(
                Project.tenant_slug == principal.tenant_slug, Project.key == project_key
            )
        ).first()
        if project and project.id not in existing_project_ids:
            session.add(PortfolioProject(portfolio_id=portfolio.id, project_id=project.id))

    session.commit()
    session.refresh(portfolio)

    projects = _resolve_portfolio_projects(session, portfolio, principal.tenant_slug)
    return _portfolio_to_public(session, portfolio, principal.tenant_slug, projects=projects)


@router.delete("/portfolios/{portfolio_key}/projects/{project_key}")
def remove_portfolio_project(
    portfolio_key: str,
    project_key: str,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.PORTFOLIOS)),
) -> PortfolioPublic:
    """Remove a project from a portfolio."""

    portfolio = session.exec(
        select(Portfolio).where(
            Portfolio.tenant_slug == principal.tenant_slug, Portfolio.key == portfolio_key
        )
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug, Project.key == project_key
        )
    ).first()
    if project:
        link = session.exec(
            select(PortfolioProject).where(
                PortfolioProject.portfolio_id == portfolio.id,
                PortfolioProject.project_id == project.id,
            )
        ).first()
        if link:
            session.delete(link)
            session.commit()

    session.refresh(portfolio)
    projects = _resolve_portfolio_projects(session, portfolio, principal.tenant_slug)
    return _portfolio_to_public(session, portfolio, principal.tenant_slug, projects=projects)
