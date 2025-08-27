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
from langchain_tool_server.tool import tool
from langchain_tool_server.context import Context

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
    ) -> None:
        """Add a LangChain tool to the server.

        Args:
            tool: A BaseTool instance (created with @tool decorator).
            permissions: Permissions required to call the tool.
        """
        # Let ToolHandler.add() do the validation - it has better error messages
        self.tool_handler.add(tool, permissions=permissions)
        logger.info(f"Registered tool: {tool.name}")

    def add_tools(self, *tools) -> None:
        """Add multiple LangChain tools at once.

        Args:
            tools: BaseTool instances (created with @tool decorator).
        """
        for tool in tools:
            self.add_tool(tool)

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

        self.app.add_middleware(
            AuthenticationMiddleware,
            backend=ServerAuthenticationBackend(auth),
            on_error=on_auth_error,
        )

    @classmethod
    def from_toolkit(cls, toolkit_dir: str = ".", **kwargs) -> "Server":
        """Create server from toolkit directory.
        
        Args:
            toolkit_dir: Path to toolkit directory (default: current directory)
            **kwargs: Additional arguments passed to Server constructor
            
        Returns:
            Server instance with toolkit tools registered
            
        Raises:
            ValueError: If no toolkit package found or TOOLS registry missing
        """
        import importlib.util
        import sys
        from pathlib import Path
        
        toolkit_path = Path(toolkit_dir).resolve()
        
        # Find package directory (has __init__.py and is not hidden/cache)
        package_dirs = [
            d for d in toolkit_path.iterdir() 
            if d.is_dir() 
            and (d / "__init__.py").exists() 
            and not d.name.startswith('.')
            and d.name not in {'__pycache__', 'node_modules', '.git', '.venv', 'venv', 'env'}
        ]
        
        if not package_dirs:
            raise ValueError(f"No toolkit package found in {toolkit_path}")
            
        package_dir = package_dirs[0]
        package_name = package_dir.name
        
        logger.info(f"Loading toolkit: {package_name}")
        
        try:
            # Import toolkit package
            spec = importlib.util.spec_from_file_location(
                package_name, 
                package_dir / "__init__.py"
            )
            
            if not spec or not spec.loader:
                raise ValueError(f"Could not load package {package_name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = module
            
            # Load tools submodule first (needed for relative imports)
            tools_init = package_dir / "tools" / "__init__.py"
            if tools_init.exists():
                tools_spec = importlib.util.spec_from_file_location(
                    f"{package_name}.tools",
                    tools_init
                )
                if tools_spec and tools_spec.loader:
                    tools_module = importlib.util.module_from_spec(tools_spec)
                    sys.modules[f"{package_name}.tools"] = tools_module
                    
                    # Load individual tool modules
                    tools_dir = package_dir / "tools"
                    for py_file in tools_dir.glob("*.py"):
                        if py_file.name.startswith("__"):
                            continue
                        tool_spec = importlib.util.spec_from_file_location(
                            f"{package_name}.tools.{py_file.stem}",
                            py_file
                        )
                        if tool_spec and tool_spec.loader:
                            tool_module = importlib.util.module_from_spec(tool_spec)
                            sys.modules[f"{package_name}.tools.{py_file.stem}"] = tool_module
                            tool_spec.loader.exec_module(tool_module)
                    
                    # Now load the tools __init__.py
                    tools_spec.loader.exec_module(tools_module)
            
            # Execute main package module
            spec.loader.exec_module(module)
            
            # Get TOOLS registry
            if not hasattr(module, 'TOOLS'):
                raise ValueError(f"Package {package_name} does not export TOOLS registry")
            
            tools = module.TOOLS
            if not isinstance(tools, list):
                raise ValueError(f"TOOLS must be a list, got {type(tools)}")
            
            
            # Check for optional auth.py file
            auth_file = package_dir / "auth.py"
            auth_instance = None
            
            if auth_file.exists():
                logger.info(f"Loading auth from {package_name}.auth")
                try:
                    # Load auth module
                    auth_spec = importlib.util.spec_from_file_location(
                        f"{package_name}.auth",
                        auth_file
                    )
                    if auth_spec and auth_spec.loader:
                        auth_module = importlib.util.module_from_spec(auth_spec)
                        sys.modules[f"{package_name}.auth"] = auth_module
                        auth_spec.loader.exec_module(auth_module)
                        
                        # Look for 'auth' instance in the auth module
                        if hasattr(auth_module, 'auth'):
                            auth_instance = auth_module.auth
                            logger.info(f"Loaded auth handler from {package_name}.auth")
                        else:
                            logger.warning(f"auth.py exists but no 'auth' instance found")
                            
                except Exception as e:
                    logger.warning(f"Failed to load auth from {package_name}.auth: {e}")
            
            # Create server and register tools
            server = cls(**kwargs)
            
            # Add auth if found
            if auth_instance:
                server.add_auth(auth_instance)
            
            for tool in tools:
                server.add_tool(tool)
                
            logger.info(f"Registered {len(tools)} tools from {package_name}")
            return server
            
        except (ImportError, ModuleNotFoundError) as e:
            raise ValueError(f"Error importing toolkit: {e}") from e

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI Application"""
        return await self.app.__call__(scope, receive, send)


__all__ = ["__version__", "Server", "Auth", "InjectedRequest", "tool", "Context"]
