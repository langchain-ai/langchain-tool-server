from typing import Any, Awaitable, Callable, Dict, Union, cast

from fastapi import APIRouter, HTTPException
from fastapi.requests import Request
from jsonschema_rs import validator_for
from langchain_core.tools import BaseTool, InjectedToolArg
from langchain_core.tools import tool as tool_decorator
from langchain_core.utils.function_calling import convert_to_openai_function
from typing_extensions import TypedDict


class RegisteredTool(TypedDict):
    """A registered tool."""

    # Add ability to specify a unique ID for tools
    name: str
    """Name of the tool."""
    description: str
    """Description of the tool."""
    input_schema: Dict[str, Any]
    """Input schema of the tool."""
    fn: Callable[[Dict[str, Any]], Awaitable[Any]]
    """Function to call the tool."""
    permissions: set[str]
    """Scopes required to call the tool.

    If empty, not permissions are required and the tool is considered to be public.
    """
    accepts: list[tuple[str, Any]]
    """List of run time arguments that the fn accepts.

    For example, a signature like def foo(x: int, request: Request) -> str:`,

    would have an entry in the `accepts` list as ("request", Request).
    """


def _is_allowed(
    tool: RegisteredTool, request: Request | None, auth_enabled: bool
) -> bool:
    """Check if the tool is listable."""
    required_permissions = tool["permissions"]

    # If tool requests Request object, but one is not provided, then the tool is not
    # allowed.
    for _, type_ in tool["accepts"]:
        if type_ is Request and request is None:
            return False

    if not auth_enabled or not required_permissions:
        # Used to avoid request.auth attribute access raising an assertion errors
        # when no auth middleware is enabled..
        return True
    permissions = request.auth.scopes if hasattr(request, "auth") else set()
    return required_permissions.issubset(permissions)


class ToolHandler:
    def __init__(self) -> None:
        """Initializes the tool handler."""
        self.catalog: Dict[str, RegisteredTool] = {}
        self.auth_enabled = False

    def add(
        self, tool: Union[BaseTool, Callable], *, permissions: list[str] | None = None
    ) -> None:
        """Registers a tool in the catalog."""
        # If not already a BaseTool, we'll convert it to one using
        # the tool decorator.
        if not isinstance(tool, BaseTool):
            tool = tool_decorator(tool)

        if isinstance(tool, BaseTool):
            accepts = []
            from pydantic import BaseModel

            if not issubclass(tool.args_schema, BaseModel):
                raise NotImplementedError(
                    "Expected args_schema to be a Pydantic model. "
                    f"Got {type(tool.args_schema)}."
                    "This is not yet supported."
                )

            for name, field in tool.args_schema.model_fields.items():
                if field.annotation is Request:
                    accepts.append((name, Request))

            registered_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": convert_to_openai_function(tool)["parameters"],
                "fn": cast(Callable[[Dict[str, Any]], Awaitable[Any]], tool.ainvoke),
                "permissions": cast(set[str], set(permissions or [])),
                "accepts": accepts,
            }
        else:
            raise AssertionError("Reached unreachable code")

        if registered_tool["name"] in self.catalog:
            # Add unique ID to support duplicated tools?
            raise ValueError(f"Tool {registered_tool['name']} already exists")
        self.catalog[registered_tool["name"]] = registered_tool

    async def call_tool(
        self, name: str, args: Dict[str, Any], request: Request
    ) -> Awaitable[Any]:
        """Decorator to register a tool in the catalog."""
        if name not in self.catalog:
            raise HTTPException(status_code=404, detail=f"Tool {name} not found")

        tool = self.catalog[name]

        if not _is_allowed(tool, request, self.auth_enabled):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Validate and parse the payload according to the tool's input schema.
        fn = tool["fn"]

        injected_arguments = {}

        accepts = tool["accepts"]

        for name, field in accepts:
            if field is Request:
                injected_arguments[name] = request

        if isinstance(fn, Callable):
            payload_schema_ = tool["input_schema"]
            validator = validator_for(payload_schema_)
            if not validator.is_valid(args):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid payload for tool call to tool {name} "
                        f"with args {args} and schema {payload_schema_}",
                    ),
                )
            # Update the injected arguments post-validation
            args.update(injected_arguments)
            return await fn(args)
        else:
            # This is an internal error
            raise AssertionError(f"Invalid tool implementation: {type(fn)}")

    async def list_tools(self, request: Request | None) -> list[Dict[str, Any]]:
        """Lists all available tools in the catalog."""
        # Incorporate default permissions for the tools.
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"],
            }
            for tool in self.catalog.values()
            if _is_allowed(tool, request, self.auth_enabled)
        ]


class CallToolRequest(TypedDict):
    """Request to call a tool."""

    name: str
    """The name of the tool to call."""
    args: Dict[str, Any]
    """The arguments to pass to the tool."""


class Tool(TypedDict):
    """Response from a tool."""

    name: str
    """Name of the tool."""
    description: str
    """Description of the tool."""
    inputSchema: Dict[str, Any]
    """Input schema of the tool. This is a JSON schema."""


def create_tools_router(tool_handler: ToolHandler) -> APIRouter:
    """Creates an API router for tools."""
    router = APIRouter()

    @router.get("", operation_id="listTools")
    async def list_tools(request: Request) -> list[Tool]:
        """Lists available tools."""
        return await tool_handler.list_tools(request)

    @router.post("/call", operation_id="callTool")
    async def call_tool(call_tool_request: CallToolRequest, request: Request) -> Any:
        """Call a tool by name with the provided payload."""
        name = call_tool_request["name"]
        args = call_tool_request["args"]
        return await tool_handler.call_tool(name, args, request)

    return router


class InjectedRequest(InjectedToolArg):
    """Annotation for injecting the starlette request object.

    Example:
        ..code-block:: python

            from typing import Annotated
            from open_tool_server.server.tools import InjectedRequest
            from starlette.requests import Request

            @app.tool(permissions=["group1"])
            async def who_am_i(request: Annotated[Request, InjectedRequest]) -> str:
                \"\"\"Return the user's identity\"\"\"
                # The `user` attribute can be used to retrieve the user object.
                # This object corresponds to the return value of the authentication
                # function.
                return request.user.identity
    """
