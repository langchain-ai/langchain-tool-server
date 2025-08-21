"""MCP client to test talking with the MCP app using streamable HTTP"""

import asyncio

from mcp import ClientSession
import mcp.client.streamable_http as streamable_http


async def main():
    if len(sys.argv) < 2:
        print(
            "Usage: uv run client.py <URL of HTTP MCP server (i.e. http://localhost:8002/mcp)>"
        )
        sys.exit(1)

    url = sys.argv[1]

    if "mcp" not in url:
        raise ValueError("Use url format of [host]/mcp")

    async with streamable_http.streamablehttp_client(url=url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            
            print("Testing tools from multi-file server...")
            
            # Test math tool
            print("\n1. Testing factorial tool:")
            result = await session.call_tool("factorial", {"n": 5})
            print(f"factorial(5) = {result.content[0].text}")
            
            # Test text tool
            print("\n2. Testing reverse_text tool:")
            result = await session.call_tool("reverse_text", {"text": "Hello World"})
            print(f"reverse_text('Hello World') = {result.content[0].text}")
            
            # Test utility tool
            print("\n3. Testing ping tool:")
            result = await session.call_tool("ping", {})
            print(f"ping() = {result.content[0].text}")
            
            print("\nAll tools working successfully!")


if __name__ == "__main__":
    import sys

    asyncio.run(main())
