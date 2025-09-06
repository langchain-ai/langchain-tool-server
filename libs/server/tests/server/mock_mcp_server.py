#!/usr/bin/env python3
"""Simple test MCP server using FastMCP."""

from fastmcp import FastMCP

# Create server
mcp = FastMCP("Test MCP Server")


@mcp.tool()
def mcp_add(x: int, y: int) -> int:
    """Add two numbers via MCP."""
    return x + y


@mcp.tool()
def mcp_subtract(x: int, y: int) -> int:
    """Subtract y from x via MCP."""
    return x - y


@mcp.tool()
def mcp_greet(name: str) -> str:
    """Greet someone via MCP."""
    return f"Hello {name} from MCP server!"


if __name__ == "__main__":
    # Run as stdio server

    mcp.run(transport="stdio")
