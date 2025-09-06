#!/usr/bin/env python3
"""Test with a real MCP server."""

import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
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
args = ["./server/mock_mcp_server.py"]
"""
    (test_dir / "toolkit.toml").write_text(toolkit_toml)

    server = await Server.afrom_toolkit(str(test_dir), enable_mcp=False)

    for tool_name, tool_info in server.tool_handler.catalog.items():
        logger.info(
            f"  - {tool_name}: {tool_info.get('description', 'No description')}"
        )
    native_request = {
        "tool_id": "native_echo",
        "input": {"text": "Hello from native!"},
    }
    native_result = await server.tool_handler.call_tool(native_request, None)

    mcp_request = {"tool_id": "test_mcp.mcp_add", "input": {"x": 5, "y": 3}}
    mcp_result = await server.tool_handler.call_tool(mcp_request, None)
    print(f"MCP tool result: {mcp_result}")

    greet_request = {
        "tool_id": "test_mcp.mcp_greet",
        "input": {"name": "LangChain"},
    }
    greet_result = await server.tool_handler.call_tool(greet_request, None)
