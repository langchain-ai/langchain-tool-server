import uuid
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Literal,
    Union,
    cast,
)

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing_extensions import NotRequired, TypedDict

from langchain_tool_server.tool import Tool


class RegisteredTool(TypedDict):
    """A registered tool."""

    id: str
    """Unique identifier for the tool."""
    name: str
    """Name of the tool."""
    description: str
    """Description of the tool."""
    input_schema: Dict[str, Any]
    """Input schema of the tool."""
    output_schema: Dict[str, Any]
    """Output schema of the tool."""
    fn: Callable
    """Function to call the tool."""
    permissions: set[str]
    """Scopes required to call the tool.

    If empty, not permissions are required and the tool is considered to be public.
    """
    metadata: NotRequired[Dict[str, Any]]
    """Optional metadata associated with the tool."""


def _is_allowed(
    tool: RegisteredTool, request: Request | None, auth_enabled: bool
) -> bool:
    """Check if the request has required permissions to see / use the tool."""
    required_permissions = tool["permissions"]

    if not auth_enabled or not required_permissions:
        # Used to avoid request.auth attribute access raising an assertion errors
        # when no auth middleware is enabled..
        return True
    permissions = request.auth.scopes if hasattr(request, "auth") else set()
    return required_permissions.issubset(permissions)


class CallToolRequest(TypedDict):
    """Request to call a tool."""

    tool_id: str
    """An unique identifier for the tool to call."""
    input: NotRequired[Dict[str, Any]]
    """The input to pass to the tool."""
    execution_id: NotRequired[str]
    """Execution ID."""
    user_id: NotRequired[str]
    """User ID for tools requiring authentication."""


# Not using `class` syntax b/c $schema is not a valid attribute name.
class CallToolFullRequest(BaseModel):
    """Full request to call a tool."""

    # The protocol schema will temporarily allow otc://1.0 for backwards compatibility.
    # This is expected to be removed in the near future as it is not part of the
    # official spec.
    protocol_schema: Union[Literal["urn:oxp:1.0"], str] = Field(
        default="urn:oxp:1.0",
        description="Protocol version.",
        alias="$schema",
    )
    request: CallToolRequest = Field(..., description="Request to call a tool.")


class ToolError(TypedDict):
    """Error message from the tool."""

    message: str
    """Error message for the user or AI model."""
    developer_message: NotRequired[str]
    """Internal error message for logging/debugging."""
    can_retry: NotRequired[bool]
    """Indicates whether the tool call can be retried."""
    additional_prompt_content: NotRequired[str]
    """Extra content to include in a retry prompt."""
    retry_after_ms: NotRequired[int]
    """Time in milliseconds to wait before retrying."""


class ToolException(Exception):
    """An exception that can be raised by a tool."""

    def __init__(
        self,
        *,
        user_message: str = "",
        developer_message: str = "",
        can_retry: bool = False,
        additional_prompt_content: str = "",
        retry_after_ms: int = 0,
    ) -> None:
        """Initializes the tool exception."""
        self.message = user_message
        self.developer_message = developer_message
        self.can_retry = can_retry
        self.additional_prompt_content = additional_prompt_content
        self.retry_after_ms = retry_after_ms


class CallToolResponse(TypedDict):
    """Response from a tool execution."""

    execution_id: str
    """A unique ID for the execution"""

    success: bool
    """Whether the execution was successful."""

    value: NotRequired[Any]
    """The output of the tool execution."""

    error: NotRequired[ToolError]
    """Error message from the tool."""


class ToolDefinition(TypedDict):
    """Used in the response of the list tools endpoint."""

    id: str
    """Unique identifier for the tool."""

    name: str
    """The name of the tool."""

    description: str
    """A human-readable explanation of the tool's purpose."""

    input_schema: Dict[str, Any]
    """The input schema of the tool. This is a JSON schema."""

    output_schema: Dict[str, Any]
    """The output schema of the tool. This is a JSON schema."""


class AuthRequirementsRequest(BaseModel):
    """Request to get auth requirements for tools."""

    tool_names: list[str] = Field(..., description="List of tool names to check auth requirements for.")


