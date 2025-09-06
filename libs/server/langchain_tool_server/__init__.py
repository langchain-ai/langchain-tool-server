import importlib.util
import logging
import sys
from contextlib import asynccontextmanager
from typing import Callable, TypeVar

import tomllib
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
from langchain_tool_server.context import Context
from langchain_tool_server.mcp_loader import load_mcp_servers_tools
from langchain_tool_server.splash import SPLASH
from langchain_tool_server.tool import tool
from langchain_tool_server.tools import (
    InjectedRequest,
    ToolHandler,
    create_tools_router,
    validation_exception_handler,
)


def _load_auth_instance(path: str, package_dir) -> Auth:
    """Load an Auth instance from a path string.

    Args:
        path: Path in the format './path/to/file.py:auth_instance_name'
        package_dir: Base directory for resolving relative paths

    Returns:
        Auth instance

    Raises:
        ValueError: If path format is invalid or auth instance not found
        ImportError: If module cannot be imported
        FileNotFoundError: If file path does not exist
    """
    if ":" not in path:
        raise ValueError(
            f"Invalid auth path format: {path}. "
            "Must be in format: './path/to/file.py:name' or 'module:name'"
        )

    module_name, callable_name = path.rsplit(":", 1)
    module_name = module_name.rstrip(":")

    try:
        if "/" in module_name or ".py" in module_name:
            # Load from file path (resolve relative to package directory)
            if module_name.startswith("./"):
                file_path = package_dir / module_name[2:]  # Remove ./
            else:
                file_path = package_dir / module_name

            if not file_path.exists():
                raise FileNotFoundError(f"Auth file not found: {file_path}")

            # Determine proper module name and package from file structure
            relative_path = file_path.relative_to(package_dir)

            if len(relative_path.parts) > 1:
                # File is in a package subdirectory (e.g., oap_tool_server/auth.py)
                package_name = relative_path.parts[0]
                module_name_parts = (
                    [package_name]
                    + list(relative_path.parts[1:-1])
                    + [relative_path.stem]
                )
                full_module_name = ".".join(module_name_parts)
                module_package = ".".join(module_name_parts[:-1])
            else:
                # File is in root directory
                full_module_name = relative_path.stem
                module_package = None

            modspec = importlib.util.spec_from_file_location(
                full_module_name, file_path
            )
            if modspec is None or modspec.loader is None:
                raise ValueError(f"Could not load auth file: {file_path}")

            module = importlib.util.module_from_spec(modspec)

            # Set proper package context for relative imports
            if module_package:
                module.__package__ = module_package

                # Ensure parent package exists in sys.modules
                if package_name not in sys.modules:
                    package_init_path = package_dir / package_name / "__init__.py"
                    if package_init_path.exists():
                        package_spec = importlib.util.spec_from_file_location(
                            package_name, package_init_path
                        )
                        if package_spec and package_spec.loader:
                            package_module = importlib.util.module_from_spec(
                                package_spec
                            )
                            package_module.__path__ = [str(package_dir / package_name)]
                            sys.modules[package_name] = package_module
                            package_spec.loader.exec_module(package_module)

            # Add package directory to sys.path temporarily for imports
            package_path_str = str(package_dir)
            path_added = package_path_str not in sys.path
            if path_added:
                sys.path.insert(0, package_path_str)

            try:
                sys.modules[full_module_name] = module
                modspec.loader.exec_module(module)
            finally:
                if path_added:
                    sys.path.remove(package_path_str)
        else:
            # Load from Python module
            module = importlib.import_module(module_name)

        loaded_auth = getattr(module, callable_name, None)
        if loaded_auth is None:
            raise ValueError(
                f"Could not find auth instance '{callable_name}' in module: {module_name}"
            )
        if not isinstance(loaded_auth, Auth):
            raise ValueError(f"Expected an Auth instance, got {type(loaded_auth)}")

        return loaded_auth

    except ImportError as e:
        raise ImportError(f"Could not import auth module '{module_name}': {e}") from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Could not find auth file: {module_name}") from e


