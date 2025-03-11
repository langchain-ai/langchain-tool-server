"""Integration test to test the MCP server."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from mcp import ClientSession
from mcp.client.sse import sse_client


@asynccontextmanager
async def get_client(
    url: str, *, headers: dict | None = None
) -> AsyncGenerator[ClientSession, None]:
    async with sse_client(url=url, headers=headers) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            yield session


URL = os.environ.get("MCP_SSE_URL", "http://localhost:8131/mcp/sse")


async def test_list_tools() -> None:
    async with get_client(URL) as session:
        list_tool_result = await session.list_tools()
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
            for tool in list_tool_result.tools
        ]
        assert tools == [
            {
                "name": "echo",
                "description": "Echo a message.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                },
            },
            {
                "name": "add",
                "description": "Add two numbers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
            },
            {
                "name": "say_hello",
                "description": "Say hello.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]


async def test_call_tool() -> None:
    """Test calling a tool."""
    async with get_client(URL) as session:
        tool_call = await session.call_tool("echo", {"msg": "Hello"})
        assert tool_call.content[0].text == "Hello!"
