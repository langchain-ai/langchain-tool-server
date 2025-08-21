"""Text processing tools for the MCP server"""

from langchain_core.tools import tool

@tool
async def reverse_text(text: str) -> str:
    """Reverse the given text."""
    return text[::-1]

@tool
async def count_words(text: str) -> int:
    """Count the number of words in the text."""
    return len(text.split())

@tool
async def uppercase(text: str) -> str:
    """Convert text to uppercase."""
    return text.upper()

# Export all tools for bulk registration
TOOLS = [reverse_text, count_words, uppercase]