from __future__ import annotations

import asyncio
import logging
import sys
from importlib import metadata
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
)

import httpx
import orjson
from httpx._types import QueryParamTypes

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available.
    __version__ = ""

logger = logging.getLogger(__name__)

PROTOCOL = "urn:oxp:1.0"


def _get_headers(custom_headers: Optional[dict[str, str]]) -> dict[str, str]:
    """Combine api_key and custom user-provided headers."""
    custom_headers = custom_headers or {}
    headers = {
        "User-Agent": f"langchain-tool-sdk-py/{__version__}",
        **custom_headers,
    }
    return headers


def _decode_json(r: httpx.Response) -> Any:
    body = r.read()
    return orjson.loads(body if body else None)


def _encode_json(json: Any) -> tuple[dict[str, str], bytes]:
    body = orjson.dumps(
        json,
        _orjson_default,
        orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS,
    )
    content_length = str(len(body))
    content_type = "application/json"
    headers = {"Content-Length": content_length, "Content-Type": content_type}
    return headers, body


def _orjson_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump()
    elif hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    elif isinstance(obj, (set, frozenset)):
        return list(obj)
    else:
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def _aencode_json(json: Any) -> tuple[dict[str, str], bytes]:
    """Encode JSON."""
    if json is None:
        return {}, None
    body = await asyncio.get_running_loop().run_in_executor(
        None,
        orjson.dumps,
        json,
        _orjson_default,
        orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS,
    )
    content_length = str(len(body))
    content_type = "application/json"
    headers = {"Content-Length": content_length, "Content-Type": content_type}
    return headers, body


async def _adecode_json(r: httpx.Response) -> Any:
    """Decode JSON."""
    body = await r.aread()
    return (
        await asyncio.get_running_loop().run_in_executor(None, orjson.loads, body)
        if body
        else None
    )


