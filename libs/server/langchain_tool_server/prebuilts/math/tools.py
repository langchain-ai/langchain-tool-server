from langchain_core.tools import tool


@tool
async def add(x: float, y: float) -> float:
    """Add two numbers together."""
    return x + y


@tool
async def subtract(x: float, y: float) -> float:
    """Subtract y from x."""
    return x - y


@tool
async def multiply(x: float, y: float) -> float:
    """Multiply two numbers together."""
    return x * y


@tool
async def divide(x: float, y: float) -> float:
    """Divide x by y."""
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y


TOOLS = [add, subtract, multiply, divide]
