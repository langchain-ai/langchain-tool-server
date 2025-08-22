"""Custom tool decorator and base class."""

from typing import Any, Callable


class Tool:
    """Simple tool class."""
    
    def __init__(self, func: Callable):
        self.func = func
        self.name = func.__name__
        self.description = func.__doc__ or ""
    
    async def __call__(self, *args, **kwargs) -> Any:
        """Call the tool function."""
        if hasattr(self.func, '__call__'):
            result = self.func(*args, **kwargs)
            # Handle both sync and async functions
            if hasattr(result, '__await__'):
                return await result
            return result
        raise RuntimeError(f"Tool {self.name} is not callable")


def tool(func: Callable) -> Tool:
    """Decorator to create a tool from a function.
    
    Usage:
        @tool
        def my_function():
            '''Description of my function'''
            return "result"
    """
    return Tool(func)