class AsyncHttpClient:
    """Handle async requests to the LangGraph API.

    Adds additional error messaging & content handling above the
    provided httpx client.

    Attributes:
        client (httpx.AsyncClient): Underlying HTTPX async client.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get(self, path: str, *, params: Optional[QueryParamTypes] = None) -> Any:
        """Send a GET request."""
        r = await self.client.get(path, params=params)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = (await r.aread()).decode()
            if sys.version_info >= (3, 11):
                e.add_note(body)
            else:
                logger.error(f"Error from langchain-tool-server: {body}", exc_info=e)
            raise e
        return await _adecode_json(r)

    async def post(self, path: str, *, json: Optional[dict]) -> Any:
        """Send a POST request."""
        if json is not None:
            headers, content = await _aencode_json(json)
        else:
            headers, content = {}, b""
        r = await self.client.post(path, headers=headers, content=content)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = (await r.aread()).decode()
            if sys.version_info >= (3, 11):
                e.add_note(body)
            else:
                logger.error(f"Error from langchain-tool-server: {body}", exc_info=e)
            raise e
        return await _adecode_json(r)

    async def put(self, path: str, *, json: dict) -> Any:
        """Send a PUT request."""
        headers, content = await _aencode_json(json)
        r = await self.client.put(path, headers=headers, content=content)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = (await r.aread()).decode()
            if sys.version_info >= (3, 11):
                e.add_note(body)
            else:
                logger.error(f"Error from langchain-tool-server: {body}", exc_info=e)
            raise e
        return await _adecode_json(r)

    async def patch(self, path: str, *, json: dict) -> Any:
        """Send a PATCH request."""
        headers, content = await _aencode_json(json)
        r = await self.client.patch(path, headers=headers, content=content)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = (await r.aread()).decode()
            if sys.version_info >= (3, 11):
                e.add_note(body)
            else:
                logger.error(f"Error from langchain-tool-server: {body}", exc_info=e)
            raise e
        return await _adecode_json(r)

    async def delete(self, path: str, *, json: Optional[Any] = None) -> None:
        """Send a DELETE request."""
        r = await self.client.request("DELETE", path, json=json)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = (await r.aread()).decode()
            if sys.version_info >= (3, 11):
                e.add_note(body)
            else:
                logger.error(f"Error from langchain-tool-server: {body}", exc_info=e)
            raise e




############
# PUBLIC API


def get_client(
    url: Optional[str] = None,
    *,
    mcp: bool = True,
    headers: Optional[dict[str, str]] = None,
) -> "AsyncClientBase":
    """Get a client instance.

    Args:
        url: The URL of the tool server.
        mcp: Whether to use MCP protocol (True) or HTTP REST (False). Defaults to True.
        headers: Optional custom headers (only used for HTTP mode).

    Returns:
        AsyncClientBase: The client for accessing the tool server.
    """
    if url is None:
        url = "http://localhost:8000"
    
    if mcp:
        # For MCP, append /mcp to URL if not present
        mcp_url = url if url.endswith('/mcp') else f"{url}/mcp"
        return AsyncMCPClient(mcp_url)
    else:
        # HTTP mode
        transport = httpx.AsyncHTTPTransport(retries=5)
        client = httpx.AsyncClient(
            base_url=url,
            transport=transport,
            timeout=httpx.Timeout(connect=5, read=300, write=300, pool=5),
            headers=_get_headers(headers),
        )
        return AsyncHTTPClient(client)


class AsyncClientBase:
    """Base class for async clients."""
    
    async def info(self) -> Any:
        """Get server info."""
        raise NotImplementedError
    
    async def health(self) -> Any:
        """Check server health."""
        raise NotImplementedError


class AsyncHTTPClient(AsyncClientBase):
    """HTTP-based async client."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """Initialize the client."""
        self.http = AsyncHttpClient(client)
        self.tools = AsyncHTTPToolsClient(self.http)

    async def info(self) -> Any:
        return await self.http.get("/info")

    async def health(self) -> Any:
        return await self.http.get("/health")


class AsyncMCPClient(AsyncClientBase):
    """MCP-based async client."""
    
    def __init__(self, url: str) -> None:
        """Initialize the MCP client."""
        self.url = url
        self.tools = AsyncMCPToolsClient(url)
    
    async def info(self) -> Any:
        # MCP doesn't have info endpoint, return basic info
        return {"protocol": "mcp", "url": self.url}
    
    async def health(self) -> Any:
        # MCP health check by attempting connection
        try:
            from mcp import ClientSession
            async with await self.tools._create_session_context() as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class AsyncHTTPToolsClient:
    """HTTP Tools API."""

    def __init__(self, http: AsyncHttpClient) -> None:
        """Initialize the client."""
        self.http = http

    async def list(self) -> Any:
        """List tools."""
        return await self.http.get("/tools")

    async def call(
        self,
        tool_id: str,
        args: Dict[str, Any] | None = None,
        *,
        user_id: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> Any:
        """Call a tool."""
        payload = {"tool_id": tool_id}
        if args is not None:
            payload["input"] = args
        if user_id is not None:
            payload["user_id"] = user_id
        if call_id is not None:
            payload["call_id"] = call_id
        request = {"request": payload, "$schema": PROTOCOL}
        return await self.http.post("/tools/call", json=request)


class AsyncMCPToolsClient:
    """MCP Tools API."""
    
    def __init__(self, url: str) -> None:
        """Initialize the MCP client."""
        self.url = url
    
    async def _create_session_context(self, headers: Optional[Dict[str, str]] = None):
        """Create a new MCP session context for each operation."""
        try:
            import mcp.client.streamable_http as streamable_http
            from mcp import ClientSession
            
            # Pass custom headers if provided
            kwargs = {"url": self.url}
            if headers:
                kwargs["headers"] = headers
                
            return streamable_http.streamablehttp_client(**kwargs)
        except ImportError as e:
            raise ImportError(
                "To use MCP mode, you must have mcp installed. "
                "You can install it with `pip install mcp`."
            ) from e
    
    async def list(self) -> Any:
        """List tools via MCP."""
        from mcp import ClientSession
        async with await self._create_session_context() as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools_list = await session.list_tools()
                
                # Convert MCP format to our standard format
                return [
                    {
                        "id": tool.name,
                        "name": tool.name, 
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema.model_dump() if tool.inputSchema else {},
                        "output_schema": {}
                    }
                    for tool in tools_list.tools
                ]
    
    async def call(
        self,
        tool_id: str,
        args: Dict[str, Any] | None = None,
        *,
        user_id: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> Any:
        """Call a tool via MCP."""
        from mcp import ClientSession
        
        # Prepare headers with user_id if provided
        headers = {}
        if user_id is not None:
            headers["X-User-ID"] = user_id
            
        async with await self._create_session_context(headers if headers else None) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                if args is None:
                    args = {}
                    
                result = await session.call_tool(tool_id, args)
                
                # Convert MCP format to our standard format
                if result.content:
                    value = result.content[0].text if result.content[0].text else result.content[0]
                else:
                    value = None
                    
                return {
                    "success": not result.isError,
                    "value": value,
                    "execution_id": call_id or "mcp-call"
                }


__all__ = [
    "get_client",
    "AsyncClientBase", 
    "AsyncHTTPClient",
    "AsyncMCPClient",
]
