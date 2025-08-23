"""Custom tool decorator and base class."""

import os
from typing import Any, Callable, Optional, List
import structlog

logger = structlog.getLogger(__name__)


class Tool:
    """Simple tool class."""
    
    def __init__(
        self, 
        func: Callable, 
        auth_provider: Optional[str] = None, 
        scopes: Optional[List[str]] = None
    ):
        self.func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""
        self.auth_provider = auth_provider
        self.scopes = scopes or []
    
    async def _auth_hook(self):
        """Auth hook that runs before tool execution.
        
        Returns:
            None if no auth required or auth successful
            Dict with auth_required=True and auth_url if auth needed
        """
        if not self.auth_provider:
            return None
        
        logger.info("Auth required for tool", tool=self.name, provider=self.auth_provider, scopes=self.scopes)
        try:
            from langchain_auth import Client

            api_key = os.getenv("LANGSMITH_API_KEY")
            if not api_key:
                raise RuntimeError(f"Tool '{self.name}' requires auth but LANGSMITH_API_KEY environment variable not set")
            
            client = Client(api_key=api_key)
            auth_result = await client.authenticate(
                provider=self.auth_provider,
                scopes=self.scopes,
                user_id="TODO_HOW_SHOULD_USER_BE_CONFIGURED"
            )
            
            if auth_result.needs_auth:
                logger.info("OAuth flow required", tool=self.name, auth_url=auth_result.auth_url)
                return {
                    "auth_required": True,
                    "auth_url": auth_result.auth_url,
                    "auth_id": getattr(auth_result, 'auth_id', None)
                }
            else:
                logger.info("Authentication successful", tool=self.name)
                return None
            
        except ImportError:
            raise RuntimeError(f"Tool '{self.name}' requires auth but langchain-auth is not installed")
        except Exception as e:
            raise RuntimeError(f"Authentication failed for tool '{self.name}': {e}")
    
    async def __call__(self, *args, **kwargs) -> Any:
        """Call the tool function."""
        # Run auth hook before execution
        auth_response = await self._auth_hook()
        
        # If auth is required, return the auth info instead of executing the tool
        if auth_response and auth_response.get("auth_required"):
            return auth_response
        
        # Auth successful or not required, execute the tool
        if hasattr(self.func, '__call__'):
            result = self.func(*args, **kwargs)
            # Handle both sync and async functions
            if hasattr(result, '__await__'):
                return await result
            return result
        raise RuntimeError(f"Tool {self.name} is not callable")


def tool(
    func: Optional[Callable] = None, 
    *, 
    auth_provider: Optional[str] = None, 
    scopes: Optional[List[str]] = None
) -> Any:
    """Decorator to create a tool from a function.
    
    Args:
        func: The function to wrap
        auth_provider: Name of the auth provider required
        scopes: List of OAuth scopes required
    
    Usage:
        @tool
        def my_function():
            '''Description of my function'''
            return "result"
            
        @tool(auth_provider="google", scopes=["read", "write"])
        def authenticated_function():
            '''Function requiring auth'''
            return "authenticated result"
    """
    def decorator(f: Callable) -> Tool:
        # Validation: if auth_provider is given, scopes must be given with at least one scope
        if auth_provider and (not scopes or len(scopes) == 0):
            raise ValueError(f"Tool '{f.__name__}': If auth_provider is specified, scopes must be provided with at least one scope")
        
        return Tool(f, auth_provider=auth_provider, scopes=scopes)
    
    # Handle both @tool and @tool() syntax
    if func is None:
        # Called as @tool(auth_provider="...", scopes=[...])
        return decorator
    else:
        # Called as @tool
        return decorator(func)