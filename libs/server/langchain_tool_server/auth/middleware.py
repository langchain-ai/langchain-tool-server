import copy
import functools
import inspect
from collections.abc import Callable, Mapping
from typing import Any

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response

from langchain_tool_server.auth import Auth

SUPPORTED_PARAMETERS = {
    "request": Request,
    "body": dict,
    "user": BaseUser,
    "path": str,
    "method": str,
    "scopes": list[str],
    "path_params": dict[str, str] | None,
    "query_params": dict[str, str] | None,
    "headers": dict[str, bytes] | None,
    "authorization": str | None,
    "scope": dict[str, Any],
}


class ServerAuthenticationBackend(AuthenticationBackend):
    def __init__(
        self,
        auth: Auth,
    ) -> None:
        """Initializes the authentication backend."""
        self.auth = auth
        self._fn = None
        self._param_names = None

    @property
    def fn(self) -> Callable:
        if self._fn is None:
            fn = self.auth._authenticate_handler
            if not inspect.iscoroutinefunction(fn):
                self._fn = functools.partial(run_in_threadpool, fn)
            else:
                self._fn = fn
        return self._fn

    @property
    def param_names(self) -> set[str]:
        if self._param_names is None:
            self._param_names = (
                _get_named_arguments(self.fn, supported_params=SUPPORTED_PARAMETERS)
                if self.fn
                else None
            )
        return self._param_names

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        """Authenticate the request and return the user and permissions."""
        if self.fn is None:
            return None
        try:
            args = _extract_arguments_from_scope(
                conn.scope, self.param_names, request=Request(conn.scope)
            )
            response = await self.fn(**args)
            return _normalize_auth_response(response)
        except AuthenticationError:
            # Can be raised by the authentication handler and handled by the middleware
            raise
        except (Auth.exceptions.HTTPException, HTTPException) as e:
            # Needs to be translated to AuthenticationError to be handled by the
            # middleware.
            # Only translate 401 status code.
            if e.status_code == 401:
                raise AuthenticationError(e.detail) from None
            raise


def _extract_arguments_from_scope(
    scope: dict[str, Any],
    param_names: set[str],
    request: Request | None = None,
    response: Response | None = None,
) -> dict[str, Any]:
    """Extract requested arguments from the ASGI scope (and request/response if needed)."""

    auth = scope.get("auth")
    args: dict[str, Any] = {}
    if "scope" in param_names:
        args["scope"] = scope
    if "request" in param_names and request is not None:
        args["request"] = request
    if "response" in param_names and response is not None:
        args["response"] = response
    if "user" in param_names:
        user = scope.get("user")
        args["user"] = user
    if "scopes" in param_names:
        args["scopes"] = auth.scopes if auth else []
    if "path_params" in param_names:
        args["path_params"] = scope.get("path_params", {})
    if "path" in param_names:
        args["path"] = scope["path"]
    if "query_params" in param_names:
        args["query_params"] = scope.get("query_params", {})
    if "headers" in param_names:
        args["headers"] = dict(scope.get("headers", {}))
    if "authorization" in param_names:
        headers = dict(scope.get("headers", {}))
        authorization = headers.get(b"authorization") or headers.get(b"Authorization")
        if isinstance(authorization, bytes):
            authorization = authorization.decode(encoding="utf-8")
        args["authorization"] = authorization
    if "method" in param_names:
        args["method"] = scope.get("method")

    return args


class DotDict:
    def __init__(self, dictionary: dict[str, Any]):
        self._dict = dictionary
        for key, value in dictionary.items():
            if isinstance(value, dict):
                setattr(self, key, DotDict(value))
            else:
                setattr(self, key, value)

    def __getattr__(self, name):
        if name not in self._dict:
            raise AttributeError(f"'DotDict' object has no attribute '{name}'")
        return self._dict[name]

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        self._dict[key] = value
        if isinstance(value, dict):
            setattr(self, key, DotDict(value))
        else:
            setattr(self, key, value)

    def __deepcopy__(self, memo):
        return DotDict(copy.deepcopy(self._dict))

    def dict(self):
        return self._dict


