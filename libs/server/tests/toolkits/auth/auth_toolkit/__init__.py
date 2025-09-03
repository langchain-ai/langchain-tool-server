"""Test toolkit for auth functionality."""

from langchain_tool_server import Context, tool


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


@tool(auth_provider="my_provider", scopes=["scopeA", "scopeB"])
def test_tool_with_auth_provider(context: Context, message: str) -> str:
    """A simple test tool that returns the context token.

    Args:
        context: Authentication context
        message: A message to echo back

    Returns:
        The context token and message
    """
    return f"Token: {context.token}, Message: {message}"


TOOLS = [test_tool, test_tool_with_auth_provider]
