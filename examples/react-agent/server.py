#!/usr/bin/env python3
from universal_tool_server import Server

app = Server()


@app.add_tool
async def get_temperature(city: str) -> str:
    """Get the temperature in the given city."""
    return "The temperature in {} is 25C".format(city)


@app.add_tool()
async def get_time(city: str) -> str:
    """Get the current local time in the given city."""
    return "The current local time in {} is 12:34 PM".format(city)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", reload=True, port=8002)
