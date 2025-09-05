#!/usr/bin/env python3
"""Test MCP integration with mocked MCP server."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
mcp_prefix_tools = true

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
            logger.info("Loading toolkit with mocked MCP server...")
            server = await Server.afrom_toolkit(str(test_dir), enable_mcp=False)

            logger.info(
                f"\nSuccessfully loaded server with {len(server.tool_handler.catalog)} tools:"
            )
            for tool_name, tool_info in server.tool_handler.catalog.items():
                logger.info(
                    f"  - {tool_name}: {tool_info.get('description', 'No description')}"
                )

            # Test native tool
            logger.info("\nTesting native tool...")
            native_request = {"tool_id": "native_tool", "input": {"text": "test"}}
            native_result = await server.tool_handler.call_tool(native_request, None)
            logger.info(f"Native result: {native_result}")

            # Test MCP tools
            logger.info("\nTesting MCP tools...")
            if "mock_mcp.add" in server.tool_handler.catalog:
                add_request = {"tool_id": "mock_mcp.add", "input": {"x": 10, "y": 20}}
                add_result = await server.tool_handler.call_tool(add_request, None)
                logger.info(f"Add result: {add_result}")

            if "mock_mcp.greet" in server.tool_handler.catalog:
                greet_request = {
                    "tool_id": "mock_mcp.greet",
                    "input": {"name": "World"},
                }
                greet_result = await server.tool_handler.call_tool(greet_request, None)
                logger.info(f"Greet result: {greet_result}")

            logger.info("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_with_mock())
