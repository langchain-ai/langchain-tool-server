#!/usr/bin/env python3
"""Math MCP server using stdio transport for testing."""

from fastmcp import FastMCP

# Create server
mcp = FastMCP("Math Server")


@mcp.tool()
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


@mcp.tool()
def subtract(x: int, y: int) -> int:
    """Subtract y from x."""
    return x - y


@mcp.tool()
def multiply(x: int, y: int) -> int:
    """Multiply two numbers."""
    return x * y


@mcp.tool()
def divide(x: int, y: int) -> float:
    """Divide x by y."""
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y


if __name__ == "__main__":
    # Run as stdio server (default transport)
    mcp.run(transport="stdio")