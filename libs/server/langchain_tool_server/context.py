"""Tool execution context."""

from typing import Optional


class Context:
    """Context passed to tools during execution."""

    def __init__(self, token: Optional[str] = None):
        self.token = token
