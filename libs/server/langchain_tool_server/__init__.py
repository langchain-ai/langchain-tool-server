import logging
from contextlib import asynccontextmanager
from typing import Callable, Optional, Tuple, TypeVar, Union, overload

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.types import Lifespan, Receive, Scope, Send

from langchain_tool_server import root
from langchain_tool_server._version import __version__
from langchain_tool_server.auth import Auth
from langchain_tool_server.auth.middleware import (
    ServerAuthenticationBackend,
    on_auth_error,
)
from langchain_tool_server.splash import SPLASH
from langchain_tool_server.tools import (
    InjectedRequest,
    ToolHandler,
    create_tools_router,
    validation_exception_handler,
)

T = TypeVar("T", bound=Callable)

logger = logging.getLogger(__name__)
# Ensure the logger has a handler and proper format
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("INFO:     %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class Server:
    """LangChain tool server."""

    def __init__(
        self, *, lifespan: Lifespan | None = None, enable_mcp: bool = False
    ) -> None:
        """Initialize the server."""

        @asynccontextmanager
        async def full_lifespan(app: FastAPI):
            """A lifespan event that is called when the server starts."""
            print(SPLASH)
            # yield whatever is inside the context manager
            if lifespan:
                async with lifespan(app) as stateful:
                    yield stateful
            else:
                yield

        self.app = FastAPI(
            version=__version__,
            lifespan=full_lifespan,
            title="LangChain Tool Server",
        )

        # Add a global exception handler for validation errors
        self.app.exception_handler(RequestValidationError)(validation_exception_handler)
        # Routes that go under `/`
        self.app.include_router(root.router)
        # Create a tool handler
        self.tool_handler = ToolHandler()
        # Routes that go under `/tools`
        router = create_tools_router(self.tool_handler)
        self.app.include_router(router, prefix="/tools")

        self._auth = Auth()
        # Also create the tool handler.
        # For now, it's a global that's referenced by both MCP and /tools router
        # Routes that go under `/mcp` (Model Context Protocol)
        self._enable_mcp = enable_mcp

        if enable_mcp:
            from langchain_tool_server.mcp import create_mcp_router

            mcp_router = create_mcp_router(self.tool_handler)
            self.app.include_router(mcp_router, prefix="/mcp")

    def add_tool(
        self, 
        tool, 
        *, 
        permissions: list[str] | None = None,
        version: Union[int, str, Tuple[int, int, int]] = (1, 0, 0),
    ) -> None:
        """Add a LangChain tool to the server.
        
        Args:
            tool: A BaseTool instance (created with @tool decorator).
            permissions: Permissions required to call the tool.
            version: Version of the tool.
        """
        logger.info(f"Registering tool: {tool.name}")
        self.tool_handler.add(tool, permissions=permissions, version=version)

    def add_tools(self, *tools) -> None:
        """Add multiple LangChain tools at once.
        
        Args:
            tools: BaseTool instances (created with @tool decorator).
        """
        for tool in tools:
            logger.info(f"Registering tool: {tool.name}")
            self.tool_handler.add(tool)

    def add_auth(self, auth: Auth) -> None:
        """Add an authentication handler to the server."""
        if not isinstance(auth, Auth):
            raise TypeError(f"Expected an instance of Auth, got {type(auth)}")

        if self._auth._authenticate_handler is not None:
            raise ValueError(
                "Please add an authentication handler before adding another one."
            )

        # Make sure that the tool handler enables authentication checks.
        # Needed b/c Starlette's Request object raises assertion errors if
        # trying to access request.auth when auth is not enabled.
        self.tool_handler.auth_enabled = True

        if self._enable_mcp:
            raise AssertionError("MCPs Python SDK does not support authentication.")

        self.app.add_middleware(
            AuthenticationMiddleware,
            backend=ServerAuthenticationBackend(auth),
            on_error=on_auth_error,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI Application"""
        return await self.app.__call__(scope, receive, send)


__all__ = ["__version__", "Server", "Auth", "InjectedRequest", "prebuilts"]
