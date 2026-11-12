"""Prisma Cloud integration helpers."""

import hashlib
from typing import Any

import httpx
from sqlmodel import Session

from app.core.config import settings
from app.core.network_security import ensure_safe_outbound_url, sanitize_url
from app.models import (
    Finding,
    FindingSeverity,
    PrismaFindingPayload,
    PrismaImportRequest,
    PrismaSyncRequest,
    Scan,
    ScanStatus,
    ScanType,
    ToolExecution,
    ToolExecutionStatus,
)
from app.services.policy_engine import apply_waivers, evaluate_scan_policy, matching_policy


class PrismaCloudClient:
    """Small client wrapper for Prisma result sync."""

    def __init__(self, request: PrismaSyncRequest) -> None:
        self.request = request

    def fetch_findings(self) -> list[PrismaFindingPayload]:
        # Validate URL to prevent SSRF
        ensure_safe_outbound_url(
            self.request.api_url,
            allowed_hosts=[
                "api.prismacloud.io",
                "*.prismacloud.io",
                "app.prismacloud.io",
                "*.app.prismacloud.io",
            ],
            allow_http=settings.allow_http_outbound,
        )

        headers = dict(self.request.auth_headers)
        if self.request.access_key:
            headers.setdefault("x-prisma-access-key", self.request.access_key)
        if self.request.access_secret:
            headers.setdefault("x-prisma-access-secret", self.request.access_secret)

        response = httpx.get(
            self.request.api_url,
            headers=headers,
            timeout=settings.external_api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if self.request.results_path:
            findings_payload = _pluck_path(payload, self.request.results_path)
        else:
            findings_payload = payload
        if isinstance(findings_payload, list):
            items = findings_payload
        else:
            items = findings_payload.get("findings", [])
        return [PrismaFindingPayload.model_validate(item) for item in items]


def import_prisma_findings(
    session: Session,
    payload: PrismaImportRequest,
    *,
    tenant_slug: str,
    actor: str,
) -> Scan:
    """Persist Prisma findings as a completed scan."""

    scan = Scan(
        tenant_slug=tenant_slug,
        repo=payload.repo,
        branch=payload.branch,
        commit=payload.commit,
        source="prisma",
        scan_type=ScanType.SECURITY_ONLY,
        status=ScanStatus.RUNNING,
        include_quality_metrics=False,
        scan_metadata={"integration": "prisma", **payload.integration_metadata},
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    findings = [_map_prisma_finding(scan.id, item) for item in payload.findings]
    for finding in findings:
        session.add(finding)

    execution = ToolExecution(
        scan_id=scan.id,
        tool="prisma-cloud",
        status=ToolExecutionStatus.COMPLETED,
        findings_count=len(findings),
        stdout_summary="Prisma import completed",
        version="remote",
    )
    session.add(execution)
    session.commit()

    persisted = list(scan.findings)
    persisted, suppressed = apply_waivers(session, scan, persisted, actor=actor)
    for finding in persisted:
        session.add(finding)

    active = [finding for finding in persisted if not finding.is_suppressed]
    scan.total_findings = len(active)
    scan.critical_findings = sum(item.severity == FindingSeverity.CRITICAL for item in active)
    scan.high_findings = sum(item.severity == FindingSeverity.HIGH for item in active)
    scan.medium_findings = sum(item.severity == FindingSeverity.MEDIUM for item in active)
    scan.low_findings = sum(item.severity == FindingSeverity.LOW for item in active)
    scan.info_findings = sum(item.severity == FindingSeverity.INFO for item in active)
    scan.suppressed_findings = suppressed
    policy = evaluate_scan_policy(
        scan, matching_policy(session, scan.tenant_slug, scan.repo, scan.branch)
    )
    scan.quality_gate_passed = policy.passed
    scan.status = ScanStatus.COMPLETED
    scan.scan_metadata = {
        **(scan.scan_metadata or {}),
        "policy": policy.model_dump(),
    }
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def sync_prisma_findings(
    session: Session, request: PrismaSyncRequest, *, tenant_slug: str, actor: str
) -> Scan:
    """Fetch Prisma findings from a remote endpoint and import them."""

    client = PrismaCloudClient(request)
    findings = client.fetch_findings()
    return import_prisma_findings(
        session,
        PrismaImportRequest(
            repo=request.repo,
            branch=request.branch,
            commit=request.commit,
            tenant_slug=tenant_slug,
            findings=findings,
            integration_metadata={
                "source_url": sanitize_url(request.api_url),
                **request.integration_metadata,
            },
        ),
        tenant_slug=tenant_slug,
        actor=actor,
    )


def _map_prisma_finding(scan_id: int, payload: PrismaFindingPayload) -> Finding:
    fingerprint = (
        payload.fingerprint
        or hashlib.sha1(
            f"prisma:{payload.tool}:{payload.file_path}:{payload.line}:{payload.title}".encode(
                "utf-8"
            )
        ).hexdigest()
    )
    severity = _severity(payload.severity)
    return Finding(
        scan_id=scan_id,
        tool=payload.tool,
        scan_source="prisma",
        severity=severity,
        title=payload.title,
        message=payload.message,
        description=payload.description,
        category=payload.category,
        file_path=payload.file_path,
        line=payload.line,
        column=payload.column,
        rule_id=payload.rule_id,
        cwe_id=payload.cwe_id,
        owasp_category=payload.owasp_category,
        confidence=payload.confidence,
        fingerprint=fingerprint,
        tool_metadata=payload.raw,
    )


def _severity(value: str) -> FindingSeverity:
    normalized = value.strip().lower()
    if normalized in {"critical", "blocker"}:
        return FindingSeverity.CRITICAL
    if normalized in {"high", "error"}:
        return FindingSeverity.HIGH
    if normalized in {"medium", "moderate", "warning"}:
        return FindingSeverity.MEDIUM
    if normalized in {"low", "minor"}:
        return FindingSeverity.LOW
    return FindingSeverity.INFO


def _pluck_path(payload: Any, results_path: str | None) -> Any:
    if not results_path:
        return payload
    value = payload
    for part in results_path.split("."):
        if isinstance(value, dict):
            value = value.get(part, [])
        else:
            return []
    return value
