"""VigilWeave MCP server entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from vigilweave_mcp.client import VigilWeaveClient
from vigilweave_mcp.tools import register_tools


def create_server(client: VigilWeaveClient | None = None) -> FastMCP:
    """Create the VigilWeave FastMCP server and own its API client lifecycle."""

    api_client = client if client is not None else VigilWeaveClient()

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, object]]:
        try:
            yield {}
        finally:
            await api_client.close()

    server = FastMCP("vigilweave", lifespan=lifespan)
    register_tools(server, api_client)
    return server


def main() -> None:
    """Run the VigilWeave MCP server on stdio."""

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
