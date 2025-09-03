from langchain_tool_server import Context, tool


@tool
def hello() -> str:
    """Say hello."""
    return "Hello, world!"


@tool
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


@tool(auth_provider="test_provider", scopes=["test_scope"])
def test_auth_tool(context: Context, message: str) -> str:
    """A test tool that requires authentication.

    Args:
        context: Authentication context
        message: A message to echo

    Returns:
        The message with auth info
    """
    return f"Authenticated message: {message}"


TOOLS = [hello, add, test_auth_tool]
