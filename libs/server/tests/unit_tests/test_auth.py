"""Test custom auth functionality."""

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from langchain_tool_server import Server


async def test_custom_auth_called():
    """Test that custom auth function is properly called and tracks requests."""
    # Get path to test auth toolkit
    test_dir = Path(__file__).parent.parent / "toolkits" / "auth"
    
    # Create server from toolkit
    server = Server.from_toolkit(str(test_dir), enable_mcp=False)
    
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
        
        # Test 1: Request without auth should call auth and fail
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "test_tool", "input": {"message": "hello"}}}
        )
        assert response.status_code == 401
        assert auth_module.AUTH_WAS_CALLED
        assert auth_module.AUTH_CALL_COUNT == 1
        assert auth_module.LAST_AUTHORIZATION is None
        
        # Reset for next test
        auth_module.reset_auth_tracking()
        
        # Test 2: Request with valid bearer token should call auth and succeed
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "test_tool", "input": {"message": "hello"}}},
            headers={"Authorization": "Bearer test123"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_WAS_CALLED
        assert auth_module.AUTH_CALL_COUNT == 1
        assert auth_module.LAST_AUTHORIZATION == "Bearer test123"
        
        # Verify the response contains the expected tool output
        result = response.json()
        assert result["success"] is True
        assert result["value"] == "Test tool says: hello"
        
        # Test 3: Another request should increment call count
        response = await client.post(
            "/tools/call",
            json={"request": {"tool_id": "test_tool", "input": {"message": "world"}}},
            headers={"Authorization": "Bearer another_token"}
        )
        assert response.status_code == 200
        assert auth_module.AUTH_CALL_COUNT == 2
        assert auth_module.LAST_AUTHORIZATION == "Bearer another_token"


async def test_custom_auth_headers_tracking():
    """Test that custom auth properly tracks headers."""
    test_dir = Path(__file__).parent.parent / "toolkits" / "auth"
    server = Server.from_toolkit(str(test_dir), enable_mcp=False)
    
    # Find auth module
    import sys
    auth_module = None
    for name, module in sys.modules.items():
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