class ProxyUser(BaseUser):
    """A proxy that wraps a user object to ensure it has all BaseUser properties.

    This will:
    1. Ensure the required identity property exists
    2. Provide defaults for optional properties if they don't exist
    3. Proxy all other attributes to the underlying user object
    """

    def __init__(self, user: Any):
        if not hasattr(user, "identity"):
            raise ValueError("User must have an identity property")
        self._user = user

    @property
    def identity(self) -> str:
        return self._user.identity

    @property
    def is_authenticated(self) -> bool:
        return getattr(self._user, "is_authenticated", True)

    @property
    def display_name(self) -> str:
        return getattr(self._user, "display_name", self.identity)

    def __deepcopy__(self, memo):
        return ProxyUser(copy.deepcopy(self._user))

    def model_dump(self):
        if hasattr(self._user, "model_dump") and callable(self._user.model_dump):
            return {
                "identity": self.identity,
                "is_authenticated": self.is_authenticated,
                "display_name": self.display_name,
                **self._user.model_dump(mode="json"),
            }
        return self.dict()

    def dict(self):
        d = (
            self._user.dict()
            if hasattr(self._user, "dict") and callable(self._user.dict)
            else {}
        )
        return {
            "identity": self.identity,
            "is_authenticated": self.is_authenticated,
            "display_name": self.display_name,
            **d,
        }

    def __getitem__(self, key):
        return self._user[key]

    def __setitem__(self, key, value):
        self._user[key] = value

    def __getattr__(self, name: str) -> Any:
        """Proxy any other attributes to the underlying user object."""
        return getattr(self._user, name)


class SimpleUser(ProxyUser):
    def __init__(self, username: str):
        super().__init__(DotDict({"identity": username}))


def _normalize_auth_response(
    response: Any,
) -> tuple[AuthCredentials, BaseUser]:
    if isinstance(response, tuple):
        if len(response) != 2:
            raise ValueError(
                f"Expected a tuple with two elements (permissions, user), got {len(response)}"
            )
        permissions, user = response
    elif hasattr(response, "permissions"):
        permissions = response.permissions
        user = response
    elif isinstance(response, dict | Mapping) and "permissions" in response:
        permissions = response["permissions"]
        user = response
    else:
        user = response
        permissions = []

    return AuthCredentials(permissions), normalize_user(user)


def normalize_user(user: Any) -> BaseUser:
    """Normalize user into a BaseUser instance."""
    if isinstance(user, BaseUser):
        return user
    if hasattr(user, "identity"):
        return ProxyUser(user)
    if isinstance(user, str):
        return SimpleUser(username=user)
    if isinstance(user, dict) and "identity" in user:
        return ProxyUser(DotDict(user))
    raise ValueError(
        f"Expected a BaseUser instance with required property: identity (str). "
        f"Optional properties are: is_authenticated (bool, defaults to True) and "
        f"display_name (str, defaults to identity). Got {type(user)} instead"
    )


def _get_named_arguments(fn: Callable, supported_params: dict) -> set[str]:
    """Get the named arguments that a function accepts, ensuring they're supported."""
    sig = inspect.signature(fn)
    # Check for unsupported required parameters
    unsupported = []
    for name, param in sig.parameters.items():
        if name not in supported_params and param.default is param.empty:
            unsupported.append(name)

    if unsupported:
        supported_str = "\n".join(
            f"  - {name} ({getattr(typ, '__name__', str(typ))})"
            for name, typ in supported_params.items()
        )
        raise ValueError(
            f"Handler has unsupported required parameters: {', '.join(unsupported)}.\n"
            f"Supported parameters are:\n{supported_str}"
        )

    return {p for p in sig.parameters if p in supported_params}


def on_auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
    """Handle authentication errors."""
    return JSONResponse({"error": str(exc)}, status_code=401)
