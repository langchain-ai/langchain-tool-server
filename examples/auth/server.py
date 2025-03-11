#!/usr/bin/env python
from typing import Annotated

from starlette.requests import Request

from universal_tool_server import Auth, Server
from universal_tool_server.tools import InjectedRequest

app = Server()
auth = Auth()


@auth.authenticate
async def authenticate(headers: dict[bytes, bytes]) -> dict:
    """Authenticate incoming requests."""
    # Replace this with actual authentication logic.
    api_key = headers.get(b"x-api-key")

    api_key_to_user = {
        b"1": {"permissions": ["authenticated", "group1"], "identity": "some-user"},
        b"2": {"permissions": ["authenticated", "group2"], "identity": "another-user"},
    }

    if not api_key or api_key not in api_key_to_user:
        raise auth.exceptions.HTTPException(detail="Not authorized")
    return api_key_to_user[api_key]


# At the moment this has to be done after registering the authenticate handler.
app.add_auth(auth)


@app.add_tool(permissions=["group1"])
async def echo(msg: str) -> str:
    """Echo a message."""
    return msg + "!"


@app.add_tool(permissions=["group2"])
async def say_hello() -> str:
    """Say hello."""
    return "Hello"


@app.add_tool(permissions=["authenticated"])
async def who_am_i(request: Annotated[Request, InjectedRequest]) -> str:
    """Get the user identity."""
    return request.user.identity


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", host="127.0.0.1", port=8002, reload=True)
