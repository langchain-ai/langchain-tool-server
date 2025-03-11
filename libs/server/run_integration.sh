#!/usr/bin/bash
uv run uvicorn tests.integration.mcp_server:app --host localhost --port 8131 --reload & 
pid=$! 
trap "kill $pid" EXIT 
sleep 5  # wait a bit for the server to be fully up
uv run pytest tests/integration

