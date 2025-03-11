from universal_tool_server import Server

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", reload=True, port=8002)
