from __future__ import annotations

import json
from itertools import chain
from typing import TYPE_CHECKING, Any, Sequence

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from universal_tool_server.tools import CallToolRequest, ToolHandler

if TYPE_CHECKING:
    from mcp.types import EmbeddedResource, ImageContent, TextContent

MCP_APP_PREFIX = "/mcp"


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


def create_mcp_app(tool_handler: ToolHandler) -> Starlette:
    """Create a Starlette app for an MCP server."""
    from mcp.server.lowlevel import Server as MCPServer
    from mcp.server.sse import SseServerTransport
    from mcp.types import Tool

    sse = SseServerTransport(f"{MCP_APP_PREFIX}/messages/")
    server = MCPServer(name="MCP Server")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.

        tools = []

        for tool in await tool_handler.list_tools(request=None):
            # MCP has no concept of tool versions, so we'll only
            # return the latest version.
            if tool_handler.latest_version[tool["name"]]["id"] != tool["id"]:
                continue

            tools.append(
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["input_schema"],
                )
            )

        return tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Call a tool by name with arguments."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.
        call_tool_request: CallToolRequest = {
            "tool_id": name,
            "input": arguments,
        }
        result = await tool_handler.call_tool(call_tool_request, request=None)
        return _convert_to_content(result)

    async def handle_sse(request: Request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )
    return starlette_app
