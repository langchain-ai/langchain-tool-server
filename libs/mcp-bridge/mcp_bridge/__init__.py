#!/usr/bin/env python

from __future__ import annotations

import json
from itertools import chain
from typing import Any, Sequence

from mcp import stdio_server
from mcp.server.lowlevel import Server as MCPServer
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from universal_tool_client import AsyncClient, get_async_client

SPLASH = """\
███╗   ███╗ ██████╗██████╗     ██████╗ ██████╗ ██╗██████╗  ██████╗ ███████╗
████╗ ████║██╔════╝██╔══██╗    ██╔══██╗██╔══██╗██║██╔══██╗██╔════╝ ██╔════╝
██╔████╔██║██║     ██████╔╝    ██████╔╝██████╔╝██║██║  ██║██║  ███╗█████╗
██║╚██╔╝██║██║     ██╔═══╝     ██╔══██╗██╔══██╗██║██║  ██║██║   ██║██╔══╝
██║ ╚═╝ ██║╚██████╗██║         ██████╔╝██║  ██║██║██████╔╝╚██████╔╝███████╗
╚═╝     ╚═╝ ╚═════╝╚═╝         ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝ ╚══════╝
"""


def _convert_to_content(
    result: Any,
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Convert a result to a sequence of content objects."""
    # This code comes directly from the FastMCP server.
    # Imported here as it is a private function.
    import pydantic_core
    from mcp.server.fastmcp.utilities.types import Image
    from mcp.types import EmbeddedResource, ImageContent, TextContent

    if result is None:
        return []

    if isinstance(result, (TextContent, ImageContent, EmbeddedResource)):
        return [result]

    if isinstance(result, Image):
        return [result.to_image_content()]

    if isinstance(result, (list, tuple)):
        return list(chain.from_iterable(_convert_to_content(item) for item in result))

    if not isinstance(result, str):
        try:
            result = json.dumps(pydantic_core.to_jsonable_python(result))
        except Exception:
            result = str(result)

    return [TextContent(type="text", text=result)]


async def create_mcp_server(
    client: AsyncClient, *, tools: list[str] | None = None
) -> MCPServer:
    """Create MCP server.

    Args:
        client: AsyncClient instance.
        tools: If provided, only the tools on this list will be available.
    """
    tools = tools or []
    for tool in tools:
        if "@" in tool:
            raise NotImplementedError("Tool versions are not yet supported.")

    server = MCPServer(name="OTC-MCP Bridge")
    server_tools = await client.tools.list()

    latest_tool = {}

    for tool in server_tools:
        version = tool["version"]
        # version is semver 3 tuple
        version_tuple = tuple(map(int, version.split(".")))
        current_version = latest_tool.get(tool["name"], (0, 0, 0))

        if version_tuple > current_version:
            latest_tool[tool["name"]] = version_tuple

    available_tools = [
        Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["input_schema"],
        )
        for tool in server_tools
        if tuple(map(int, tool["version"].split("."))) == latest_tool[tool["name"]]
    ]

    if tools:
        available_tools = [tool for tool in available_tools if tool["name"] in tools]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.
        return available_tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Call a tool by name with arguments."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.
        response = await client.tools.call(name, arguments)
        if not response["success"]:
            raise NotImplementedError(
                "Support for error messages is not yet implemented."
            )
        return _convert_to_content(response["value"])

    return server


async def run_server_stdio(server: MCPServer) -> None:
    """Run the MCP server."""
    print(SPLASH)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def main(
    *, url: str, headers: dict | None, tools: list[str] | None = None
) -> None:
    """Run the MCP server in stdio mode."""
    client = get_async_client(url=url, headers=headers)
    server = await create_mcp_server(client, tools=tools)
    await run_server_stdio(server)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
