"""Test custom auth functionality."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from langchain_tool_server import Server


async def test_custom_auth_called():
    """Test that custom auth function is properly called across all endpoints."""
    # Get path to test auth toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "auth"
    
    # Create server from toolkit with MCP enabled
    server = Server.from_toolkit(str(test_dir), enable_mcp=True)
    
    # Import the auth module to access tracking variables
    # We need to import after server creation so the auth module is loaded
    import sys
    auth_module_name = None
    for name, module in sys.modules.items():
        if hasattr(module, 'AUTH_WAS_CALLED'):
            auth_module_name = name
            break
    
    assert auth_module_name is not None, "Auth module not found in sys.modules"
    auth_module = sys.modules[auth_module_name]
    
    # Reset tracking
    auth_module.reset_auth_tracking()
    assert not auth_module.AUTH_WAS_CALLED
    assert auth_module.AUTH_CALL_COUNT == 0
    
    # Create test client
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        
        # Test 1: HTTP REST API - List tools
        response = await client.get(
            "/tools",
            headers={"Authorization": "Bearer token1"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_WAS_CALLED
        assert auth_module.AUTH_CALL_COUNT == 1
        assert auth_module.LAST_AUTHORIZATION == "Bearer token1"
        
        # Verify tools are listed
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"
        
        # Test 2: HTTP REST API - Execute tool  
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "test_tool", "input": {"message": "hello"}}},
            headers={"Authorization": "Bearer token2"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_CALL_COUNT == 2
        assert auth_module.LAST_AUTHORIZATION == "Bearer token2"
        
        # Verify tool execution result
        result = response.json()
        assert result["success"] is True
        assert result["value"] == "Test tool says: hello"
        
        # Test 3: MCP - List tools
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Authorization": "Bearer token3"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_CALL_COUNT == 3
        assert auth_module.LAST_AUTHORIZATION == "Bearer token3"
        
        # Verify MCP tools list response
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        tools = data["result"]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"
        
        # Test 4: MCP - Execute tool
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "test_tool", "arguments": {"message": "world"}}
            },
            headers={"Authorization": "Bearer token4"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_CALL_COUNT == 4
        assert auth_module.LAST_AUTHORIZATION == "Bearer token4"
        
        # Verify MCP tool execution result
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert data["result"]["content"][0]["type"] == "text"
        assert data["result"]["content"][0]["text"] == "Test tool says: world"


async def test_custom_auth_headers_tracking():
    """Test that custom auth properly tracks headers."""
    test_dir = Path(__file__).parent.parent / "toolkits" / "auth"
    server = Server.from_toolkit(str(test_dir), enable_mcp=False)
    
    # Find auth module
    import sys
    auth_module = None
    for _, module in sys.modules.items():
        if hasattr(module, 'AUTH_WAS_CALLED'):
            auth_module = module
            break
    
    assert auth_module is not None
    auth_module.reset_auth_tracking()
    
    transport = ASGITransport(app=server, raise_app_exceptions=True)
    async with AsyncClient(base_url="http://localhost", transport=transport) as client:
        
        # Make request with custom headers
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "test_tool", "input": {"message": "test"}}},
            headers={
                "Authorization": "Bearer custom_token",
                "Custom-Header": "custom_value"
            }
        )
        
        assert response.status_code == 200
        assert auth_module.AUTH_WAS_CALLED
        
        # Check that headers were tracked (they may be modified by middleware)
        assert auth_module.LAST_HEADERS is not None
        # The exact headers format may vary due to middleware, but authorization should be tracked
        assert auth_module.LAST_AUTHORIZATION == "Bearer custom_token"
