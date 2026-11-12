"""Repository history and blame helpers."""

import shutil
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.network_security import is_safe_repo_url
from app.models import (
    RepositoryBlameRequest,
    RepositoryBlameResponse,
    RepositoryHistoryPoint,
    RepositoryHistoryResponse,
    Scan,
)
from app.services.git_utils import clone_repository, git_blame_line


def build_repository_history(
    session: Session, *, tenant_slug: str, repo: str, limit: int
) -> RepositoryHistoryResponse:
    """Build scan history series for one repository."""

    statement = (
        select(Scan)
        .where(Scan.tenant_slug == tenant_slug, Scan.repo == repo)
        .order_by(Scan.started_at.desc())
        .limit(max(1, limit))
    )
    scans = list(session.exec(statement).all())
    points = [
        RepositoryHistoryPoint(
            scan_id=scan.id or 0,
            started_at=scan.started_at,
            completed_at=scan.completed_at,
            status=scan.status,
            total_findings=scan.total_findings,
            critical_findings=scan.critical_findings,
            high_findings=scan.high_findings,
            medium_findings=scan.medium_findings,
            low_findings=scan.low_findings,
            info_findings=scan.info_findings,
            quality_score=scan.quality_score,
            quality_gate_passed=scan.quality_gate_passed,
        )
        for scan in scans
    ]
    points.reverse()
    total_scans = session.exec(
        select(func.count(Scan.id)).where(Scan.tenant_slug == tenant_slug, Scan.repo == repo)
    ).one()
    return RepositoryHistoryResponse(repo=repo, total_scans=int(total_scans), points=points)


def resolve_repository_blame(payload: RepositoryBlameRequest) -> RepositoryBlameResponse:
    """Resolve git blame details for a single file line."""

    if payload.line <= 0:
        raise ValueError("line must be greater than 0")
    if not is_safe_repo_url(payload.repo):
        raise ValueError(
            "Unsupported repository URL scheme. Only https:// and file:// are allowed."
        )
    if payload.repo.startswith("file://"):
        from app.core.config import settings

        if not settings.enable_file_repo_access:
            raise ValueError("Local file:// repository access is disabled")

    repo_path: Path | None = None
    try:
        repo_path = clone_repository(
            payload.repo, payload.branch, payload.commit, timeout_seconds=180
        )
        # Prevent path traversal: resolve path and ensure it's within repo
        target = (repo_path / payload.file_path).resolve()
        if not str(target).startswith(str(repo_path.resolve())):
            raise ValueError("Invalid file path: path traversal detected")
        if not target.exists():
            raise FileNotFoundError(payload.file_path)
        raw = git_blame_line(repo_path, payload.file_path, payload.line, timeout_seconds=120)
        return RepositoryBlameResponse(
            repo=payload.repo,
            file_path=payload.file_path,
            line=payload.line,
            commit=raw.get("commit", ""),
            author=raw.get("author", ""),
            author_email=raw.get("author_email", ""),
            authored_at_unix=int(raw.get("authored_at_unix", "0")),
            summary=raw.get("summary", ""),
        )
    finally:
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)
