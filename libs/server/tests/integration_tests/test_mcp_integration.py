#!/usr/bin/env python3
"""Test script for MCP server integration."""

import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_mcp_toolkit():
    """Test loading a toolkit with MCP servers configured."""
    from langchain_tool_server import Server

    # Test with the example MCP toolkit
    toolkit_path = Path(__file__).parent / "../toolkits/mcp_example"

    # Test sync toolkit loading
    sync_server = Server.from_toolkit(str(toolkit_path), enable_mcp=False)
    assert len(sync_server.tool_handler.catalog) == 2, f"Expected 2 native tools, got {len(sync_server.tool_handler.catalog)}"

    # Test async toolkit loading with MCP servers
    async_server = await Server.afrom_toolkit(str(toolkit_path), enable_mcp=False)
    
    # Should load native tools + MCP tools
    assert len(async_server.tool_handler.catalog) >= 2, f"Expected at least 2 tools, got {len(async_server.tool_handler.catalog)}"
    
    # Verify native tools are loaded
    assert "native_add" in async_server.tool_handler.catalog, "native_add tool not found"
    assert "native_multiply" in async_server.tool_handler.catalog, "native_multiply tool not found"
    
    # Verify math server tools (stdio transport)
    assert "math_server.add" in async_server.tool_handler.catalog, "math_server.add not found"
    assert "math_server.subtract" in async_server.tool_handler.catalog, "math_server.subtract not found"
    assert "math_server.multiply" in async_server.tool_handler.catalog, "math_server.multiply not found"
    assert "math_server.divide" in async_server.tool_handler.catalog, "math_server.divide not found"
    
    # Verify weather API tools (HTTP transport)
    assert "weather_api.get_weather" in async_server.tool_handler.catalog, "weather_api.get_weather not found"
    assert "weather_api.get_forecast" in async_server.tool_handler.catalog, "weather_api.get_forecast not found" 
    assert "weather_api.convert_temperature" in async_server.tool_handler.catalog, "weather_api.convert_temperature not found"
    
    # Test native tool execution
    native_request = {"tool_id": "native_add", "input": {"x": 5, "y": 3}}
    native_result = await async_server.tool_handler.call_tool(native_request, None)
    assert native_result["success"] == True, f"native_add failed: {native_result}"
    assert native_result["value"] == 8, f"Expected 8, got {native_result['value']}"
    
    # Test MCP tool execution - Math server (stdio)
    math_request = {"tool_id": "math_server.add", "input": {"x": 10, "y": 5}}
    math_result = await async_server.tool_handler.call_tool(math_request, None)
    assert math_result["success"] == True, f"math_server.add failed: {math_result}"
    assert int(math_result["value"]) == 15, f"Expected 15, got {math_result['value']}"
    
    # Test weather API tool (HTTP transport)
    weather_request = {"tool_id": "weather_api.get_weather", "input": {"city": "London"}}
    weather_result = await async_server.tool_handler.call_tool(weather_request, None)
    assert weather_result["success"] == True, f"weather_api.get_weather failed: {weather_result}"
    
    # Parse JSON string result (MCP tools often return JSON strings)
    import json
    if isinstance(weather_result["value"], str):
        weather_data = json.loads(weather_result["value"])
    else:
        weather_data = weather_result["value"]
    
    assert isinstance(weather_data, dict), f"Expected dict result, got {type(weather_data)}"
    assert "city" in weather_data, "Weather result missing 'city' field"
    assert weather_data["city"] == "London", f"Expected London, got {weather_data['city']}"


@pytest.mark.asyncio
async def test_basic_toolkit():
    """Test that existing toolkits still work."""
    from langchain_tool_server import Server

    # Test with the basic toolkit (no MCP servers)
    toolkit_path = Path(__file__).parent / "../toolkits/basic"

    # Test sync server
    sync_server = Server.from_toolkit(str(toolkit_path))
    assert len(sync_server.tool_handler.catalog) == 3, f"Expected 3 basic tools, got {len(sync_server.tool_handler.catalog)}"

    # Test async server (should be same for basic toolkit)
    async_server = await Server.afrom_toolkit(str(toolkit_path))
    assert len(async_server.tool_handler.catalog) == 3, f"Expected 3 basic tools, got {len(async_server.tool_handler.catalog)}"
    
    # Verify expected tools are present
    expected_tools = ["hello", "add", "test_auth_tool"]
    for tool_name in expected_tools:
        assert tool_name in sync_server.tool_handler.catalog, f"Missing tool: {tool_name}"
        assert tool_name in async_server.tool_handler.catalog, f"Missing tool in async server: {tool_name}"
    
    # Both servers should have identical tool catalogs for basic toolkit
    assert sync_server.tool_handler.catalog.keys() == async_server.tool_handler.catalog.keys(), "Sync and async servers have different tools"
