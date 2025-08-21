"""Python SDK tests are directly in the server code."""


def test_attempt_import() -> None:
    """Simple test to just verify that the module can be imported."""
    from langchain_tool_client import (  # noqa: F401
        AsyncClient,
        SyncClient,
        get_async_client,
        get_sync_client,
    )
