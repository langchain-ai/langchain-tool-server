"""Test toolkit for auth functionality."""
from langchain_tool_server import tool

@tool
def test_tool(message: str) -> str:
    """A simple test tool.
    
    Args:
        message: A message to echo back
        
    Returns:
        The message with a prefix
    """
    return f"Test tool says: {message}"

TOOLS = [test_tool]