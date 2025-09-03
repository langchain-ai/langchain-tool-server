"""Test MCP functionality."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from langchain_tool_server import Server


async def test_simple():
    """Test MCP list tools endpoint."""
    # Get path to basic test toolkit (now has both regular and auth tools)
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
        assert len(tools) == 3

        # Check tools without auth
        hello_tool = next(t for t in tools if t["name"] == "hello")
        assert hello_tool["description"] == "Say hello."
        # Should not have auth fields
        assert "auth_provider" not in hello_tool
        assert "scopes" not in hello_tool

        add_tool = next(t for t in tools if t["name"] == "add")
        assert add_tool["description"] == "Add two numbers."
        # Should not have auth fields
        assert "auth_provider" not in add_tool
        assert "scopes" not in add_tool

        # Check tool with auth - verify auth info is included
        auth_tool = next(t for t in tools if t["name"] == "test_auth_tool")
        assert auth_tool["description"].startswith(
            "A test tool that requires authentication."
        )
        # Should have auth fields
        assert "auth_provider" in auth_tool
        assert "scopes" in auth_tool
        assert auth_tool["auth_provider"] == "test_provider"
        assert auth_tool["scopes"] == ["test_scope"]

        # Test executing a non-auth tool
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


async def test_invalid_params():
    """Test MCP tool call with invalid parameters returns proper error."""
    # Get path to test toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "basic"

    # Create server from toolkit
    server = Server.from_toolkit(str(test_dir), enable_mcp=True)

    # Create test client
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        # Test executing the add tool with wrong parameter names
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "add", "arguments": {"wrong": 5, "params": 3}},
            },
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # MCP should return error in result
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "error" in data
        assert "Invalid input" in data["error"]["message"]
