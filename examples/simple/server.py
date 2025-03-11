#!/usr/bin/env python
from universal_tool_server import Server
from universal_tool_server.auth import Auth

app = Server()
auth = Auth()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", host="127.0.0.1", port=8002, reload=True)
