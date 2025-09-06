#!/usr/bin/env python3
"""WebSocket MCP server using official MCP Python SDK for testing."""

import asyncio
import json
from typing import Any, Dict, List, Optional, Sequence

from mcp.server.session import ServerSession
from mcp.server import Server, NotificationOptions
from mcp.types import Tool, TextContent, CallToolRequest, CallToolResult
from mcp.server.websocket import websocket_server


# Tool implementations
async def validate_json(json_string: str) -> Dict[str, Any]:
    """Validate and parse JSON string."""
    try:
        parsed = json.loads(json_string)
        return {"valid": True, "parsed": parsed}
    except json.JSONDecodeError as e:
        return {"valid": False, "error": str(e)}


async def format_json(data: str, indent: int = 2) -> str:
    """Format JSON string with proper indentation."""
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, indent=indent)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


async def minify_json(data: str) -> str:
    """Remove whitespace from JSON string."""
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, separators=(',', ':'))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


async def extract_keys(json_string: str) -> List[str]:
    """Extract all keys from a JSON object."""
    try:
        parsed = json.loads(json_string)
        if isinstance(parsed, dict):
            return list(parsed.keys())
        else:
            raise ValueError("JSON is not an object")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


# Create server instance
server = Server("WebSocket Tools Server")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="validate_json",
            description="Validate and parse a JSON string",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_string": {
                        "type": "string",
                        "description": "The JSON string to validate"
                    }
                },
                "required": ["json_string"]
            }
        ),
        Tool(
            name="format_json",
            description="Format JSON string with proper indentation",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The JSON string to format"
                    },
                    "indent": {
                        "type": "integer",
                        "description": "Number of spaces for indentation",
                        "default": 2
                    }
                },
                "required": ["data"]
            }
        ),
        Tool(
            name="minify_json",
            description="Remove whitespace from JSON string",
            inputSchema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "description": "The JSON string to minify"
                    }
                },
                "required": ["data"]
            }
        ),
        Tool(
            name="extract_keys",
            description="Extract all keys from a JSON object",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_string": {
                        "type": "string",
                        "description": "The JSON object string"
                    }
                },
                "required": ["json_string"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "validate_json":
            result = await validate_json(arguments["json_string"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "format_json":
            indent = arguments.get("indent", 2)
            result = await format_json(arguments["data"], indent)
            return [TextContent(type="text", text=result)]
        
        elif name == "minify_json":
            result = await minify_json(arguments["data"])
            return [TextContent(type="text", text=result)]
        
        elif name == "extract_keys":
            result = await extract_keys(arguments["json_string"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def main():
    """Run the WebSocket server."""
    # Create WebSocket server on port 8080
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute
    
    def create_session():
        return ServerSession(server, NotificationOptions())
    
    async def websocket_endpoint(websocket):
        session = create_session()
        await websocket_server(websocket.scope, websocket.receive, websocket.send, session)
    
    app = Starlette(
        routes=[
            WebSocketRoute("/ws", websocket_endpoint)
        ]
    )
    
    print("Starting WebSocket MCP server on ws://localhost:8080/ws")
    uvicorn.run(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()