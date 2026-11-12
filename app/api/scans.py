"""Scan and repository endpoints."""

import csv
import logging
from datetime import UTC, datetime
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import Feature, require_feature
from app.core.network_security import is_safe_repo_url
from app.core.rate_limiter import (
    CSV_EXPORT_RATE_LIMIT,
    PDF_EXPORT_RATE_LIMIT,
    check_rate_limit,
)
from app.core.security import require_scope
from app.models import (
    FileMetrics,
    Finding,
    FindingPublic,
    FindingSeverity,
    FindingStats,
    FindingTriageRequest,
    QualityMetricsResponse,
    RepositorySummary,
    ReviewStatus,
    Scan,
    ScanAssignmentStatus,
    ScanCreate,
    ScanPublic,
    ToolExecution,
    ToolExecutionPublic,
)
from app.models.project import Project
from app.services.policy_engine import write_audit_event
from app.services.project_mapping import get_project_repo_link
from app.services.report_generator import generate_scan_report_pdf
from app.services.sarif_export import export_scan_to_sarif
from app.services.scanner import execute_scan
from app.tasks.scan_tasks import run_scan

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_tenant_scan(session: Session, scan_id: int, tenant_slug: str) -> Scan:
    scan = session.get(Scan, scan_id)
    if scan is None or scan.tenant_slug != tenant_slug:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _scan_to_public(session: Session, scan: Scan) -> ScanPublic:
    """Serialize a scan with derived project metadata."""

    project_key: str | None = None
    if scan.project_id is not None:
        project = session.get(Project, scan.project_id)
        if project is not None and project.tenant_slug == scan.tenant_slug:
            project_key = project.key

    tool_executions = list(
        session.exec(
            select(ToolExecution)
            .where(ToolExecution.scan_id == scan.id)
            .order_by(ToolExecution.id.asc())
        ).all()
    )

    return ScanPublic(
        **scan.model_dump(),
        project_key=project_key,
        assignment_status=(
            ScanAssignmentStatus.ASSIGNED
            if scan.project_id is not None and project_key is not None
            else ScanAssignmentStatus.UNASSIGNED
        ),
        tool_executions=[
            ToolExecutionPublic(**execution.model_dump()) for execution in tool_executions
        ],
    )


def _resolve_scm_connection_for_repo(
    session: Session,
    *,
    repo: str,
    tenant_slug: str,
    project_key: str | None,
) -> tuple[Project | None, int | None, dict[str, Any] | None]:
    """Resolve explicit project ownership and SCM credentials for a new scan."""

    if not project_key:
        return None, None, None

    project, project_repo = get_project_repo_link(
        session,
        tenant_slug=tenant_slug,
        project_key=project_key,
        repo=repo,
    )
    github_metadata = None
    if project_repo.github_installation_id is not None:
        github_metadata = {"installation_id": project_repo.github_installation_id}
    return project, project_repo.scm_connection_id, github_metadata


def _filtered_finding_statement(
    scan_id: int,
    *,
    severity: list[FindingSeverity] | None = None,
    category: list[str] | None = None,
    tool: list[str] | None = None,
    review_status: list[ReviewStatus] | None = None,
    include_suppressed: bool = False,
):
    statement = select(Finding).where(Finding.scan_id == scan_id)
    if severity:
        statement = statement.where(Finding.severity.in_(severity))  # type: ignore[arg-type]
    if category:
        statement = statement.where(Finding.category.in_(category))  # type: ignore[arg-type]
    if tool:
        statement = statement.where(Finding.tool.in_(tool))  # type: ignore[arg-type]
    if review_status:
        statement = statement.where(
            Finding.review_status.in_([item.value for item in review_status])
        )
    if not include_suppressed:
        statement = statement.where(Finding.is_suppressed.is_(False))
    return statement.order_by(Finding.id.asc())


def _load_filtered_findings(
    session: Session,
    scan_id: int,
    *,
    severity: list[FindingSeverity] | None = None,
    category: list[str] | None = None,
    tool: list[str] | None = None,
    review_status: list[ReviewStatus] | None = None,
    include_suppressed: bool = False,
) -> list[Finding]:
    return list(
        session.exec(
            _filtered_finding_statement(
                scan_id,
                severity=severity,
                category=category,
                tool=tool,
                review_status=review_status,
                include_suppressed=include_suppressed,
            )
        ).all()
    )


