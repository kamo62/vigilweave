"""MCP tool definitions for VigilWeave."""

from __future__ import annotations

from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from vigilweave_mcp.client import VigilWeaveClient

_VALID_REVIEW_STATUSES = {"open", "acknowledged", "false_positive", "fixed", "wont_fix"}
_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low", "Info"}


def _format_failed_tool(execution: dict[str, Any]) -> str:
    tool = execution.get("tool", "unknown tool")
    detail = (
        execution.get("stderr_summary") or execution.get("stdout_summary") or "execution failed"
    )
    return f"{tool}: {detail}"


def register_tools(server: FastMCP, client: VigilWeaveClient) -> None:
    """Register all VigilWeave MCP tools on the server."""

    @server.tool()
    async def list_projects() -> list[dict[str, Any]]:
        """List all projects in VigilWeave."""
        return await client.list_projects()

    @server.tool()
    async def search_scans(repo: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Search scan history. Optionally filter by repository name."""
        limit = max(1, min(limit, 500))
        return await client.search_scans(repo=repo, limit=limit)

    @server.tool()
    async def get_scan_detail(scan_id: int) -> dict[str, Any]:
        """Get full details for a specific scan including quality metrics."""
        if scan_id <= 0:
            raise ValueError("scan_id must be a positive integer")
        scan = await client.get_scan(scan_id)
        try:
            quality = await client.get_quality_metrics(scan_id)
            scan["quality_metrics"] = quality
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
        return scan

    @server.tool()
    async def get_quality_gate_status(scan_id: int) -> dict[str, Any]:
        """Check whether a scan's quality gate passed or failed, with scores."""
        if scan_id <= 0:
            raise ValueError("scan_id must be a positive integer")
        scan = await client.get_scan(scan_id)
        stats = await client.get_finding_stats(scan_id)
        failed_tools = [
            execution
            for execution in scan.get("tool_executions", [])
            if execution.get("status") == "failed"
        ]
        scan_error = scan.get("error") or scan.get("error_message")
        metadata = scan.get("scan_metadata")
        if not scan_error and isinstance(metadata, dict):
            scan_error = metadata.get("error") or metadata.get("error_message")
        if not scan_error and failed_tools:
            scan_error = "; ".join(_format_failed_tool(execution) for execution in failed_tools)
        return {
            "scan_id": scan_id,
            "scan_status": scan.get("status"),
            "scan_error": scan_error,
            "failed_tools": failed_tools,
            "quality_gate_passed": scan.get("quality_gate_passed"),
            "quality_score": scan.get("quality_score"),
            "quality_grade": scan.get("quality_grade"),
            "findings": stats,
        }

    @server.tool()
    async def search_findings(scan_id: int, severity: str | None = None) -> list[dict[str, Any]]:
        """List findings for a scan, optionally filtered by severity.

        Valid severities: Critical, High, Medium, Low, Info.
        """
        if scan_id <= 0:
            raise ValueError("scan_id must be a positive integer")
        if severity and severity not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}")
        return await client.get_findings(scan_id, severity=severity)

    @server.tool()
    async def create_scan(
        repo: str,
        scan_type: str = "comprehensive",
        branch: str | None = None,
        project_key: str | None = None,
    ) -> dict[str, Any]:
        """Trigger a new VigilWeave scan for a repository."""
        if not repo or not repo.strip():
            raise ValueError("repo must be a non-empty string")
        if scan_type not in {"comprehensive", "fast", "security-only", "custom"}:
            raise ValueError("scan_type must be one of: comprehensive, fast, security-only, custom")
        return await client.create_scan(
            repo,
            scan_type=scan_type,
            branch=branch,
            project_key=project_key,
        )

    @server.tool()
    async def get_project_health() -> list[dict[str, Any]]:
        """Get an aggregate health view across all repositories."""
        return await client.get_repository_summary()

    @server.tool()
    async def get_capabilities() -> dict[str, Any]:
        """Return system capabilities including license tier and available features."""
        return await client.get_capabilities()

    @server.tool()
    async def triage_finding(
        scan_id: int,
        finding_id: int,
        review_status: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Update a finding's triage status.

        Valid statuses: open, acknowledged, false_positive, fixed, wont_fix.
        """
        if scan_id <= 0:
            raise ValueError("scan_id must be a positive integer")
        if finding_id <= 0:
            raise ValueError("finding_id must be a positive integer")
        if review_status not in _VALID_REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {sorted(_VALID_REVIEW_STATUSES)}")
        return await client.triage_finding(scan_id, finding_id, review_status, comment=comment)

    @server.tool()
    async def get_policy_status() -> list[dict[str, Any]]:
        """List all policy profiles configured in VigilWeave."""
        return await client.list_policies()
