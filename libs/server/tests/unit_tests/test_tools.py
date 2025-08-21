from typing import Any

from langchain_core.tools import tool
from typing_extensions import TypedDict

from langchain_tool_server.tools import get_output_schema


async def test_get_output_schema() -> None:
    """Test get output schema."""

    @tool
    def another_tool() -> str:
        """Hello"""

    assert get_output_schema(another_tool) == {"type": "string"}

    @tool
    async def async_another_tool() -> str:
        """Hello"""

    assert get_output_schema(async_another_tool) == {"type": "string"}

    class Foo(TypedDict):
        bar: str

    @tool
    def call_tool() -> Foo:
        """Hello"""
        pass

    assert get_output_schema(call_tool) == {
        "properties": {"bar": {"title": "Bar", "type": "string"}},
        "required": ["bar"],
        "title": "Foo",
        "type": "object",
    }

    @tool
    def void_tool() -> None:
        """Hello"""
        pass

    assert get_output_schema(void_tool) == {"type": "null"}

    @tool
    def any_tool() -> Any:
        """Hello"""
        pass

    assert get_output_schema(any_tool) == {}

    # Unspecified return type (same as Any)
    @tool
    def unspecified_tool():
        """Hello"""
        pass

    assert get_output_schema(unspecified_tool) == {}
