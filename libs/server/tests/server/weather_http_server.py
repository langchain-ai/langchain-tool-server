#!/usr/bin/env python3
"""Weather MCP server using streamable HTTP transport for testing."""

import random
from typing import Literal
from fastmcp import FastMCP

# Create server
mcp = FastMCP("Weather API Server")


@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # Mock weather data for testing
    conditions = ["sunny", "cloudy", "rainy", "snowy"]
    return {
        "city": city,
        "temperature": random.randint(-10, 35),
        "condition": random.choice(conditions),
        "humidity": random.randint(30, 90),
        "wind_speed": random.randint(0, 25)
    }


@mcp.tool()
def get_forecast(city: str, days: int = 5) -> list:
    """Get weather forecast for a city."""
    if days < 1 or days > 7:
        raise ValueError("Days must be between 1 and 7")
    
    forecast = []
    conditions = ["sunny", "cloudy", "rainy", "snowy"]
    
    for day in range(days):
        forecast.append({
            "day": day + 1,
            "city": city,
            "high_temp": random.randint(15, 35),
            "low_temp": random.randint(-5, 15),
            "condition": random.choice(conditions),
            "chance_of_rain": random.randint(0, 100)
        })
    
    return forecast


@mcp.tool()
def convert_temperature(temp: float, from_unit: Literal["C", "F"], to_unit: Literal["C", "F"]) -> float:
    """Convert temperature between Celsius and Fahrenheit."""
    if from_unit == to_unit:
        return temp
    
    if from_unit == "C" and to_unit == "F":
        return (temp * 9/5) + 32
    elif from_unit == "F" and to_unit == "C":
        return (temp - 32) * 5/9
    else:
        raise ValueError("Invalid temperature units")


if __name__ == "__main__":
    # Run as streamable HTTP server on port 8000
    mcp.run(transport="http", host="127.0.0.1", port=8000, path="/mcp")