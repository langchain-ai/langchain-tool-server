from langchain_tool_server.tool import tool


@tool
def hello() -> str:
    """Say hello."""
    return "Hello, world!"


@tool
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


TOOLS = [hello, add]
