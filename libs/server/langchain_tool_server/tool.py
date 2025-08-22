"""Custom tool decorator and base class."""

import os
from typing import Any, Callable, Optional, List


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
    
    async def _auth_hook(self) -> None:
        """Auth hook that runs before tool execution."""
        if self.auth_provider:
            print(f"Auth required for tool '{self.name}' - Provider: {self.auth_provider}, Scopes: {self.scopes}")
            
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
                print(f"Authentication successful for tool '{self.name}' - Token obtained {auth_result.token}")
                
            except ImportError:
                raise RuntimeError(f"Tool '{self.name}' requires auth but langchain-auth is not installed")
            except Exception as e:
                print(f"TEMP DEBUG - Full auth error details:")
                print(f"  Tool: {self.name}")
                print(f"  Provider: {self.auth_provider}")
                print(f"  Scopes: {self.scopes}")
                print(f"  Exception type: {type(e)}")
                print(f"  Exception message: {e}")
                print(f"  Exception args: {e.args}")
                raise RuntimeError(f"Authentication failed for tool '{self.name}': {e}")
        else:
            print(f"No auth required for tool '{self.name}'")
    
    async def __call__(self, *args, **kwargs) -> Any:
        """Call the tool function."""
        # Run auth hook before execution
        await self._auth_hook()
        
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