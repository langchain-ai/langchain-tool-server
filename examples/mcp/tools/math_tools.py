"""Mathematical tools for the MCP server"""

from langchain_core.tools import tool

@tool
async def add(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y

@tool
async def multiply(x: int, y: int) -> int:
    """Multiply two numbers together."""
    return x * y

@tool
async def power(base: int, exponent: int) -> int:
    """Raise a number to a power."""
    return base ** exponent

@tool
async def factorial(n: int) -> int:
    """Calculate the factorial of a number."""
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

# Export all tools for bulk registration
TOOLS = [add, multiply, power, factorial]