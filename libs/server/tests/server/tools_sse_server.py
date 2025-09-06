#!/usr/bin/env python3
"""Tools MCP server using SSE transport for testing."""

import hashlib
import base64
import uuid
from datetime import datetime
from fastmcp import FastMCP

# Create server
mcp = FastMCP("Local Tools Server")


@mcp.tool()
def hash_text(text: str, algorithm: str = "sha256") -> str:
    """Generate hash of text using specified algorithm."""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512
    }
    
    if algorithm not in algorithms:
        raise ValueError(f"Unsupported algorithm. Choose from: {list(algorithms.keys())}")
    
    hasher = algorithms[algorithm]()
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()


@mcp.tool()
def encode_base64(text: str) -> str:
    """Encode text to base64."""
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')


@mcp.tool()
def decode_base64(encoded: str) -> str:
    """Decode base64 encoded text."""
    try:
        return base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}")


@mcp.tool()
def generate_uuid() -> str:
    """Generate a random UUID."""
    return str(uuid.uuid4())


@mcp.tool()
def get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


@mcp.tool()
def reverse_string(text: str) -> str:
    """Reverse a string."""
    return text[::-1]


@mcp.tool()
def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


if __name__ == "__main__":
    # Run as SSE server on port 9000
    mcp.run(transport="sse", host="127.0.0.1", port=9000)