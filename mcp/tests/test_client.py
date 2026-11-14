from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from vigilweave_mcp.client import VigilWeaveClient


def test_create_scan_sends_optional_tenant_and_project_key_without_empty_auth() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"id": 12})

    async def run() -> None:
        client = VigilWeaveClient(
            "https://scanner.example.com",
            api_key="",
            tenant="acme",
            transport=httpx.MockTransport(handler),
        )
        try:
            await client.create_scan("https://github.com/acme/app.git", project_key="APP")
        finally:
            await client.close()

    asyncio.run(run())

    request = captured[0]
    assert request.headers["X-VigilWeave-Tenant"] == "acme"
    assert "authorization" not in request.headers
    assert json.loads(request.content) == {
        "repo": "https://github.com/acme/app.git",
        "scan_type": "comprehensive",
        "include_quality_metrics": True,
        "project_key": "APP",
    }


def test_api_errors_are_not_hidden() -> None:
    async def run() -> None:
        client = VigilWeaveClient(
            "https://scanner.example.com",
            api_key="vw_test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503, json={"detail": "unavailable"})
            ),
        )
        try:
            with pytest.raises(httpx.HTTPStatusError, match="503"):
                await client.get_scan(12)
        finally:
            await client.close()

    asyncio.run(run())
