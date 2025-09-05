"""Example toolkit with native tools and MCP server configuration."""

from langchain_tool_server import tool


@tool
def native_add(x: int, y: int) -> int:
    """Add two numbers using a native tool."""
    return x + y


@tool
def native_multiply(x: int, y: int) -> int:
    """Multiply two numbers using a native tool."""
    return x * y


# Export tools for the toolkit
TOOLS = [native_add, native_multiply]