class ToolHandler:
    def __init__(self) -> None:
        """Initializes the tool handler."""
        self.catalog: Dict[str, RegisteredTool] = {}
        self.auth_enabled = False


    def add(
        self,
        tool: Tool,
        *,
        permissions: list[str] | None = None,
    ) -> None:
        """Register a tool in the catalog.

        Args:
            tool: A Tool instance (created with @tool decorator).
            permissions: Permissions required to call the tool.
        """
        if not isinstance(tool, Tool):
            # Try to get the function name for a better error message
            func_name = getattr(tool, "__name__", "unknown")
            raise TypeError(
                f"Function '{func_name}' must be decorated with @tool decorator. "
                f"Got {type(tool)}.\n"
                f"Change:\n"
                f"  def {func_name}(...):\n"
                f"To:\n"
                f"  @tool\n"
                f"  def {func_name}(...):"
            )

        registered_tool = {
            "id": tool.name,
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "fn": tool,
            "permissions": cast(set[str], set(permissions or [])),
            "metadata": {},
        }

        if registered_tool["id"] in self.catalog:
            raise ValueError(f"Tool {registered_tool['id']} already exists")
        self.catalog[registered_tool["id"]] = registered_tool

    async def call_tool(
        self, call_tool_request: CallToolRequest, request: Request | None
    ) -> CallToolResponse:
        """Calls a tool by name with the provided payload."""
        tool_id = call_tool_request["tool_id"]
        args = call_tool_request.get("input", {})
        execution_id = call_tool_request.get("execution_id", uuid.uuid4())
        
        # Extract user_id from authenticated user context (set by auth middleware)
        user_id = None
        if self.auth_enabled and request and hasattr(request, 'user'):
            user_id = getattr(request.user, 'identity', None)

        if tool_id not in self.catalog:
            if self.auth_enabled:
                raise HTTPException(
                    status_code=403,
                    detail="Tool either does not exist or insufficient permissions",
                )

            raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

        tool = self.catalog[tool_id]

        if not _is_allowed(tool, request, self.auth_enabled):
            raise HTTPException(
                status_code=403,
                detail="Tool either does not exist or insufficient permissions",
            )

        # Call the tool
        fn = tool["fn"]

        if isinstance(fn, Tool):
            # Call our custom Tool instance (it handles auth hook internally)
            # Pass user_id for auth tools
            tool_output = await fn(user_id=user_id, **args)
        else:
            # This is an internal error
            raise AssertionError(f"Invalid tool implementation: {type(fn)}")

        return {"success": True, "execution_id": str(execution_id), "value": tool_output}

    async def list_tools(self, request: Request | None) -> list[ToolDefinition]:
        """Lists all available tools in the catalog."""
        # Incorporate default permissions for the tools.
        tool_definitions = []

        for tool in self.catalog.values():
            if _is_allowed(tool, request, self.auth_enabled):
                tool_definition = {
                    "id": tool["id"],
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"],
                    "output_schema": tool["output_schema"],
                }

                tool_definitions.append(tool_definition)

        return tool_definitions

    async def get_auth_requirements(
        self, tool_names: list[str], request: Request | None
    ) -> Dict[str, list[str]]:
        """Get consolidated authentication requirements for specified tools.
        
        Returns a dict mapping auth provider names to lists of required scopes.
        Raises HTTPException if any tool doesn't exist or user lacks permission.
        """
        provider_scopes: Dict[str, set[str]] = {}
        
        for tool_name in tool_names:
            if tool_name not in self.catalog:
                if self.auth_enabled:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Tool '{tool_name}' either does not exist or insufficient permissions",
                    )
                raise HTTPException(
                    status_code=404, 
                    detail=f"Tool '{tool_name}' not found"
                )
                
            tool = self.catalog[tool_name]

            if not _is_allowed(tool, request, self.auth_enabled):
                raise HTTPException(
                    status_code=403,
                    detail=f"Tool '{tool_name}' either does not exist or insufficient permissions",
                )
                
            # Check if this is a Tool instance with auth requirements
            tool_fn = tool["fn"]
            if hasattr(tool_fn, "auth_provider") and tool_fn.auth_provider:
                provider = tool_fn.auth_provider
                scopes = tool_fn.scopes or []
                
                if provider not in provider_scopes:
                    provider_scopes[provider] = set()
                
                # Add all scopes for this provider (automatically deduplicates)
                provider_scopes[provider].update(scopes)
        return {provider: list(scopes) for provider, scopes in provider_scopes.items()}


class ValidationErrorResponse(TypedDict):
    """Validation error response."""

    message: str


def create_tools_router(tool_handler: ToolHandler) -> APIRouter:
    """Creates an API router for tools."""
    router = APIRouter()

    @router.get(
        "",
        operation_id="list-tools",
        responses={
            200: {"model": list[ToolDefinition]},
            422: {"model": ValidationErrorResponse},
        },
    )
    async def list_tools(request: Request) -> list[ToolDefinition]:
        """Lists available tools."""
        return await tool_handler.list_tools(request)

    @router.post("/call", operation_id="call-tool")
    async def call_tool(
        call_tool_request: CallToolFullRequest, request: Request
    ) -> CallToolResponse:
        """Call a tool by name with the provided payload."""
        if call_tool_request.protocol_schema not in {"urn:oxp:1.0", "otc://1.0"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid protocol schema. Expected 'urn:oxp:1.0'.",
            )
        return await tool_handler.call_tool(call_tool_request.request, request)

    @router.post("/auth-requirements", operation_id="get-auth-requirements")
    async def get_auth_requirements(
        auth_request: AuthRequirementsRequest, request: Request
    ) -> Dict[str, list[str]]:
        """Get consolidated authentication requirements for specified tools."""
        return await tool_handler.get_auth_requirements(auth_request.tool_names, request)

    return router


class InjectedRequest:
    """Annotation for injecting the starlette request object.

    Example:
        ..code-block:: python

            from typing import Annotated
            from langchain_tool_server.server.tools import InjectedRequest
            from starlette.requests import Request

            @app.tool(permissions=["group1"])
            async def who_am_i(request: Annotated[Request, InjectedRequest]) -> str:
                \"\"\"Return the user's identity\"\"\"
                # The `user` attribute can be used to retrieve the user object.
                # This object corresponds to the return value of the authentication
                # function.
                return request.user.identity
    """


logger = structlog.getLogger(__name__)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Exception translation for validation errors.

    This will match the shape of the error response to the one implemented by
    the tool calling spec.
    """
    msg = ", ".join(str(e) for e in exc.errors())
    if exc.body:
        msg = f"{exc.body}: {msg}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"message": msg}),
    )
