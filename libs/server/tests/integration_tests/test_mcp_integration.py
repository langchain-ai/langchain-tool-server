#!/usr/bin/env python3
"""Test script for MCP server integration."""

import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_toolkit():
    """Test loading a toolkit with MCP servers configured."""
    from langchain_tool_server import Server

    # Test with the example MCP toolkit
    toolkit_path = Path(__file__).parent / "tests/toolkits/mcp_example"

    try:
        # Test sync method (should warn about MCP servers)
        logger.info("Testing sync from_toolkit...")
        sync_server = Server.from_toolkit(str(toolkit_path), enable_mcp=False)
        logger.info(
            f"Sync server created with {len(sync_server.tool_handler.catalog)} tools"
        )

        # Test async method (should load MCP servers)
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

    except Exception as e:
        logger.error(f"Error testing MCP toolkit: {e}")
        import traceback

        logger.error(traceback.format_exc())


async def test_basic_toolkit():
    """Test that existing toolkits still work."""
    from langchain_tool_server import Server

    # Test with the basic toolkit (no MCP servers)
    toolkit_path = Path(__file__).parent / "tests/toolkits/basic"

    try:
        # Both sync and async should work the same for non-MCP toolkits
        sync_server = Server.from_toolkit(str(toolkit_path))
        logger.info(
            f"Basic sync server created with {len(sync_server.tool_handler.catalog)} tools"
        )

        async_server = await Server.afrom_toolkit(str(toolkit_path))
        logger.info(
            f"Basic async server created with {len(async_server.tool_handler.catalog)} tools"
        )

    except Exception as e:
        logger.error(f"Error testing basic toolkit: {e}")


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Testing MCP Server Integration")
    logger.info("=" * 60)

    logger.info("\n1. Testing backward compatibility with basic toolkit:")
    await test_basic_toolkit()

    logger.info("\n2. Testing MCP server toolkit:")
    await test_mcp_toolkit()

    logger.info("\n" + "=" * 60)
    logger.info("Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
