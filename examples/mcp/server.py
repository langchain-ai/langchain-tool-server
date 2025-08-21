from universal_tool_server import Server
from langchain_core.tools import tool

app = Server(enable_mcp=True)

# Tools defined directly in the server file
@tool
async def echo(msg: str) -> str:
    """Echo a message."""
    return msg + "!"

@tool
async def add_simple(x: int, y: int) -> int:
    """Add two numbers (simple version)."""
    return x + y

@tool
async def say_hello() -> str:
    """Say hello."""
    return "Hello"

# Register local tools
app.add_tools(echo, add_simple, say_hello)

# Import and register tools from modules in bulk
from tools.math_tools import TOOLS as math_tools
from tools.text_tools import TOOLS as text_tools
from tools.utility_tools import TOOLS as utility_tools

# Register all tools from all modules in one line!
app.add_tools(*math_tools, *text_tools, *utility_tools)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", reload=True, port=8002)
