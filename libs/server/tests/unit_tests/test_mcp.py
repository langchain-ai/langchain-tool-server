"""Test MCP functionality."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from langchain_tool_server import Server


async def test_simple():
    """Test MCP list tools endpoint."""
    # Get path to test toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "basic"

    # Create server from toolkit
    server = Server.from_toolkit(str(test_dir), enable_mcp=True)

    # Create test client
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        # Test MCP list tools endpoint
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data

        # Verify tools are listed
        tools = data["result"]["tools"]
        assert len(tools) == 2

        # Check hello tool
        hello_tool = next(t for t in tools if t["name"] == "hello")
        assert hello_tool["description"] == "Say hello."

        # Check add tool
        add_tool = next(t for t in tools if t["name"] == "add")
        assert add_tool["description"] == "Add two numbers."
        assert add_tool["inputSchema"]["properties"]["x"]["type"] == "integer"
        assert add_tool["inputSchema"]["properties"]["y"]["type"] == "integer"

        # Test executing the add tool
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "add", "arguments": {"x": 5, "y": 3}},
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert data["result"]["content"][0]["type"] == "text"
        assert data["result"]["content"][0]["text"] == "8"
