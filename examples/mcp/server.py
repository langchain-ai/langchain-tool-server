from langchain_tool_server import Server
from langchain_core.tools import tool

from tools.math_tools import TOOLS as math_tools
from tools.text_tools import TOOLS as text_tools

app = Server(enable_mcp=True)

@tool
async def echo(msg: str) -> str:
    """Echo a message."""
    return msg + "!"

@tool
async def add_simple(x: int, y: int) -> int:
    """Add two numbers (simple version)."""
    return x + y

app.add_tool(echo)
app.add_tool(add_simple)
app.add_tools(*math_tools, *text_tools)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("__main__:app", reload=True, port=8002, use_colors=False)
