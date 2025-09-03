"""Test auth module with tracking capabilities."""

from langchain_tool_server import Auth

# Global variable to track if auth was called
AUTH_WAS_CALLED = False
AUTH_CALL_COUNT = 0
LAST_HEADERS = None
LAST_AUTHORIZATION = None

auth = Auth()


@auth.authenticate
async def authenticate(headers: dict, authorization: str = None) -> dict:
    """Test auth handler that tracks when it's called."""
    global AUTH_WAS_CALLED, AUTH_CALL_COUNT, LAST_HEADERS, LAST_AUTHORIZATION

    AUTH_WAS_CALLED = True
    AUTH_CALL_COUNT += 1
    LAST_HEADERS = headers.copy() if headers else None
    LAST_AUTHORIZATION = authorization

    if not authorization or not authorization.startswith("Bearer "):
        raise auth.exceptions.HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )

    # For testing, accept any bearer token
    token = authorization.replace("Bearer ", "")

    return {
        "identity": f"test_user_{token}",
        "permissions": ["test"],
        "display_name": f"Test User {token}",
    }


def reset_auth_tracking():
    """Reset tracking variables for testing."""
    global AUTH_WAS_CALLED, AUTH_CALL_COUNT, LAST_HEADERS, LAST_AUTHORIZATION
    AUTH_WAS_CALLED = False
    AUTH_CALL_COUNT = 0
    LAST_HEADERS = None
    LAST_AUTHORIZATION = None
