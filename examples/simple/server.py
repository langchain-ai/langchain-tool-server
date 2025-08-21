#!/usr/bin/env python
from langchain_tool_server import Server
from langchain_tool_server.auth import Auth
from langchain_tool_server.prebuilts import math
from langchain_core.tools import tool

app = Server()
auth = Auth()


@app.add_tool()
async def echo(msg: str) -> str:
    """Echo a message."""
    return msg + "!"


@app.add_tool()
async def say_hello() -> str:
    """Say hello."""
    return "Hello"

@tool(auth_provider='gmail', auth_scopes=['gmail.send', 'gmail.read'])
async def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail API."""
    return f"Email sent to {to} with subject '{subject}'"

@tool(auth_provider='slack')
async def send_slack_message(channel: str, message: str) -> str:
    """Send a message to a Slack channel."""
    return f"Message sent to {channel}: {message}"

app.add_tools(*math.TOOLS)
app.add_tools(send_email, send_slack_message)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("__main__:app", host="127.0.0.1", port=8002, reload=True)
