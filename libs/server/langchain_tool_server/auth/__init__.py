from __future__ import annotations

import typing

from langchain_tool_server.auth import exceptions, types

AH = typing.TypeVar("AH", bound=types.Authenticator)


class Auth:
    """Add custom authentication and authorization management.

    The Auth class provides a unified system for handling authentication and
    authorization.

    ???+ example "Basic Usage"
        ```python
        from langchain_tool_server.auth import Auth

        my_auth = Auth()

        async def verify_token(token: str) -> str:
            # Verify token and return user_id
            # This would typically be a call to your auth server
            return "user_id"

        @auth.authenticate
        async def authenticate(authorization: str) -> str:
            # Verify token and return user_id
            result = await verify_token(authorization)
            if result != "user_id":
                raise Auth.exceptions.HTTPException(
                    status_code=401, detail="Unauthorized"
                )
            return result

    ???+ note "Request Processing Flow"
        Authentication (your `@auth.authenticate` handler) is performed first
        on **every request**
    """

    __slots__ = ("_authenticate_handler",)
    types = types
    """Reference to auth type definitions.

    Provides access to all type definitions used in the auth system,
    like ThreadsCreate, AssistantsRead, etc."""

    exceptions = exceptions
    """Reference to auth exception definitions.

    Provides access to all exception definitions used in the auth system,
    like HTTPException, etc.
    """

    def __init__(self) -> None:
        # These are accessed by the API. Changes to their names or types is
        # will be considered a breaking change.
        self._authenticate_handler: typing.Optional[types.Authenticator] = None

    def authenticate(self, fn: AH) -> AH:
        """Register an authentication handler function.

        The authentication handler is responsible for verifying credentials
        and returning user scopes. It can accept any of the following parameters
        by name:

            - request (Request): The raw ASGI request object
            - body (dict): The parsed request body
            - method (str): The HTTP method, e.g., "GET"
            - headers (dict[bytes, bytes]): Request headers
            - authorization (str | None): The Authorization header
                value (e.g., "Bearer <token>")

        Args:
            fn (Callable): The authentication handler function to register.
                Must return a representation of the user. This could be a:
                    - string (the user id)
                    - dict containing {"identity": str, "permissions": list[str]}
                    - or an object with identity and permissions properties
                Permissions can be optionally used by your handlers downstream.

        Returns:
            The registered handler function.

        Raises:
            ValueError: If an authentication handler is already registered.

        ???+ example "Examples"
            Basic token authentication:
            ```python
            @auth.authenticate
            async def authenticate(authorization: str) -> str:
                user_id = verify_token(authorization)
                return user_id
            ```

            Accept the full request context:
            ```python
            @auth.authenticate
            async def authenticate(
                method: str,
                path: str,
                headers: dict[bytes, bytes]
            ) -> str:
                user = await verify_request(method, path, headers)
                return user
            ```
        """
        if self._authenticate_handler is not None:
            raise ValueError(
                "Authentication handler already set as {self._authenticate_handler}."
            )
        self._authenticate_handler = fn
        return fn


__all__ = ["Auth", "types", "exceptions"]