def _serialize_findings_csv(findings: list[Finding]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "severity",
            "category",
            "tool",
            "title",
            "message",
            "review_status",
            "is_suppressed",
            "file_path",
            "line",
            "rule_id",
            "cwe_id",
            "owasp_category",
            "fingerprint",
            "suppression_reason",
            "reviewed_by",
            "reviewed_at",
        ]
    )
    for finding in findings:
        writer.writerow(
            [
                finding.id,
                finding.severity.value,
                finding.category,
                finding.tool,
                finding.title,
                finding.message,
                finding.review_status,
                finding.is_suppressed,
                finding.file_path or "",
                finding.line or "",
                finding.rule_id or "",
                finding.cwe_id or "",
                finding.owasp_category or "",
                finding.fingerprint,
                finding.suppression_reason or "",
                finding.reviewed_by or "",
                finding.reviewed_at.isoformat() if finding.reviewed_at else "",
            ]
        )
    return buffer.getvalue()


@router.post("/scans/", response_model=ScanPublic, status_code=status.HTTP_201_CREATED)
def create_scan(
    payload: ScanCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
) -> ScanPublic:
    """Create and queue a scan."""

    if not is_safe_repo_url(payload.repo):
        raise HTTPException(
            status_code=422,
            detail="Unsupported repository URL scheme. Only https:// and file:// are allowed.",
        )
    if payload.repo.startswith("file://") and not settings.enable_file_repo_access:
        raise HTTPException(status_code=422, detail="Local file:// repository access is disabled")

    project, scm_connection_id, github_metadata = _resolve_scm_connection_for_repo(
        session,
        repo=payload.repo,
        tenant_slug=principal.tenant_slug,
        project_key=payload.project_key,
    )

    scan = Scan(
        tenant_slug=principal.tenant_slug,
        project_id=project.id if project is not None else None,
        repo=payload.repo,
        branch=payload.branch,
        commit=payload.commit,
        source="native",
        scan_type=payload.scan_type,
        include_quality_metrics=payload.include_quality_metrics,
        scan_metadata={
            "requested_tools": payload.tools or [],
            "actor": principal.actor,
            "scm_connection_id": scm_connection_id,
            "github": github_metadata,
        },
    )
    session.add(scan)
    session.flush()
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="scan.created",
        entity_type="scan",
        entity_id=str(scan.id),
        details={"repo": scan.repo, "scan_type": str(scan.scan_type)},
    )
    session.commit()
    session.refresh(scan)
    if settings.celery_task_always_eager:
        execute_scan(session, scan.id)
    else:
        run_scan.delay(scan.id)
    session.refresh(scan)
    return _scan_to_public(session, scan)


