"""Test REST API functionality."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from langchain_tool_server import Server


async def test_simple():
    """Test REST API list tools and tool execution endpoints."""
    # Get path to test toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "basic"

    # Create server from toolkit (without MCP)
    server = Server.from_toolkit(str(test_dir), enable_mcp=False)

    # Create test client
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        # Test REST API list tools endpoint
        response = await client.get("/tools")

        assert response.status_code == 200
        tools = response.json()

        # Verify tools are listed
        assert len(tools) == 2

        # Check hello tool
        hello_tool = next(t for t in tools if t["name"] == "hello")
        assert hello_tool["description"] == "Say hello."

        # Check add tool
        add_tool = next(t for t in tools if t["name"] == "add")
        assert add_tool["description"] == "Add two numbers."
        assert add_tool["input_schema"]["properties"]["x"]["type"] == "integer"
        assert add_tool["input_schema"]["properties"]["y"]["type"] == "integer"

        # Test executing the add tool
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "add", "input": {"x": 5, "y": 3}}},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert "execution_id" in data
        assert data["value"] == 8


async def test_invalid_params():
    """Test REST API tool call with invalid parameters returns 400."""
    # Get path to test toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "basic"

    # Create server from toolkit (without MCP)
    server = Server.from_toolkit(str(test_dir), enable_mcp=False)

    # Create test client
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        # Test executing the add tool with wrong parameter names
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "add", "input": {"wrong": 5, "params": 3}}},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400
        data = response.json()

        # Should return error details
        assert "detail" in data
        assert "Invalid input" in data["detail"]
