"""Authentication middleware decorator.

This module defines the core types used for authentication, authorization, and
request handling.

It includes user protocols, authentication contexts, and typed
dictionaries for various API operations.
"""

import functools
import sys
import typing
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

import typing_extensions

T = typing.TypeVar("T")


def _slotify(fn: T) -> T:
    """Add slots to a dataclass if supported."""
    if sys.version_info >= (3, 10):  # noqa: UP036
        return functools.partial(fn, slots=True)  # type: ignore
    return fn


dataclass = _slotify(dataclass)


@typing.runtime_checkable
class MinimalUser(typing.Protocol):
    """User objects must at least expose the identity property."""

    @property
    def identity(self) -> str:
        """The unique identifier for the user.

        This could be a username, email, or any other unique identifier used
        to distinguish between different users in the system.
        """
        ...


class MinimalUserDict(typing.TypedDict, total=False):
    """The dictionary representation of a user."""

    identity: typing_extensions.Required[str]
    """The required unique identifier for the user."""
    display_name: str
    """The typing.Optional display name for the user."""
    is_authenticated: bool
    """Whether the user is authenticated. Defaults to True."""
    permissions: Sequence[str]
    """A list of permissions associated with the user.

    You can use these in your `@auth.on` authorization logic to determine
    access permissions to different resources.
    """


@typing.runtime_checkable
class BaseUser(typing.Protocol):
    """The base ASGI user protocol"""

    @property
    def is_authenticated(self) -> bool:
        """Whether the user is authenticated."""
        ...

    @property
    def display_name(self) -> str:
        """The display name of the user."""
        ...

    @property
    def identity(self) -> str:
        """The unique identifier for the user."""
        ...

    @property
    def permissions(self) -> Sequence[str]:
        """The permissions associated with the user."""
        ...


Authenticator = Callable[
    ...,
    Awaitable[
        typing.Union[
            MinimalUser, str, BaseUser, MinimalUserDict, typing.Mapping[str, typing.Any]
        ],
    ],
]
"""Type for authentication functions.

An authenticator can return either:
1. A string (user_id)
2. A dict containing {"identity": str, "permissions": list[str]}
3. An object with identity and permissions properties

Permissions can be used downstream by your authorization logic to determine
access permissions to different resources.

The authenticate decorator will automatically inject any of the following parameters
by name if they are included in your function signature:

Parameters:
    request (Request): The raw ASGI request object
    body (dict): The parsed request body
    path (str): The request path
    method (str): The HTTP method (GET, POST, etc.)
    path_params (dict[str, str] | None): URL path parameters
    query_params (dict[str, str] | None): URL query parameters
    headers (dict[str, bytes] | None): Request headers
    authorization (str | None): The Authorization header value (e.g. "Bearer <token>")

???+ example "Examples"
    Basic authentication with token:
    ```python
    from langchain_tool_server.auth import Auth

    auth = Auth()

    @auth.authenticate
    async def authenticate1(authorization: str) -> Auth.types.MinimalUserDict:
        return await get_user(authorization)
    ```

    Authentication with multiple parameters:
    ```
    @auth.authenticate
    async def authenticate2(
        method: str,
        path: str,
        headers: dict[str, bytes]
    ) -> Auth.types.MinimalUserDict:
        # Custom auth logic using method, path and headers
        user = verify_request(method, path, headers)
        return user
    ```

    Accepting the raw ASGI request:
    ```python
    MY_SECRET = "my-secret-key"
    @auth.authenticate
    async def get_current_user(request: Request) -> Auth.types.MinimalUserDict:
        try:
            token = (request.headers.get("authorization") or "").split(" ", 1)[1]
            payload = jwt.decode(token, MY_SECRET, algorithms=["HS256"])
        except (IndexError, InvalidTokenError):
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.myauth-provider.com/auth/v1/user",
                headers={"Authorization": f"Bearer {MY_SECRET}"}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="User not found")

            user_data = response.json()
            return {
                "identity": user_data["id"],
                "display_name": user_data.get("name"),
                "permissions": user_data.get("permissions", []),
                "is_authenticated": True,
            }
    ```
"""