def _load_tools_object(path: str, package_dir) -> list:
    """Load a TOOLS list from a path string.

    Args:
        path: Path in format './path/to/file.py:TOOLS'
        package_dir: Base directory for resolving relative paths

    Returns:
        List of tools

    Raises:
        ValueError: If path format is invalid or TOOLS object not found
        ImportError: If module cannot be imported
        FileNotFoundError: If file path does not exist
    """
    if ":" not in path:
        raise ValueError(
            f"Invalid tools path format: {path}. "
            "Must be in format: './path/to/file.py:TOOLS' or 'module:TOOLS'"
        )

    module_name, object_name = path.rsplit(":", 1)
    module_name = module_name.rstrip(":")

    try:
        if "/" in module_name or ".py" in module_name:
            # Load from file path (resolve relative to package directory)
            if module_name.startswith("./"):
                file_path = package_dir / module_name[2:]  # Remove ./
            else:
                file_path = package_dir / module_name

            if not file_path.exists():
                raise FileNotFoundError(f"Tools file not found: {file_path}")

            modname = f"dynamic_tools_module_{hash(str(file_path))}"
            modspec = importlib.util.spec_from_file_location(modname, file_path)
            if modspec is None or modspec.loader is None:
                raise ValueError(f"Could not load tools file: {file_path}")

            module = importlib.util.module_from_spec(modspec)
            sys.modules[modname] = module
            modspec.loader.exec_module(module)
        else:
            # Load from Python module
            module = importlib.import_module(module_name)

        loaded_tools = getattr(module, object_name, None)
        if loaded_tools is None:
            raise ValueError(
                f"Could not find tools object '{object_name}' in module: {module_name}"
            )
        if not isinstance(loaded_tools, list):
            raise ValueError(f"Expected a list of tools, got {type(loaded_tools)}")

        return loaded_tools

    except ImportError as e:
        raise ImportError(f"Could not import tools module '{module_name}': {e}") from e
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Could not find tools file: {module_name}") from e


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

    def _add_tool(
        self,
        tool,
        *,
        permissions: list[str] | None = None,
    ) -> None:
        """Add a LangChain tool to the server (internal method).

        Args:
            tool: A BaseTool instance (created with @tool decorator).
            permissions: Permissions required to call the tool.
        """
        # Let ToolHandler.add() do the validation - it has better error messages
        self.tool_handler.add(tool, permissions=permissions)
        logger.info(f"Registered tool: {tool.name}")

    def _add_tools(self, *tools) -> None:
        """Add multiple LangChain tools at once (internal method).

        Args:
            tools: BaseTool instances (created with @tool decorator).
        """
        for tool_item in tools:
            self._add_tool(tool_item)

    def _add_auth(self, auth: Auth) -> None:
        """Add an authentication handler to the server (internal method)."""
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
    def _load_toolkit_base(
        cls, toolkit_dir: str = ".", **kwargs
    ) -> tuple["Server", dict]:
        """Load toolkit base configuration and create server with tools and auth.

        This is a shared helper method for both from_toolkit and afrom_toolkit
        that handles all the common toolkit loading logic.

        Args:
            toolkit_dir: Path to toolkit directory (default: current directory)
            **kwargs: Additional arguments passed to Server constructor

        Returns:
            Tuple of (server_instance, toolkit_config)

        Raises:
            ValueError: If no toolkit package found or configuration is invalid
        """
        from pathlib import Path

        toolkit_path = Path(toolkit_dir).resolve()

        # Find package directory (has __init__.py and is not hidden/cache)
        package_dirs = [
            d
            for d in toolkit_path.iterdir()
            if d.is_dir()
            and (d / "__init__.py").exists()
            and not d.name.startswith(".")
            and d.name
            not in {"__pycache__", "node_modules", ".git", ".venv", "venv", "env"}
        ]

        if not package_dirs:
            raise ValueError(f"No toolkit package found in {toolkit_path}")

        package_dir = package_dirs[0]
        package_name = package_dir.name

        logger.info(f"Loading toolkit: {package_name}")

        try:
            with open(toolkit_path / "toolkit.toml", "rb") as f:
                toolkit_config = tomllib.load(f)

            tools_path = toolkit_config.get("toolkit", {}).get("tools")
            if not tools_path:
                raise ValueError(
                    "No tools path specified in toolkit.toml. "
                    "Please add: tools = './path/to/file.py:TOOLS'"
                )

            tools = _load_tools_object(tools_path, toolkit_path)

            auth_instance = None
            auth_path = toolkit_config.get("toolkit", {}).get("auth")

            if auth_path:
                logger.info(f"Loading auth from path: {auth_path}")
                try:
                    auth_instance = _load_auth_instance(auth_path, toolkit_path)
                    logger.info(f"Successfully loaded auth handler from {auth_path}")
                except Exception as e:
                    logger.error(f"Failed to load auth from {auth_path}: {e}")
                    import traceback

                    logger.error(f"Auth loading traceback:\n{traceback.format_exc()}")
                    raise e

            # Create server and register tools
            server = cls(**kwargs)

            # Add auth if found
            if auth_instance:
                server._add_auth(auth_instance)

            for tool_item in tools:
                server._add_tool(tool_item)

            logger.info(f"Successfully registered {len(tools)} tools from {tools_path}")

            return server, toolkit_config

        except (ImportError, ModuleNotFoundError) as e:
            raise ValueError(f"Error importing toolkit: {e}") from e

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
        # Load toolkit base configuration and create server
        server, toolkit_config = cls._load_toolkit_base(toolkit_dir, **kwargs)

        # Check if MCP servers are configured
        mcp_servers = toolkit_config.get("mcp_servers", [])
        if mcp_servers:
            logger.warning(
                f"Found {len(mcp_servers)} MCP server configuration(s) in toolkit.toml. "
                "MCP servers require async initialization. Please use Server.afrom_toolkit() "
                "instead of Server.from_toolkit() to load MCP server tools."
            )

        return server

    @classmethod
    async def afrom_toolkit(cls, toolkit_dir: str = ".", **kwargs) -> "Server":
        """Create server from toolkit directory with async MCP server support.

        This async version supports loading tools from MCP servers configured in
        toolkit.toml. Use this method when your toolkit includes MCP servers.

        Args:
            toolkit_dir: Path to toolkit directory (default: current directory)
            **kwargs: Additional arguments passed to Server constructor

        Returns:
            Server instance with toolkit tools and MCP tools registered

        Raises:
            ValueError: If no toolkit package found or configuration is invalid
        """
        # Load toolkit base configuration and create server
        server, toolkit_config = cls._load_toolkit_base(toolkit_dir, **kwargs)

        # Load MCP server tools if configured
        mcp_servers = toolkit_config.get("mcp_servers", [])
        if mcp_servers:
            logger.info(f"Found {len(mcp_servers)} MCP server configurations")
            try:
                # Load tools from MCP servers
                mcp_tools = await load_mcp_servers_tools(
                    mcp_servers,
                    prefix_tools=toolkit_config.get("mcp_prefix_tools", True),
                )

                # Register MCP tools
                for tool in mcp_tools:
                    server._add_tool(tool)

                logger.info(f"Successfully registered {len(mcp_tools)} MCP tools")

            except ImportError as e:
                logger.warning(
                    f"langchain-mcp-adapters not installed, skipping MCP servers: {e}"
                )
            except Exception as e:
                logger.error(f"Failed to load MCP server tools: {e}")
                # Don't fail the entire server if MCP loading fails
                # This allows graceful degradation

        return server

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI Application"""
        return await self.app.__call__(scope, receive, send)


__all__ = ["__version__", "Server", "Auth", "InjectedRequest", "tool", "Context"]
