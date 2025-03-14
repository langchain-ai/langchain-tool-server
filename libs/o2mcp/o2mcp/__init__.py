#!/usr/bin/env python

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from importlib import metadata
from itertools import chain
from typing import Any, Literal, Sequence

from mcp import stdio_server
from mcp.server.lowlevel import Server as MCPServer
from mcp.server.sse import SseServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from universal_tool_client import AsyncClient, get_async_client

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""


# ANSI color codes
class Colors:
    RED = "\033[91m"
    END = "\033[0m"


def print_error(message: str) -> None:
    """Print an error message in red if terminal supports colors."""
    # Check if stdout is a terminal and if the terminal supports colors
    if sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        print(f"{Colors.RED}Error: {message}{Colors.END}")
    else:
        print(f"Error: {message}")


SPLASH = """\
   ██████╗ ██████╗ ███╗   ███╗ ██████╗██████╗
   ██╔═══██╗╚════██╗████╗ ████║██╔════╝██╔══██╗
   ██║   ██║ █████╔╝██╔████╔██║██║     ██████╔╝
   ██║   ██║██╔═══╝ ██║╚██╔╝██║██║     ██╔═══╝
   ╚██████╔╝███████╗██║ ╚═╝ ██║╚██████╗██║
    ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝╚═╝
"""


