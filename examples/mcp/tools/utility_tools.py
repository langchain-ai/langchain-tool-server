"""Utility tools for the MCP server"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any
from langchain_core.tools import tool

@tool
async def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().isoformat()

@tool
async def echo_json(data: Dict[str, Any]) -> str:
    """Echo back the provided data as formatted JSON."""
    return json.dumps(data, indent=2)

@tool
async def sleep_and_return(seconds: int, message: str = "Done!") -> str:
    """Sleep for the specified number of seconds and return a message."""
    await asyncio.sleep(seconds)
    return f"Slept for {seconds} seconds. {message}"

@tool
async def generate_uuid() -> str:
    """Generate a random UUID."""
    import uuid
    return str(uuid.uuid4())

@tool
async def ping() -> str:
    """Simple ping tool to test connectivity."""
    return "pong"

# Export all tools for bulk registration
TOOLS = [get_current_time, echo_json, sleep_and_return, generate_uuid, ping]