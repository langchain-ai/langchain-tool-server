#!/usr/bin/env python3
"""Test script for MCP server integration."""

import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_toolkit():
    """Test loading a toolkit with MCP servers configured."""
    from langchain_tool_server import Server

    # Test with the example MCP toolkit
    toolkit_path = Path(__file__).parent / "../toolkits/mcp_example"

    logger.info("Testing sync from_toolkit...")
    sync_server = Server.from_toolkit(str(toolkit_path), enable_mcp=False)
    logger.info(
        f"Sync server created with {len(sync_server.tool_handler.catalog)} tools"
    )

    logger.info("\nTesting async afrom_toolkit...")
    async_server = await Server.afrom_toolkit(str(toolkit_path), enable_mcp=False)
    logger.info(
        f"Async server created with {len(async_server.tool_handler.catalog)} tools"
    )

    # List loaded tools
    logger.info("\nLoaded tools:")
    for tool_name in async_server.tool_handler.catalog.keys():
        tool_info = async_server.tool_handler.catalog[tool_name]
        logger.info(
            f"  - {tool_name}: {tool_info.get('description', 'No description')}"
        )


async def test_basic_toolkit():
    """Test that existing toolkits still work."""
    from langchain_tool_server import Server

    # Test with the basic toolkit (no MCP servers)
    toolkit_path = Path(__file__).parent / "../toolkits/basic"

    sync_server = Server.from_toolkit(str(toolkit_path))
    logger.info(
        f"Basic sync server created with {len(sync_server.tool_handler.catalog)} tools"
    )

    async_server = await Server.afrom_toolkit(str(toolkit_path))
    logger.info(
        f"Basic async server created with {len(async_server.tool_handler.catalog)} tools"
    )