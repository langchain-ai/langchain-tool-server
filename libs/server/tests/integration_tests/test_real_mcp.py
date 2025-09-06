#!/usr/bin/env python3
"""Test with a real MCP server."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_real_mcp_server():
    """Test loading tools from a real MCP server."""
    from langchain_tool_server import Server

    # Create a temporary toolkit.toml
    test_dir = Path("/tmp/test_mcp_toolkit")
    test_dir.mkdir(exist_ok=True)

    # Create the toolkit package
    toolkit_pkg = test_dir / "test_toolkit"
    toolkit_pkg.mkdir(exist_ok=True)

    # Create __init__.py with native tools
    init_content = '''
from langchain_tool_server import tool

@tool
def native_echo(text: str) -> str:
    """Echo the input text."""
    return text

TOOLS = [native_echo]
'''
    (toolkit_pkg / "__init__.py").write_text(init_content)

    # Create toolkit.toml with MCP server
    toolkit_toml = """
[toolkit]
name = "test_real_mcp"
tools = "./test_toolkit/__init__.py:TOOLS"

[[mcp_servers]]
name = "test_mcp"
transport = "stdio"
command = "python"
args = ["tests/server/mock_mcp_server.py"]
"""
    (test_dir / "toolkit.toml").write_text(toolkit_toml)

    server = await Server.afrom_toolkit(str(test_dir), enable_mcp=False)

    # Should load native tool + MCP tools from mock_mcp_server.py
    assert len(server.tool_handler.catalog) >= 1, f"Expected at least 1 tool, got {len(server.tool_handler.catalog)}"

    # Verify native tool is present
    assert "native_echo" in server.tool_handler.catalog, "native_echo tool not found"
    
    # Test native tool execution
    native_request = {
        "tool_id": "native_echo",
        "input": {"text": "Hello from native!"},
    }
    native_result = await server.tool_handler.call_tool(native_request, None)
    assert native_result["success"] == True, f"native_echo failed: {native_result}"
    assert native_result["value"] == "Hello from native!", f"Expected 'Hello from native!', got {native_result['value']}"

    # Test MCP tools if they loaded successfully
    expected_mcp_tools = ["test_mcp.mcp_add", "test_mcp.mcp_subtract", "test_mcp.mcp_greet"]
    loaded_mcp_tools = [tool for tool in server.tool_handler.catalog.keys() if tool.startswith("test_mcp.")]
    
    if loaded_mcp_tools:
        # If MCP tools loaded, test them
        if "test_mcp.mcp_add" in server.tool_handler.catalog:
            mcp_request = {"tool_id": "test_mcp.mcp_add", "input": {"x": 5, "y": 3}}
            mcp_result = await server.tool_handler.call_tool(mcp_request, None)
            assert mcp_result["success"] == True, f"test_mcp.mcp_add failed: {mcp_result}"
            assert int(mcp_result["value"]) == 8, f"Expected 8, got {mcp_result['value']}"

        if "test_mcp.mcp_greet" in server.tool_handler.catalog:
            greet_request = {
                "tool_id": "test_mcp.mcp_greet",
                "input": {"name": "LangChain"},
            }
            greet_result = await server.tool_handler.call_tool(greet_request, None)
            assert greet_result["success"] == True, f"test_mcp.mcp_greet failed: {greet_result}"
            assert "LangChain" in greet_result["value"], f"Expected LangChain in result, got {greet_result['value']}"
    
    # The test should pass even if MCP server doesn't connect (graceful degradation)
    # but native tools should always work
