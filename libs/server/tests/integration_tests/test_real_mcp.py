#!/usr/bin/env python3
"""Test with a real MCP server."""

import asyncio
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
mcp_prefix_tools = true

[[mcp_servers]]
name = "test_mcp"
transport = "stdio"
command = "python"
args = ["/Users/isaachershenson/Documents/langchain-tool-server/.conductor/mcp-server-support/libs/server/test_mcp_server.py"]
"""
    (test_dir / "toolkit.toml").write_text(toolkit_toml)

    try:
        # Load the server with MCP support
        logger.info("Loading toolkit with MCP server...")
        server = await Server.afrom_toolkit(str(test_dir), enable_mcp=False)

        logger.info(
            f"\nSuccessfully loaded server with {len(server.tool_handler.catalog)} tools:"
        )
        for tool_name, tool_info in server.tool_handler.catalog.items():
            logger.info(
                f"  - {tool_name}: {tool_info.get('description', 'No description')}"
            )

        # Test calling a native tool
        logger.info("\nTesting native tool...")
        native_request = {
            "tool_id": "native_echo",
            "input": {"text": "Hello from native!"},
        }
        native_result = await server.tool_handler.call_tool(native_request, None)
        logger.info(f"Native tool result: {native_result}")

        # Test calling an MCP tool
        logger.info("\nTesting MCP tool...")
        if "test_mcp.mcp_add" in server.tool_handler.catalog:
            mcp_request = {"tool_id": "test_mcp.mcp_add", "input": {"x": 5, "y": 3}}
            mcp_result = await server.tool_handler.call_tool(mcp_request, None)
            logger.info(f"MCP tool result: {mcp_result}")

        if "test_mcp.mcp_greet" in server.tool_handler.catalog:
            greet_request = {
                "tool_id": "test_mcp.mcp_greet",
                "input": {"name": "LangChain"},
            }
            greet_result = await server.tool_handler.call_tool(greet_request, None)
            logger.info(f"MCP greet result: {greet_result}")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
