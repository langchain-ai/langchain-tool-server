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
    
    # Call the send_email tool with auth metadata
    print("Calling send_email tool...")
    result = await client.tools.call("send_email", {
        "to": "test@example.com",
        "subject": "Test Email", 
        "body": "This is a test email"
    })
    print(f"Result: {result}")


if __name__ == "__main__":
    import sys

    asyncio.run(main())
