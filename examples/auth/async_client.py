"""Example of using the async client to call universal-tool-server with auth."""

import asyncio

from universal_tool_client import get_async_client


async def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: uv run client.py url of universal-tool-server  (i.e. http://localhost:8080/)>"
        )
        sys.exit(1)

    url = sys.argv[1]

    print("\n--- Results for unauthenticated user ---\n")
    # A client with no credentials will get a 401
    client = get_async_client(url=url)

    try:
        print(await client.tools.list())
    except Exception as e:
        print(f"Error: {e}")

    print('\n--- Results for x-api-key="1" ---\n')
    # As some-user
    client = get_async_client(url=url, headers={"x-api-key": "1"})
    print("User: some-user has access to the following tools:")
    tools = await client.tools.list()
    for tool in tools:
        print(tool)
    # Call a tool
    who_am_i = await client.tools.call("who_am_i", {})
    print(f"Result of calling who_am_i: {who_am_i}")

    print('\n--- Results for x-api-key="2" ---\n')
    # As another-user
    client = get_async_client(url=url, headers={"x-api-key": "2"})
    print("User: another-user has access to the following tools:")
    for tool in await client.tools.list():
        print(tool)
    who_am_i = await client.tools.call("who_am_i", {})
    print(f"Result of calling who_am_i: {who_am_i}")


if __name__ == "__main__":
    import sys

    asyncio.run(main())