def _convert_to_content(
    result: Any,
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Convert a result to a sequence of content objects."""
    # This code comes directly from the FastMCP server.
    # Imported here as it is a private function.
    import pydantic_core
    from mcp.server.fastmcp.utilities.types import Image
    from mcp.types import EmbeddedResource, ImageContent, TextContent

    if result is None:
        return []

    if isinstance(result, (TextContent, ImageContent, EmbeddedResource)):
        return [result]

    if isinstance(result, Image):
        return [result.to_image_content()]

    if isinstance(result, (list, tuple)):
        return list(chain.from_iterable(_convert_to_content(item) for item in result))

    if not isinstance(result, str):
        try:
            result = json.dumps(pydantic_core.to_jsonable_python(result))
        except Exception:
            result = str(result)

    return [TextContent(type="text", text=result)]


async def create_mcp_server(
    client: AsyncClient, *, tools: list[str] | None = None
) -> MCPServer:
    """Create MCP server.

    Args:
        client: AsyncClient instance.
        tools: If provided, only the tools on this list will be available.
    """
    tools = tools or []
    for tool in tools:
        if "@" in tool:
            raise NotImplementedError("Tool versions are not yet supported.")

    server = MCPServer(name="OTC-MCP Bridge")
    server_tools = await client.tools.list()

    latest_tool = {}

    for tool in server_tools:
        version = tool["version"]
        # version is semver 3 tuple
        version_tuple = tuple(map(int, version.split(".")))
        current_version = latest_tool.get(tool["name"], (0, 0, 0))

        if version_tuple > current_version:
            latest_tool[tool["name"]] = version_tuple

    available_tools = [
        Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["input_schema"],
        )
        for tool in server_tools
        if tuple(map(int, tool["version"].split("."))) == latest_tool[tool["name"]]
    ]

    if tools:
        available_tools = [
            available_tool
            for available_tool in available_tools
            if available_tool.name in tools
        ]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.
        return available_tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Call a tool by name with arguments."""
        # The original request object is not currently available in the MCP server.
        # We'll send a None for the request object.
        # This means that if Auth is enabled, the MCP endpoint will not
        # list any tools that require authentication.
        response = await client.tools.call(name, arguments)
        if not response["success"]:
            raise NotImplementedError(
                "Support for error messages is not yet implemented."
            )
        return _convert_to_content(response["value"])

    return server


async def run_server_stdio(server: MCPServer) -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def run_starlette(server: MCPServer, *, host: str, port: int) -> None:
    """Run as a Starlette server exposing /sse endpoint."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info",
        timeout_graceful_shutdown=1,
    )
    uvicorn_server = uvicorn.Server(config)
    await uvicorn_server.serve()


async def display_tools_table(*, url: str, headers: dict | None) -> None:
    """Connect to server and display available tools in a tabular format."""
    client = get_async_client(url=url, headers=headers)
    print(f"\nConnecting to server at {url}...\n")

    try:
        server_tools = await client.tools.list()

        if not server_tools:
            print("No tools available.")
            return

        # Find the longest tool name for formatting
        max_name_length = max(len(tool["name"]) for tool in server_tools)

        # Print table header
        print(f"{'NAME':<{max_name_length + 2}}| DESCRIPTION")
        print(f"{'-' * (max_name_length + 2)}|{'-' * 70}")

        # Group tools by name and get the latest version of each
        latest_tools = {}

        for tool in server_tools:
            name = tool["name"]
            version = tool["version"]
            version_tuple = tuple(map(int, version.split(".")))

            if name not in latest_tools or version_tuple > latest_tools[name][0]:
                latest_tools[name] = (version_tuple, tool)

        # Sort tools by name
        for name in sorted(latest_tools.keys()):
            tool = latest_tools[name][1]

            description = tool["description"].strip()
            if not description:
                print(f"{tool['name']:<{max_name_length + 2}}| [No description]")
                print()
                continue

            # Split description by newlines to preserve original line breaks
            desc_lines = description.split("\n")
            first_line = True

            for line in desc_lines:
                if first_line:
                    # Print first line with the tool name
                    print(f"{tool['name']:<{max_name_length + 2}}| {line}")
                    first_line = False
                else:
                    # Print remaining lines with proper indentation relative to the column
                    print(f"{' ' * (max_name_length + 2)}| {line}")

            # Add a small gap between tools
            print()

    except Exception as e:
        print_error(f"Failed to list tools: {str(e)}")
        sys.exit(1)


async def run(
    *,
    url: str,
    headers: dict | None,
    tools: list[str] | None = None,
    mode: str = Literal["stdio", "sse"],
    sse_settings: dict | None = None,
) -> None:
    """Run the MCP server in stdio mode."""
    client = get_async_client(url=url, headers=headers)
    print()
    print()
    print(SPLASH)
    print()
    server = await create_mcp_server(client, tools=tools)
    print()
    print(f"Connected to {url}")

    if mode == "sse":
        sse_settings = sse_settings or {}
        port = sse_settings.get("port", 8000)
        host = sse_settings.get("host", "localhost")
        print(f"Running MCP server with SSE endpoint at http://{host}:{port}/sse")
        print()
        await run_starlette(server, host=host, port=port)
    else:
        print("* Running MCP server in stdio mode. Press CTRL+C to exit.")
        await run_server_stdio(server)


def get_usage_examples() -> str:
    """Return usage examples for the command line interface."""
    examples = """
Examples:
  # Connect to a Universal Tool Server with default settings
  o2mcp --url http://localhost:8000

  # Connect with authentication headers
  o2mcp --url http://localhost:8000 --headers '{"Authorization": "Bearer YOUR_TOKEN"}'

  # Connect and limit to specific tools
  o2mcp --url http://localhost:8000 --tools tool1 tool2 tool3

  # List available tools without starting the server
  o2mcp --url http://localhost:8000 --list-tools

  # Start the server in SSE mode
  o2mcp --url http://localhost:8000 --mode sse

  # Start the server in SSE mode with custom host and port
  o2mcp --url http://localhost:8000 --mode sse --host 0.0.0.0 --port 9000

  # Display version information
  o2mcp --version
"""
    return examples


def show_usage_examples() -> None:
    """Print usage examples for the command line interface."""
    print(get_usage_examples())


def main() -> None:
    """Main entry point for the MCP Bridge."""
    parser = argparse.ArgumentParser(
        description="MCP Bridge Server",
        epilog=get_usage_examples(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url", type=str, help="URL of the Universal Tool Server (required)"
    )
    parser.add_argument(
        "--headers",
        type=str,
        default=None,
        help="JSON encoded headers to include in requests",
    )
    parser.add_argument(
        "--tools",
        type=str,
        nargs="*",
        help=(
            "List of tools to expose. If not specified, all available tools will be "
            "used"
        ),
    )
    parser.add_argument(
        "--list-tools", action="store_true", help="List available tools and exit"
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version information and exit"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        help="Server mode: stdio (default) or sse",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the SSE server to (only used with --mode sse)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the SSE server to (only used with --mode sse)",
    )
    # Show help and version if no arguments provided
    if len(sys.argv) == 1:
        print(f"MCP Bridge v{__version__}")
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Handle version request
    if args.version:
        print(f"MCP Bridge v{__version__}")
        sys.exit(0)

    # Check for required URL
    if not args.url:
        parser.print_help()
        print("\n")  # Add extra space before error
        print_error("the --url argument is required")
        sys.exit(1)

    headers = None
    if args.headers:
        try:
            headers = json.loads(args.headers)
        except json.JSONDecodeError:
            parser.print_help()
            print("\n")  # Add extra space before error
            print_error("--headers must be valid JSON")
            sys.exit(1)

    if args.list_tools:
        asyncio.run(display_tools_table(url=args.url, headers=headers))
    else:
        sse_settings = None

        # Check if host or port are specified in stdio mode
        if args.mode == "stdio" and (args.host != "localhost" or args.port != 8000):
            print_error("--host and --port can only be used with --mode sse")
            sys.exit(1)

        if args.mode == "sse":
            sse_settings = {
                "host": args.host,
                "port": args.port,
            }
        asyncio.run(
            run(
                url=args.url,
                headers=headers,
                tools=args.tools,
                mode=args.mode,
                sse_settings=sse_settings,
            )
        )


if __name__ == "__main__":
    main()
