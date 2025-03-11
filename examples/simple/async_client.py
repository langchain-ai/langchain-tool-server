import asyncio

from universal_tool_client import get_async_client


async def main():
    if len(sys.argv) < 2:
        print(
            "Usage: uv run client.py url of universal-tool-server  (i.e. http://localhost:8080/)>"
        )
        sys.exit(1)

    url = sys.argv[1]
    client = get_async_client(url=url)
    # Check server status
    print(await client.ok())  # "OK"
    print(await client.info())  # Server version and other information

    # List tools
    print(await client.tools.list())  # List of tools
    # Call a tool
    print(await client.tools.call("add", {"x": 1, "y": 2}))  # 3

    # Get as langchain tools
    select_tools = ["echo", "add"]
    tools = await client.tools.as_langchain_tools(select_tools)
    # Async
    print(await tools[0].ainvoke({"msg": "Hello"}))  # "Hello!"
    print(await tools[1].ainvoke({"x": 1, "y": 3}))  # 4


if __name__ == "__main__":
    import sys

    asyncio.run(main())
