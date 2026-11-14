from __future__ import annotations

import asyncio
import json

import anyio
import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from vigilweave_mcp.server import create_server
from vigilweave_mcp.tools import register_tools


class StubClient:
    async def close(self) -> None:
        pass

    async def list_projects(self):
        return []

    async def search_scans(self, **kwargs):
        return []

    async def get_scan(self, scan_id):
        return {"id": scan_id, "status": "failed", "error": "scan worker failed"}

    async def get_finding_stats(self, scan_id):
        return {}

    async def get_quality_metrics(self, scan_id):
        return {}

    async def get_findings(self, scan_id, severity=None):
        return []

    async def create_scan(self, repo, scan_type="comprehensive", branch=None, project_key=None):
        return {"repo": repo, "project_key": project_key}

    async def get_repository_summary(self):
        return []

    async def get_capabilities(self):
        return {}

    async def triage_finding(self, *args, **kwargs):
        return {}

    async def list_policies(self):
        return []


def test_server_uses_fastmcp_and_registers_expected_tools() -> None:
    server = create_server(StubClient())

    assert isinstance(server, FastMCP)
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {
        "list_projects",
        "search_scans",
        "get_scan_detail",
        "get_quality_gate_status",
        "search_findings",
        "create_scan",
        "get_project_health",
        "get_capabilities",
        "triage_finding",
        "get_policy_status",
    } <= names


def test_server_closes_api_client_when_transport_ends() -> None:
    class ClosingClient(StubClient):
        closed = False

        async def close(self) -> None:
            self.closed = True

    client = ClosingClient()
    server = create_server(client)

    async def run_until_eof() -> None:
        incoming, read_stream = anyio.create_memory_object_stream(1)
        write_stream, outgoing = anyio.create_memory_object_stream(1)
        async with incoming, read_stream, write_stream, outgoing:
            await incoming.aclose()
            await server._mcp_server.run(
                read_stream,
                write_stream,
                server._mcp_server.create_initialization_options(),
            )

    asyncio.run(run_until_eof())
    assert client.closed


def test_quality_gate_status_exposes_failed_scan_diagnostics() -> None:
    class DiagnosticClient(StubClient):
        async def get_scan(self, scan_id):
            return {
                "id": scan_id,
                "status": "failed",
                "quality_gate_passed": False,
                "tool_executions": [
                    {"tool": "semgrep", "status": "failed", "stderr_summary": "runner unavailable"}
                ],
            }

    server = FastMCP("test")
    register_tools(server, DiagnosticClient())
    result = asyncio.run(server.call_tool("get_quality_gate_status", {"scan_id": 12}))
    payload = json.loads(result[0][0].text)

    assert payload["scan_status"] == "failed"
    assert payload["scan_error"] == "semgrep: runner unavailable"


def test_scan_detail_does_not_hide_non_missing_metrics_errors() -> None:
    class UnavailableClient(StubClient):
        async def get_quality_metrics(self, scan_id):
            request = httpx.Request("GET", "https://scanner.example.com/quality-metrics")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError(
                "503 Service Unavailable", request=request, response=response
            )

    server = FastMCP("test")
    register_tools(server, UnavailableClient())

    async def invoke() -> None:
        with pytest.raises(ToolError, match="503"):
            await server.call_tool("get_scan_detail", {"scan_id": 12})

    asyncio.run(invoke())


def test_scan_detail_ignores_only_a_missing_optional_metrics_endpoint() -> None:
    class OlderServerClient(StubClient):
        async def get_quality_metrics(self, scan_id):
            request = httpx.Request("GET", "https://scanner.example.com/quality-metrics")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("404 Not Found", request=request, response=response)

    server = FastMCP("test")
    register_tools(server, OlderServerClient())
    result = asyncio.run(server.call_tool("get_scan_detail", {"scan_id": 12}))

    assert result[1]["id"] == 12
    assert "quality_metrics" not in result[1]
