from typing import Annotated

from starlette.requests import Request

from langchain_tool_server import Server
from langchain_tool_server.tools import InjectedRequest

app = Server(enable_mcp=True)


@app.add_tool()
async def echo(msg: str) -> str:
    """Echo a message."""
    return msg + "!"


@app.add_tool
async def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


@app.add_tool()
async def say_hello() -> str:
    """Say hello."""
    return "Hello"


@app.add_tool()
async def unavailable_tool(request: Annotated[Request, InjectedRequest]) -> str:
    """Tool not show up with MCP due to the injected request not being available."""
    return "Hello"
