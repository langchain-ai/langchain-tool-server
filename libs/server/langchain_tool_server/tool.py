"""Custom tool decorator and base class."""

import os
import inspect
from typing import Any, Callable, Optional, List
import structlog
from pydantic import validate_arguments

from langchain_tool_server.context import Context

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
        
        # Generate JSON schemas using Pydantic (similar to LangChain Core)
        self.input_schema = self._generate_input_schema()
        self.output_schema = self._generate_output_schema()
    
    def _generate_input_schema(self) -> dict:
        """Generate input schema from function signature using Pydantic."""
        from pydantic import create_model
        
        sig = inspect.signature(self.func)
        
        # Build fields dict for create_model, excluding context parameter for auth tools
        fields = {}
        for name, param in sig.parameters.items():
            if self.auth_provider and name == 'context':
                continue
                
            # Use parameter annotation and default value
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
            default_value = param.default if param.default != inspect.Parameter.empty else ...
            
            fields[name] = (annotation, default_value)
        
        # Create Pydantic model from filtered fields
        InputModel = create_model('InputModel', **fields)
        return InputModel.model_json_schema()
    
    def _generate_output_schema(self) -> dict:
        """Generate output schema from function return type using Pydantic."""
        try:
            sig = inspect.signature(self.func)
            return_annotation = sig.return_annotation
            
            if return_annotation == inspect.Signature.empty:
                return {"type": "string"}
            
            # Create a simple Pydantic model with the return type
            from pydantic import create_model
            OutputModel = create_model('Output', result=(return_annotation, ...))
            return OutputModel.model_json_schema()['properties']['result']
        except Exception:
            return {"type": "string"}
    
    async def _auth_hook(self, user_id: str = None):
        """Auth hook that runs before tool execution.
        
        Args:
            user_id: User ID for authentication
            
        Returns:
            None if no auth required or auth successful
            Dict with auth_required=True and auth_url if auth needed
        """
        if not self.auth_provider:
            return None
        
        if not user_id:
            raise RuntimeError(f"Tool '{self.name}' requires auth but no user_id provided")
        
        logger.info("Auth required for tool", tool=self.name, provider=self.auth_provider, scopes=self.scopes, user_id=user_id)
        try:
            from langchain_auth import Client

            api_key = os.getenv("LANGSMITH_API_KEY")
            if not api_key:
                raise RuntimeError(f"Tool '{self.name}' requires auth but LANGSMITH_API_KEY environment variable not set")
            
            client = Client(api_key=api_key)
            auth_result = await client.authenticate(
                provider=self.auth_provider,
                scopes=self.scopes,
                user_id=user_id
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
                # Store the token in context for the tool to use
                self._context = Context(token=auth_result.token)
                return None
            
        except ImportError:
            raise RuntimeError(f"Tool '{self.name}' requires auth but langchain-auth is not installed")
        except Exception as e:
            raise RuntimeError(f"Authentication failed for tool '{self.name}': {e}")
    
    async def __call__(self, *args, user_id: str = None, **kwargs) -> Any:
        """Call the tool function."""
        # Run auth hook before execution
        auth_response = await self._auth_hook(user_id=user_id)
        
        # If auth is required, return the auth info instead of executing the tool
        if auth_response and auth_response.get("auth_required"):
            return auth_response
        
        # Auth successful or not required, execute the tool
        if hasattr(self.func, '__call__'):
            # For auth tools, always inject context as first argument
            if self.auth_provider:
                if hasattr(self, '_context'):
                    # Prepend context to args
                    args = (self._context,) + args
                else:
                    raise RuntimeError(f"Tool {self.name} requires auth but no context available")
            
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
        
        # Validation: if auth_provider is given, first parameter must be 'context: Context'
        if auth_provider:
            import inspect
            from typing import get_type_hints
            
            sig = inspect.signature(f)
            params = list(sig.parameters.keys())
            
            # Check parameter name
            if not params or params[0] != 'context':
                raise ValueError(f"Tool '{f.__name__}': Tools with auth_provider must have 'context' as their first parameter")
            
            # Check parameter type annotation
            try:
                type_hints = get_type_hints(f)
                if 'context' in type_hints:
                    context_type = type_hints['context']
                    if context_type != Context:
                        raise ValueError(f"Tool '{f.__name__}': The 'context' parameter must be typed as 'Context', got '{context_type}'")
                else:
                    raise ValueError(f"Tool '{f.__name__}': The 'context' parameter must have type annotation 'Context'")
            except Exception as e:
                raise ValueError(f"Tool '{f.__name__}': Error validating context parameter type: {e}")
        
        return Tool(f, auth_provider=auth_provider, scopes=scopes)
    
    # Handle both @tool and @tool() syntax
    if func is None:
        # Called as @tool(auth_provider="...", scopes=[...])
        return decorator
    else:
        # Called as @tool
        return decorator(func)