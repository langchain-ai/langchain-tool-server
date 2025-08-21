"""Test the server."""

from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator, Optional

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.tools import tool
from starlette.requests import Request

from langchain_tool_server import Server
from langchain_tool_server._version import __version__
from langchain_tool_server.tools import InjectedRequest

from ..unit_tests.utils import AnyStr


@asynccontextmanager
async def get_async_test_client(
    server: FastAPI, *, path: Optional[str] = None, raise_app_exceptions: bool = True
) -> AsyncGenerator[AsyncClient, None]:
    """Get an async client."""
    url = "http://localhost:9999"
    if path:
        url += path
    transport = ASGITransport(
        app=server,
        raise_app_exceptions=raise_app_exceptions,
    )
    async_client = AsyncClient(base_url=url, transport=transport)
    try:
        yield async_client
    finally:
        await async_client.aclose()


async def test_health() -> None:
    app = Server()
    async with get_async_test_client(app) as client:
        response = await client.get("/health")
        response.raise_for_status()
        assert response.json() == {"status": "OK"}


async def test_info() -> None:
    """Test info end-point."""
    app = Server()
    async with get_async_test_client(app) as client:
        response = await client.get("/info")
        response.raise_for_status()
        json_data = response.json()
        assert json_data == {
            "version": __version__,
        }


async def test_list_tools() -> None:
    """Test list tools."""
    app = Server()
    async with get_async_test_client(app) as client:
        response = await client.get("/tools")
        response.raise_for_status()
        json_data = response.json()
        assert json_data == []


async def test_422() -> None:
    """Test 422 responses."""
    app = Server()

    @tool
    def echo(number: int) -> str:
        """Echo a message."""
        return str(number)

    app.add_tool(echo)

    async with get_async_test_client(app) as client:
        response = await client.post("/tools/call", json={})
        assert response.status_code == 422
        assert "message" in response.json()
        assert (
            response.json()["message"]
            == "{'type': 'missing', 'loc': ('body', 'request'), 'msg': 'Field "
            "required', 'input': {}}"
        )


async def test_lifespan() -> None:
    import contextlib

    from starlette.testclient import TestClient

    calls = []

    @contextlib.asynccontextmanager
    async def lifespan(app):
        calls.append("startup")
        yield {"foo": "bar"}
        calls.append("shutdown")

    app = Server(lifespan=lifespan)

    @tool
    def what_is_foo(request: Annotated[Request, InjectedRequest]) -> str:
        """Get foo"""
        return request.state.foo

    app.add_tool(what_is_foo)

    # Using Starlette's TestClient to make sure that the lifespan is used.
    # Seems to not be supported with httpx's ASGITransport.
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert calls == ["startup"]
        response = client.post(
            "/tools/call", json={"request": {"tool_id": "what_is_foo", "input": {}}}
        )
        response.raise_for_status()
        result = response.json()
        assert result == {
            "value": "bar",
            "success": True,
            "call_id": AnyStr(),
        }

    assert calls == ["startup", "shutdown"]
