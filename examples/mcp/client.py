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
            tools = await session.list_tools()
            print(tools)
            result = await session.call_tool("echo", {"msg": "Hello, world!"})
            print(result)


if __name__ == "__main__":
    import sys

    asyncio.run(main())
