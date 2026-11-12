"""Helpers for resolving project and repository ownership."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.project import Project, ProjectRepository


def get_project_by_key(session: Session, tenant_slug: str, project_key: str) -> Project:
    """Load a tenant-scoped project by key."""

    project = session.exec(
        select(Project).where(Project.tenant_slug == tenant_slug, Project.key == project_key)
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_project_repo_link(
    session: Session,
    *,
    tenant_slug: str,
    project_key: str,
    repo: str,
) -> tuple[Project, ProjectRepository]:
    """Return an explicit project/repository link."""

    project = get_project_by_key(session, tenant_slug, project_key)
    link = session.exec(
        select(ProjectRepository).where(
            ProjectRepository.project_id == project.id,
            ProjectRepository.repo == repo,
        )
    ).first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository is not linked to the selected project",
        )
    return project, link


def resolve_webhook_project_link(
    session: Session,
    *,
    repo: str,
) -> tuple[Project, ProjectRepository] | None:
    """Resolve a webhook repo URL to exactly one stored project mapping."""

    results = list(
        session.exec(
            select(ProjectRepository, Project)
            .join(Project, ProjectRepository.project_id == Project.id)
            .where(ProjectRepository.repo == repo)
            .order_by(ProjectRepository.id.desc())
        ).all()
    )
    if not results:
        return None

    project_ids = {project.id for _, project in results}
    if len(project_ids) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository is linked to multiple projects and cannot be routed safely",
        )

    link, project = results[0]
    return project, link
