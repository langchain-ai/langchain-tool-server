from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from langchain_tool_server.tools import CallToolRequest, ToolHandler

MCP_APP_PREFIX = "/mcp"
PROTOCOL_VERSION = "2025-03-26"


class MCPSession:
    """Represents an MCP session for streamable HTTP transport."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.initialized = False
        self.capabilities = {"tools": {}}


class MCPStreamableHandler:
    """Handler for MCP streamable HTTP transport."""

    def __init__(self, tool_handler: ToolHandler):
        self.tool_handler = tool_handler
        self.sessions: Dict[str, MCPSession] = {}

    def create_session(self) -> str:
        """Create a new MCP session."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = MCPSession(session_id)
        return session_id

    def get_session(self, session_id: Optional[str]) -> MCPSession:
        """Get or create a session."""
        if not session_id or session_id not in self.sessions:
            session_id = self.create_session()
        return self.sessions[session_id]

    def create_response(
        self, request_id: Any, result: Any, session: Optional[MCPSession] = None
    ) -> JSONResponse:
        """Create a JSON-RPC response."""
        response_data = {"jsonrpc": "2.0", "id": request_id, "result": result}

        headers = {"Content-Type": "application/json"}
        if session:
            headers["Mcp-Session-Id"] = session.session_id

        return JSONResponse(response_data, headers=headers)

    def create_error(
        self,
        request_id: Any,
        code: int,
        message: str,
        session: Optional[MCPSession] = None,
    ) -> JSONResponse:
        """Create a JSON-RPC error response."""
        response_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

        headers = {"Content-Type": "application/json"}
        if session:
            headers["Mcp-Session-Id"] = session.session_id

        return JSONResponse(response_data, status_code=400, headers=headers)

    def convert_result_to_content(self, result: Any) -> list[dict]:
        """Convert tool result to MCP content format."""
        if result is None:
            return [{"type": "text", "text": ""}]

        if isinstance(result, str):
            return [{"type": "text", "text": result}]

        # Convert non-string results to JSON string
        try:
            result_str = json.dumps(result) if not isinstance(result, str) else result
        except Exception:
            result_str = str(result)

        return [{"type": "text", "text": result_str}]

    async def handle_initialize(self, session: MCPSession, body: dict) -> JSONResponse:
        """Handle MCP initialize request."""
        session.initialized = True

        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "serverInfo": {"name": "LangChain Tool Server", "version": "2.0.0"},
        }

        return self.create_response(body.get("id"), result, session)

    async def handle_tools_list(self, session: MCPSession, body: dict) -> JSONResponse:
        """Handle tools/list request."""
        tools = await self.tool_handler.list_tools(request=None)

        # Convert to MCP format - only return latest version of each tool
        tools_list = []
        seen_names = set()

        for tool in tools:
            tool_name = tool["name"]
            if tool_name not in seen_names:
                tools_list.append(
                    {
                        "name": tool_name,
                        "description": tool["description"],
                        "inputSchema": tool["input_schema"],
                    }
                )
                seen_names.add(tool_name)

        result = {"tools": tools_list}
        return self.create_response(body.get("id"), result, session)

    async def handle_tools_call(self, session: MCPSession, body: dict, request: Request) -> JSONResponse:
        """Handle tools/call request."""
        params = body.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        print(f"MCP tools/call: tool={tool_name}, args={arguments}")

        if not tool_name:
            return self.create_error(
                body.get("id"), -32602, "Invalid params: missing 'name' field", session
            )

        try:
            # Create call request
            call_tool_request: CallToolRequest = {
                "tool_id": tool_name,
                "input": arguments,
            }

            # Execute the tool
            response = await self.tool_handler.call_tool(
                call_tool_request, request=request
            )

            if not response["success"]:
                return self.create_error(
                    body.get("id"),
                    -32603,
                    f"Tool execution failed: {response.get('error', 'Unknown error')}",
                    session,
                )

            # Convert result to MCP content format
            content = self.convert_result_to_content(response["value"])

            result = {"content": content}
            return self.create_response(body.get("id"), result, session)

        except Exception as e:
            return self.create_error(
                body.get("id"), -32603, f"Tool execution failed: {str(e)}", session
            )


def create_mcp_router(tool_handler: ToolHandler) -> APIRouter:
    """Create a FastAPI router for MCP streamable HTTP transport."""

    router = APIRouter()
    handler = MCPStreamableHandler(tool_handler)

    @router.get("")
    async def mcp_get_handler(request: Request):
        """Handle GET requests - SSE not supported, only streamable HTTP."""
        from fastapi.responses import Response

        # Return 501 Not Implemented to indicate SSE is not supported
        return Response(
            status_code=501,
            content="SSE not supported - use streamable HTTP only",
            headers={"Content-Type": "text/plain"},
        )

    @router.delete("")
    async def mcp_delete_handler(request: Request):
        """Handle DELETE requests for session termination."""
        from fastapi.responses import Response

        session_id = request.headers.get("mcp-session-id")
        if session_id and session_id in handler.sessions:
            del handler.sessions[session_id]
        return Response(status_code=204)

    @router.post("")
    async def mcp_streamable_handler(request: Request) -> JSONResponse:
        """Single endpoint for all MCP streamable HTTP communication."""

        # Parse JSON body
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Get or create session
        session_id = request.headers.get("mcp-session-id")
        session = handler.get_session(session_id)

        # Handle different methods
        method = body.get("method")
        request_id = body.get("id")

        if method == "initialize":
            return await handler.handle_initialize(session, body)

        elif method == "notifications/initialized":
            # No response needed for notifications in streamable HTTP
            from fastapi.responses import Response

            headers = {"Mcp-Session-Id": session.session_id} if session else {}
            return Response(status_code=204, headers=headers)

        elif method == "tools/list":
            return await handler.handle_tools_list(session, body)

        elif method == "tools/call":
            return await handler.handle_tools_call(session, body, request)

        else:
            return handler.create_error(
                request_id, -32601, f"Method not found: {method}", session
            )

    return router
