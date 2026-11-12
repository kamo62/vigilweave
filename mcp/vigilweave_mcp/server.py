"""VigilWeave MCP server entrypoint."""

from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server

from vigilweave_mcp.client import VigilWeaveClient
from vigilweave_mcp.tools import register_tools


def main() -> None:
    """Run the VigilWeave MCP server on stdio."""

    server = Server("vigilweave")
    client = VigilWeaveClient()
    register_tools(server, client)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            try:
                await server.run(read_stream, write_stream, server.create_initialization_options())
            finally:
                await client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
