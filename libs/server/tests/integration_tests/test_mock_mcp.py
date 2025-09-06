#!/usr/bin/env python3
"""Test MCP integration with mocked MCP server."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_mcp_with_mock():
    """Test MCP integration with a mocked MCP server."""
    from langchain_tool_server import Server

    # Create a temporary toolkit.toml
    test_dir = Path("/tmp/test_mock_mcp_toolkit")
    test_dir.mkdir(exist_ok=True)

    # Create the toolkit package
    toolkit_pkg = test_dir / "test_toolkit"
    toolkit_pkg.mkdir(exist_ok=True)

    # Create __init__.py with native tools
    init_content = '''
from langchain_tool_server import tool

@tool
def native_tool(text: str) -> str:
    """A native tool."""
    return f"Native: {text}"

TOOLS = [native_tool]
'''
    (toolkit_pkg / "__init__.py").write_text(init_content)

    # Create toolkit.toml with MCP server
    toolkit_toml = """
[toolkit]
name = "test_mock_mcp"
tools = "./test_toolkit/__init__.py:TOOLS"

[[mcp_servers]]
name = "mock_mcp"
transport = "stdio"
command = "python"
args = ["mock_server.py"]
"""
    (test_dir / "toolkit.toml").write_text(toolkit_toml)

    # Mock the MCP loading
    with patch(
        "langchain_tool_server.mcp_loader.MultiServerMCPClient"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Create mock session context manager
        mock_session = AsyncMock()
        mock_client.session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_client.session.return_value.__aexit__ = AsyncMock()

        # Create mock tools that will be returned
        from langchain_core.tools import StructuredTool

        def mock_add(x: int, y: int) -> int:
            """Add two numbers (mock MCP tool)."""
            return x + y

        def mock_greet(name: str) -> str:
            """Greet someone (mock MCP tool)."""
            return f"Hello {name}!"

        mock_tools = [
            StructuredTool.from_function(
                func=mock_add, name="add", description="Add two numbers (mock MCP tool)"
            ),
            StructuredTool.from_function(
                func=mock_greet,
                name="greet",
                description="Greet someone (mock MCP tool)",
            ),
        ]

        with patch("langchain_tool_server.mcp_loader.load_mcp_tools") as mock_load:
            mock_load.return_value = mock_tools

            # Load the server with MCP support
            server = await Server.afrom_toolkit(str(test_dir), enable_mcp=False)

            # Should have native tool + mocked MCP tools
            assert len(server.tool_handler.catalog) == 3, f"Expected 3 tools, got {len(server.tool_handler.catalog)}"

            # Verify tools are present
            assert "native_tool" in server.tool_handler.catalog, "native_tool not found"
            assert "mock_mcp.add" in server.tool_handler.catalog, "mock_mcp.add not found"
            assert "mock_mcp.greet" in server.tool_handler.catalog, "mock_mcp.greet not found"

            # Test native tool execution
            native_request = {"tool_id": "native_tool", "input": {"text": "test"}}
            native_result = await server.tool_handler.call_tool(native_request, None)
            assert native_result["success"] == True, f"native_tool failed: {native_result}"
            assert native_result["value"] == "Native: test", f"Expected 'Native: test', got {native_result['value']}"
            
            # Test mock MCP add tool
            mcp_request = {"tool_id": "mock_mcp.add", "input": {"x": 10, "y": 5}}
            mcp_result = await server.tool_handler.call_tool(mcp_request, None)
            assert mcp_result["success"] == True, f"mock_mcp.add failed: {mcp_result}"
            assert mcp_result["value"] == 15, f"Expected 15, got {mcp_result['value']}"
            
            # Test mock MCP greet tool
            greet_request = {"tool_id": "mock_mcp.greet", "input": {"name": "Test"}}
            greet_result = await server.tool_handler.call_tool(greet_request, None)
            assert greet_result["success"] == True, f"mock_mcp.greet failed: {greet_result}"
            assert greet_result["value"] == "Hello Test!", f"Expected 'Hello Test!', got {greet_result['value']}"
            
            # Verify tool descriptions
            native_tool_desc = server.tool_handler.catalog["native_tool"]["description"]
            assert native_tool_desc == "A native tool.", f"Wrong native tool description: {native_tool_desc}"
            
            mock_add_desc = server.tool_handler.catalog["mock_mcp.add"]["description"]
            assert mock_add_desc == "Add two numbers (mock MCP tool)", f"Wrong mock add description: {mock_add_desc}"