@router.get("/scans/", response_model=list[ScanPublic])
def list_scans(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
    repo_filter: str | None = Query(default=None),
    offset: int = 0,
    limit: int = Query(
        default=settings.default_scan_list_limit, ge=1, le=settings.max_scan_list_limit
    ),
) -> list[ScanPublic]:
    """List scans ordered by most recent first."""

    statement = (
        select(Scan)
        .where(Scan.tenant_slug == principal.tenant_slug)
        .order_by(Scan.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if repo_filter:
        statement = statement.where(Scan.repo.contains(repo_filter))
    return [_scan_to_public(session, scan) for scan in session.exec(statement).all()]


@router.get("/scans/{scan_id}", response_model=ScanPublic)
def get_scan(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> ScanPublic:
    """Return a single scan."""

    return _scan_to_public(session, _get_tenant_scan(session, scan_id, principal.tenant_slug))


@router.get("/scans/{scan_id}/findings", response_model=list[FindingPublic])
def get_findings(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
    severity: list[FindingSeverity] | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    tool: list[str] | None = Query(default=None),
    review_status: list[ReviewStatus] | None = Query(default=None),
    include_suppressed: bool = Query(default=False),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(
        default=settings.default_findings_limit,
        ge=1,
        le=settings.max_findings_limit,
    ),
) -> list[Finding]:
    """Return findings for a scan."""

    _get_tenant_scan(session, scan_id, principal.tenant_slug)
    statement = (
        _filtered_finding_statement(
            scan_id,
            severity=severity,
            category=category,
            tool=tool,
            review_status=review_status,
            include_suppressed=include_suppressed,
        )
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


@router.get("/scans/{scan_id}/findings/stats", response_model=FindingStats)
def get_finding_stats(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> FindingStats:
    """Return aggregate finding statistics."""

    _get_tenant_scan(session, scan_id, principal.tenant_slug)
    findings = _load_filtered_findings(session, scan_id, include_suppressed=False)
    stats = FindingStats(total_findings=len(findings), by_category={}, by_tool={})
    for finding in findings:
        if finding.severity == FindingSeverity.CRITICAL:
            stats.critical_findings += 1
        elif finding.severity == FindingSeverity.HIGH:
            stats.high_findings += 1
        elif finding.severity == FindingSeverity.MEDIUM:
            stats.medium_findings += 1
        elif finding.severity == FindingSeverity.LOW:
            stats.low_findings += 1
        else:
            stats.info_findings += 1

        stats.by_category[finding.category] = stats.by_category.get(finding.category, 0) + 1
        stats.by_tool[finding.tool] = stats.by_tool.get(finding.tool, 0) + 1
    return stats


@router.get("/scans/{scan_id}/quality-metrics", response_model=QualityMetricsResponse)
def get_quality_metrics(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> QualityMetricsResponse:
    """Return quality metrics and persisted file-level measurements."""

    scan = _get_tenant_scan(session, scan_id, principal.tenant_slug)
    metrics = list(session.exec(select(FileMetrics).where(FileMetrics.scan_id == scan_id)).all())
    return QualityMetricsResponse(
        scan_id=scan_id,
        quality_score=scan.quality_score,
        quality_grade=scan.quality_grade,
        complexity_score=scan.complexity_score,
        maintainability_score=scan.maintainability_score,
        style_score=scan.style_score,
        avg_cyclomatic_complexity=scan.avg_cyclomatic_complexity,
        max_cyclomatic_complexity=scan.max_cyclomatic_complexity,
        duplication_percentage=scan.duplication_percentage,
        maintainability_index=scan.maintainability_index,
        technical_debt_minutes=scan.technical_debt_minutes,
        quality_issues=scan.quality_issues,
        style_issues=scan.style_issues,
        complexity_issues=scan.complexity_issues,
        files=metrics,
    )


@router.get("/scans/{scan_id}/sarif")
def get_sarif(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> dict:
    """Return SARIF for a scan."""

    _get_tenant_scan(session, scan_id, principal.tenant_slug)
    return export_scan_to_sarif(session, scan_id)


@router.get("/scans/{scan_id}/report/pdf")
def get_scan_report_pdf(
    scan_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
    _: object = Depends(require_feature(Feature.REPORTING)),
    severity: list[FindingSeverity] | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    tool: list[str] | None = Query(default=None),
    review_status: list[ReviewStatus] | None = Query(default=None),
    include_suppressed: bool = Query(default=False),
) -> Response:
    """Render an on-demand PDF report for a scan.

    Rate limited to 10 requests per minute per IP to prevent resource exhaustion.
    """
    check_rate_limit(request, PDF_EXPORT_RATE_LIMIT, resource_name="PDF export")

    scan = _get_tenant_scan(session, scan_id, principal.tenant_slug)
    findings = _load_filtered_findings(
        session,
        scan_id,
        severity=severity,
        category=category,
        tool=tool,
        review_status=review_status,
        include_suppressed=include_suppressed,
    )
    try:
        pdf_bytes = generate_scan_report_pdf(scan=scan, findings=findings)
    except Exception as exc:
        logger.error("PDF generation failed for scan %s: %s", scan_id, exc, exc_info=True)
        raise HTTPException(
            status_code=503, detail="PDF reporting is temporarily unavailable"
        ) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="scan-{scan_id}-report.pdf"',
        },
    )


@router.get("/scans/{scan_id}/findings/export")
def export_scan_findings(
    scan_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
    _: object = Depends(require_feature(Feature.REPORTING)),
    severity: list[FindingSeverity] | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    tool: list[str] | None = Query(default=None),
    review_status: list[ReviewStatus] | None = Query(default=None),
    include_suppressed: bool = Query(default=False),
) -> Response:
    """Export filtered findings for a scan as CSV.

    Rate limited to 30 requests per minute per IP to prevent resource exhaustion.
    """
    check_rate_limit(request, CSV_EXPORT_RATE_LIMIT, resource_name="CSV export")

    _get_tenant_scan(session, scan_id, principal.tenant_slug)
    findings = _load_filtered_findings(
        session,
        scan_id,
        severity=severity,
        category=category,
        tool=tool,
        review_status=review_status,
        include_suppressed=include_suppressed,
    )
    try:
        csv_content = _serialize_findings_csv(findings)
    except Exception as exc:
        logger.error("CSV export failed for scan %s: %s", scan_id, exc, exc_info=True)
        raise HTTPException(
            status_code=503, detail="CSV export is temporarily unavailable"
        ) from exc
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="scan-{scan_id}-findings.csv"',
        },
    )


@router.patch("/scans/{scan_id}/findings/{finding_id}/triage", response_model=FindingPublic)
def triage_finding(
    scan_id: int,
    finding_id: int,
    payload: FindingTriageRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
) -> Finding:
    """Update the triage / review status of a finding."""

    scan = _get_tenant_scan(session, scan_id, principal.tenant_slug)
    finding = session.get(Finding, finding_id)
    if finding is None or finding.scan_id != scan_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    finding.review_status = payload.review_status.value
    finding.reviewed_by = principal.actor
    finding.reviewed_at = datetime.now(UTC)
    session.add(finding)
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="finding.triaged",
        entity_type="finding",
        entity_id=str(finding.id),
        details={
            "scan_id": scan_id,
            "review_status": payload.review_status.value,
            "comment": payload.comment,
        },
    )
    session.commit()
    session.refresh(finding)
    return finding


class BulkTriageRequest(BaseModel):
    """Payload for bulk-triaging findings."""

    finding_ids: list[int] = Field(max_length=settings.max_bulk_triage_ids)
    review_status: ReviewStatus
    comment: str | None = None


class BulkTriageResponse(BaseModel):
    """Response for bulk triage."""

    updated: int
    skipped: int


@router.post(
    "/scans/{scan_id}/findings/bulk-triage",
    response_model=BulkTriageResponse,
)
def bulk_triage_findings(
    scan_id: int,
    payload: BulkTriageRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
    _: object = Depends(require_feature(Feature.BULK_TRIAGE)),
) -> BulkTriageResponse:
    """Update the triage status of multiple findings at once."""

    scan = _get_tenant_scan(session, scan_id, principal.tenant_slug)
    now = datetime.now(UTC)
    updated = 0
    for fid in payload.finding_ids:
        finding = session.get(Finding, fid)
        if finding is None or finding.scan_id != scan_id:
            continue
        finding.review_status = payload.review_status.value
        finding.reviewed_by = principal.actor
        finding.reviewed_at = now
        session.add(finding)
        updated += 1
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="finding.bulk_triaged",
        entity_type="finding",
        entity_id=f"scan:{scan_id}",
        details={
            "scan_id": scan_id,
            "count": updated,
            "review_status": payload.review_status.value,
            "comment": payload.comment,
        },
    )
    session.commit()
    return BulkTriageResponse(updated=updated, skipped=len(payload.finding_ids) - updated)


@router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    scan_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Delete a scan and all its findings, metrics, and tool executions."""

    scan = _get_tenant_scan(session, scan_id, principal.tenant_slug)
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="scan.deleted",
        entity_type="scan",
        entity_id=str(scan.id),
        details={"repo": scan.repo, "total_findings": scan.total_findings},
    )
    session.delete(scan)
    session.commit()


@router.get("/repositories/summary", response_model=list[RepositorySummary])
def get_repository_summary(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> list[RepositorySummary]:
    """Return latest summary per repository.

    Uses SQL GROUP BY with func.max() for efficient querying.
    Avoids loading all scans into memory (O(n) vs O(n²) complexity).
    """

    # Get the latest scan ID per repository using SQL aggregation
    latest_scan_subquery = (
        select(Scan.repo, func.max(Scan.id).label("latest_scan_id"))
        .where(Scan.tenant_slug == principal.tenant_slug)
        .group_by(Scan.repo)
        .subquery()
    )

    # Get count of scans per repository
    scan_counts = (
        select(Scan.repo, func.count(Scan.id).label("scan_count"))
        .where(Scan.tenant_slug == principal.tenant_slug)
        .group_by(Scan.repo)
        .subquery()
    )

    # Join with full scan data to get the latest scan details
    stmt = (
        select(Scan, scan_counts.c.scan_count)
        .join(
            latest_scan_subquery,
            (Scan.repo == latest_scan_subquery.c.repo)
            & (Scan.id == latest_scan_subquery.c.latest_scan_id),
        )
        .join(scan_counts, Scan.repo == scan_counts.c.repo)
        .where(Scan.tenant_slug == principal.tenant_slug)
    )

    results = session.exec(stmt).all()

    summaries: list[RepositorySummary] = []
    for scan, scan_count in results:
        summaries.append(
            RepositorySummary(
                repo=scan.repo,
                scans=scan_count,
                latest_scan_id=scan.id,
                latest_status=scan.status,
                quality_gate_passed=scan.quality_gate_passed,
                total_findings=scan.total_findings,
                quality_score=scan.quality_score,
            )
        )
    return summaries
