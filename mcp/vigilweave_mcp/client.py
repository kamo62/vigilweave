"""Async HTTP client for the VigilWeave REST API."""

from __future__ import annotations

import os
from typing import Any, Self

import httpx


class VigilWeaveClient:
    """Thin wrapper around the VigilWeave v1 API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("VIGILWEAVE_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.environ.get("VIGILWEAVE_API_KEY", "")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        response = await self._client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    async def _patch(self, path: str, body: dict[str, Any]) -> Any:
        response = await self._client.patch(path, json=body)
        response.raise_for_status()
        return response.json()

    # -- Projects ----------------------------------------------------------------

    async def list_projects(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/projects/")

    # -- Scans -------------------------------------------------------------------

    async def search_scans(self, repo: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if repo:
            params["repo_filter"] = repo
        return await self._get("/api/v1/scans/", params=params)

    async def get_scan(self, scan_id: int) -> dict[str, Any]:
        return await self._get(f"/api/v1/scans/{scan_id}")

    async def create_scan(self, repo: str, scan_type: str = "comprehensive", branch: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"repo": repo, "scan_type": scan_type, "include_quality_metrics": True}
        if branch:
            body["branch"] = branch
        return await self._post("/api/v1/scans/", body)

    # -- Findings ----------------------------------------------------------------

    async def get_findings(self, scan_id: int, severity: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if severity:
            params["severity"] = severity
        return await self._get(f"/api/v1/scans/{scan_id}/findings", params=params)

    async def get_finding_stats(self, scan_id: int) -> dict[str, Any]:
        return await self._get(f"/api/v1/scans/{scan_id}/findings/stats")

    async def triage_finding(self, scan_id: int, finding_id: int, review_status: str, comment: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"review_status": review_status}
        if comment:
            body["comment"] = comment
        return await self._patch(f"/api/v1/scans/{scan_id}/findings/{finding_id}/triage", body)

    # -- Quality -----------------------------------------------------------------

    async def get_quality_metrics(self, scan_id: int) -> dict[str, Any]:
        return await self._get(f"/api/v1/scans/{scan_id}/quality-metrics")

    # -- System ------------------------------------------------------------------

    async def get_capabilities(self) -> dict[str, Any]:
        return await self._get("/api/v1/system/capabilities")

    # -- Policies ----------------------------------------------------------------

    async def list_policies(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/policies/")

    # -- Repositories ------------------------------------------------------------

    async def get_repository_summary(self) -> list[dict[str, Any]]:
        return await self._get("/api/v1/repositories/summary")
