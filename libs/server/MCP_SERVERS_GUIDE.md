# MCP Server Integration Guide

This guide explains how to integrate MCP (Model Context Protocol) servers with the LangChain Tool Server.

## Overview

The LangChain Tool Server now supports loading tools from MCP servers alongside native LangChain tools. This allows you to:

- Use existing MCP tools within the LangChain ecosystem
- Combine native LangChain tools with MCP tools in a single server
- Support multiple MCP server connections with different transports
- Automatically prefix MCP tool names to avoid conflicts

## Prerequisites

Install the required dependency:

```bash
pip install langchain-mcp-adapters>=0.1.0
```

## Configuration

MCP servers are configured in your `toolkit.toml` file using the `[[mcp_servers]]` array syntax.

### Basic Structure

```toml
[toolkit]
name = "my_toolkit"
tools = "./my_toolkit/__init__.py:TOOLS"  # Your native tools

# Optional: Control tool name prefixing
mcp_prefix_tools = true  # Default: true

# Each [[mcp_servers]] section defines one MCP server
[[mcp_servers]]
name = "server_name"
transport = "transport_type"
# ... transport-specific configuration
```

### Transport Types

#### 1. stdio Transport

For local MCP server processes:

```toml
[[mcp_servers]]
name = "local_server"
transport = "stdio"
command = "python"
args = ["-m", "mcp_server_module"]
env = { "DEBUG" = "true" }  # Optional
cwd = "/path/to/working/dir"  # Optional
```

#### 2. streamable_http Transport

For HTTP-based MCP servers:

```toml
[[mcp_servers]]
name = "http_server"
transport = "streamable_http"
url = "http://localhost:8000/mcp/"
headers = { "Authorization" = "Bearer token" }  # Optional
timeout = 30  # Optional, in seconds
```

#### 3. SSE Transport

For Server-Sent Events:

```toml
[[mcp_servers]]
name = "sse_server"
transport = "sse"
url = "http://localhost:9000/sse"
headers = { "X-Custom" = "value" }  # Optional
timeout = 10.0  # Optional, float in seconds
```

#### 4. WebSocket Transport

For WebSocket connections:

```toml
[[mcp_servers]]
name = "ws_server"
transport = "websocket"
url = "ws://localhost:8080/ws"
```

## Usage

### Loading the Server

Since MCP servers require async initialization, use the `afrom_toolkit()` method:

```python
import asyncio
from langchain_tool_server import Server

async def main():
    # Load server with MCP support
    server = await Server.afrom_toolkit("./my_toolkit", enable_mcp=False)
    
    # Server now has both native and MCP tools
    print(f"Loaded {len(server.tool_handler.catalog)} tools")
    
    # Run the server with uvicorn or similar
    # uvicorn app:server --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    asyncio.run(main())
```

### Tool Naming

By default, MCP tool names are prefixed with the server name to avoid conflicts:

- Native tool: `my_function`
- MCP tool from "math_server": `math_server.add`

You can disable prefixing by setting `mcp_prefix_tools = false` in your `toolkit.toml`.

### Example Complete Configuration

```toml
[toolkit]
name = "example_toolkit"
tools = "./example_toolkit/__init__.py:TOOLS"
auth = "./example_toolkit/auth.py:auth"  # Optional
mcp_prefix_tools = true

# MCP server for mathematical operations
[[mcp_servers]]
name = "math"
transport = "stdio"
command = "python"
args = ["-m", "mcp_server_math"]

# MCP server for weather data
[[mcp_servers]]
name = "weather"
transport = "streamable_http"
url = "http://api.weather-mcp.com/mcp/"
headers = { "API-Key" = "your-api-key" }
timeout = 30

# Local development MCP server
[[mcp_servers]]
name = "dev_tools"
transport = "sse"
url = "http://localhost:9000/sse"
```

## Error Handling

- If an MCP server fails to connect, the tool server will continue with other servers
- Failed servers are logged but don't prevent the server from starting
- Use the sync `from_toolkit()` method if you don't have MCP servers (it will warn if MCP servers are configured)

## Authentication

- MCP tools bypass the server's built-in authentication system
- MCP servers can have their own authentication via headers or environment variables
- Native tools still respect the server's authentication configuration

## Limitations

1. MCP tools are loaded at server startup and cannot be dynamically reloaded
2. MCP server connections are not automatically retried if they fail
3. Tool schemas are derived from the MCP tool definitions and may not include all LangChain-specific features

## Troubleshooting

### MCP Tools Not Loading

1. Check that `langchain-mcp-adapters` is installed
2. Verify the MCP server is running and accessible
3. Check server logs for connection errors
4. Ensure transport configuration is correct (URL, command, etc.)

### Tool Name Conflicts

- Enable `mcp_prefix_tools = true` (default) to automatically prefix MCP tool names
- Ensure native tool names don't conflict with prefixed MCP tool names

### Async Initialization Required

If you see a warning about MCP servers requiring async initialization:
- Switch from `Server.from_toolkit()` to `Server.afrom_toolkit()`
- Use `asyncio.run()` or similar to run the async initialization

## Example: Creating an MCP Server

Here's a simple MCP server using FastMCP:

```python
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool()
def add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y

@mcp.tool()
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello {name}!"

if __name__ == "__main__":
    import sys
    mcp.run(transport="stdio")
```

Save this as `my_mcp_server.py` and reference it in your `toolkit.toml`:

```toml
[[mcp_servers]]
name = "my_mcp"
transport = "stdio"
command = "python"
args = ["my_mcp_server.py"]
```

## Further Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [FastMCP Documentation](https://gofastmcp.com/)