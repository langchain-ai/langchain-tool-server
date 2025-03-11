#!/usr/bin/env python
import os

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from universal_tool_client import get_sync_client

if "ANTHROPIC_API_KEY" not in os.environ:
    raise ValueError("Please set ANTHROPIC_API_KEY in the environment.")

tool_server = get_sync_client(
    url="http://localhost:8002",
    # headers=... # If you enabled auth
)
# Get tool definitions from the server
tools = tool_server.tools.as_langchain_tools()
print("Loaded tools:", tools)

model = ChatAnthropic(model="claude-3-5-sonnet-20240620")
agent = create_react_agent(model, tools=tools)
print()

user_message = "What is the temperature in Paris?"
messages = agent.invoke({"messages": [{"role": "user", "content": user_message}]})[
    "messages"
]

for message in messages:
    message.pretty_print()
