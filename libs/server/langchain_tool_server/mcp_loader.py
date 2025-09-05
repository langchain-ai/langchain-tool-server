"""MCP (Model Context Protocol) server integration for LangChain Tool Server.

This module provides functionality to load tools from MCP servers and convert them
to LangChain tools that can be used within the tool server.
"""

import logging
import os
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

# Import the Tool class from the tool module
from langchain_tool_server.tool import Tool

logger = logging.getLogger(__name__)


class MCPConfigError(ValueError):
    """Raised when MCP server configuration is invalid."""

    pass


def substitute_env_vars(value: Any) -> Any:
    """Substitute environment variables in configuration values.

    Supports the following patterns:
    - ${{ secrets.VAR_NAME }} -> os.environ['VAR_NAME']
    - ${{ env.VAR_NAME }} -> os.environ['VAR_NAME']
    - ${VAR_NAME} -> os.environ['VAR_NAME']
    - $VAR_NAME -> os.environ['VAR_NAME']

    Args:
        value: Configuration value to process (can be string, dict, list, etc.)

    Returns:
        Value with environment variables substituted

    Raises:
        MCPConfigError: If referenced environment variable is not found
    """
    if isinstance(value, str):
        # Pattern for ${{ secrets.VAR_NAME }} or ${{ env.VAR_NAME }}
        github_pattern = r"\$\{\{\s*(?:secrets|env)\.([A-Z_][A-Z0-9_]*)\s*\}\}"
        # Pattern for ${VAR_NAME}
        brace_pattern = r"\$\{([A-Z_][A-Z0-9_]*)\}"
        # Pattern for $VAR_NAME (word boundary to avoid partial matches)
        simple_pattern = r"\$([A-Z_][A-Z0-9_]*)\b"

        def replace_env_var(match):
            var_name = match.group(1)
            if var_name not in os.environ:
                raise MCPConfigError(
                    f"Environment variable '{var_name}' not found. "
                    f"Please set it in your environment."
                )
            return os.environ[var_name]

        # Apply substitutions in order of specificity
        value = re.sub(github_pattern, replace_env_var, value)
        value = re.sub(brace_pattern, replace_env_var, value)
        value = re.sub(simple_pattern, replace_env_var, value)

        return value

    elif isinstance(value, dict):
        # Recursively process dictionary values
        return {k: substitute_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        # Recursively process list items
        return [substitute_env_vars(item) for item in value]

    else:
        # Return other types as-is
        return value


class MCPToolAdapter(Tool):
    """Adapter that wraps a LangChain BaseTool to match the Tool interface."""

    def __init__(self, base_tool: BaseTool):
        """Initialize the adapter with a BaseTool."""
        self.base_tool = base_tool

        # Create a wrapper function for the tool
        wrapper_func = self._create_wrapper_func()

        # Initialize the Tool base class with the wrapper function
        # Don't call super().__init__ as it expects different parameters
        # Instead, set attributes directly
        self.func = wrapper_func
        self.name = base_tool.name
        self.description = base_tool.description or ""
        self.auth_provider = None  # MCP tools don't use built-in auth
        self.scopes = []

        # Get schemas from the BaseTool
        self.input_schema = self._get_input_schema()
        self.output_schema = self._get_output_schema()

    def _get_input_schema(self) -> dict:
        """Get input schema from the BaseTool."""
        if hasattr(self.base_tool, "args_schema") and self.base_tool.args_schema:
            # Use the Pydantic model's JSON schema
            return (
                self.base_tool.args_schema
                if isinstance(self.base_tool.args_schema, dict)
                else self.base_tool.args_schema.model_json_schema()
            )
        return {"type": "object", "properties": {}}

    def _get_output_schema(self) -> dict:
        """Get output schema from the BaseTool."""
        # Most LangChain tools return strings
        return {"type": "string"}

    def _create_wrapper_func(self):
        """Create a wrapper function that calls the BaseTool."""

        async def wrapper(**kwargs):
            """Wrapper function that calls the BaseTool."""
            # Use ainvoke for async execution
            result = await self.base_tool.ainvoke(kwargs)
            return result

        # Set the function name and docstring to match the tool
        wrapper.__name__ = self.base_tool.name
        wrapper.__doc__ = self.base_tool.description

        return wrapper

    async def _auth_hook(self, user_id: str = None):
        """Auth hook - MCP tools don't use built-in auth."""
        return None

    async def __call__(self, *args, user_id: str = None, **kwargs) -> Any:
        """Call the wrapped tool."""
        # MCP tools don't require auth hook, just call the function
        result = await self.func(**kwargs)
        return result


def validate_mcp_config(config: dict) -> dict:
    """Validate and normalize an MCP server configuration.

    Args:
        config: Raw MCP server configuration from toolkit.toml

    Returns:
        Normalized configuration dictionary ready for use with MultiServerMCPClient

    Raises:
        MCPConfigError: If configuration is invalid
    """
    # Apply environment variable substitution to the entire config
    config = substitute_env_vars(config)

    if "name" not in config:
        raise MCPConfigError("MCP server configuration must have a 'name' field")

    if "transport" not in config:
        raise MCPConfigError(
            f"MCP server '{config['name']}' must specify a 'transport' type"
        )

    transport = config["transport"]
    name = config["name"]

    # Create the connection config based on transport type
    connection_config: Dict[str, Any] = {"transport": transport}

    if transport == "stdio":
        # stdio transport requires command and optionally args, env, cwd
        if "command" not in config:
            raise MCPConfigError(
                f"MCP server '{name}' with stdio transport must specify 'command'"
            )
        connection_config["command"] = config["command"]

        if "args" in config:
            connection_config["args"] = config["args"]

        if "env" in config:
            connection_config["env"] = config["env"]

        if "cwd" in config:
            connection_config["cwd"] = config["cwd"]

    elif transport == "streamable_http":
        # streamable_http transport requires url and optionally headers, timeout
        if "url" not in config:
            raise MCPConfigError(
                f"MCP server '{name}' with streamable_http transport must specify 'url'"
            )
        connection_config["url"] = config["url"]

        if "headers" in config:
            connection_config["headers"] = config["headers"]

        if "timeout" in config:
            # Convert timeout from seconds to timedelta
            connection_config["timeout"] = timedelta(seconds=config["timeout"])

    elif transport == "sse":
        # SSE transport requires url and optionally headers, timeout
        if "url" not in config:
            raise MCPConfigError(
                f"MCP server '{name}' with sse transport must specify 'url'"
            )
        connection_config["url"] = config["url"]

        if "headers" in config:
            connection_config["headers"] = config["headers"]

        if "timeout" in config:
            # SSE timeout is a float in seconds
            connection_config["timeout"] = float(config["timeout"])

    elif transport == "websocket":
        # WebSocket transport requires url
        if "url" not in config:
            raise MCPConfigError(
                f"MCP server '{name}' with websocket transport must specify 'url'"
            )
        connection_config["url"] = config["url"]

    else:
        raise MCPConfigError(
            f"Unknown transport type '{transport}' for MCP server '{name}'. "
            f"Supported types: stdio, streamable_http, sse, websocket"
        )

    return connection_config


async def load_mcp_servers_tools(
    mcp_configs: List[Dict[str, Any]],
    prefix_tools: bool = True,
) -> List[Any]:  # Returns list of MCPToolAdapter instances
    """Load tools from multiple MCP servers.

    Args:
        mcp_configs: List of MCP server configurations from toolkit.toml
        enable_mcp: Whether MCP mode is enabled (affects auth behavior)
        prefix_tools: Whether to prefix tool names with server name to avoid conflicts

    Returns:
        List of MCPToolAdapter instances wrapping the MCP tools

    Raises:
        MCPConfigError: If any server configuration is invalid
    """
    if not mcp_configs:
        return []

    all_tools: List[Any] = []  # Will contain MCPToolAdapter instances
    failed_servers: List[str] = []

    # Build connections dict for MultiServerMCPClient
    connections = {}
    for config in mcp_configs:
        try:
            name = config.get("name")
            if not name:
                raise MCPConfigError(
                    "MCP server configuration must have a 'name' field"
                )

            # Validate and normalize the configuration
            connection_config = validate_mcp_config(config)
            connections[name] = connection_config

        except MCPConfigError as e:
            logger.error(f"Invalid MCP server configuration: {e}")
            raise

    if not connections:
        logger.warning("No valid MCP server configurations found")
        return []

    # Load tools from each server
    for server_name in connections.keys():
        try:
            logger.info(f"Loading tools from MCP server: {server_name}")

            # Use connection config instead of session to avoid session lifecycle issues
            # This allows tools to create fresh sessions with headers per call
            connection_config = connections[server_name]
            base_tools = await load_mcp_tools(
                session=None, connection=connection_config
            )

            # Wrap each BaseTool with MCPToolAdapter
            adapted_tools = []
            for base_tool in base_tools:
                # Store original name in metadata
                if not hasattr(base_tool, "metadata") or base_tool.metadata is None:
                    base_tool.metadata = {}
                base_tool.metadata["mcp_server"] = server_name
                base_tool.metadata["original_name"] = base_tool.name

                # Optionally prefix tool names with server name
                if prefix_tools:
                    base_tool.name = f"{server_name}.{base_tool.name}"
                # Create adapter wrapper
                adapter = MCPToolAdapter(base_tool)
                adapted_tools.append(adapter)

            all_tools.extend(adapted_tools)
            logger.info(
                f"Successfully loaded {len(adapted_tools)} tools from MCP server: {server_name}"
            )

        except Exception as e:
            logger.error(f"Failed to load tools from MCP server '{server_name}': {e}")
            failed_servers.append(server_name)
            # Continue loading from other servers even if one fails

    if failed_servers:
        logger.warning(
            f"Failed to load tools from {len(failed_servers)} MCP server(s): "
            f"{', '.join(failed_servers)}"
        )

    logger.info(f"Total MCP tools loaded: {len(all_tools)}")
    return all_tools


async def initialize_mcp_client(
    configs: List[Dict[str, Any]],
) -> Optional[MultiServerMCPClient]:
    """Initialize a MultiServerMCPClient from configurations.

    This is useful for managing MCP connections separately from tool loading.

    Args:
        configs: List of MCP server configurations

    Returns:
        MultiServerMCPClient instance or None if initialization fails
    """
    connections = {}

    for config in configs:
        try:
            name = config.get("name")
            if not name:
                continue

            connection_config = validate_mcp_config(config)
            connections[name] = connection_config

        except MCPConfigError as e:
            logger.error(f"Skipping invalid MCP server configuration: {e}")
            continue

    if connections:
        return MultiServerMCPClient(connections)

    return None
