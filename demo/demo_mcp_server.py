"""Lightweight demo MCP server for PureCipher registry integration testing."""

from __future__ import annotations

import math
import re
import uuid

from fastmcp import FastMCP

mcp = FastMCP("Demo MCP Tools")


@mcp.tool
def get_weather(city: str) -> dict:
    """Get current weather for a city (mock data for demo purposes)."""
    seed = sum(ord(c) for c in city.lower())
    temp = 15 + (seed % 25)
    conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "windy"]
    return {
        "city": city,
        "temperature_celsius": temp,
        "temperature_fahrenheit": round(temp * 9 / 5 + 32, 1),
        "conditions": conditions[seed % len(conditions)],
        "humidity_percent": 30 + (seed % 50),
        "wind_kph": 5 + (seed % 30),
    }


@mcp.tool
def calculate(expression: str) -> dict:
    """Evaluate a mathematical expression safely. Supports +, -, *, /, ^, %, parentheses."""
    if not re.match(r"^[\d\s\+\-\*/\(\)\.\^%]+$", expression):
        return {"error": "Invalid characters in expression", "expression": expression}
    try:
        sanitized = expression.replace("^", "**")
        result = eval(sanitized, {"__builtins__": {}}, {"math": math})  # noqa: S307
        return {"expression": expression, "result": round(result, 10)}
    except Exception as e:
        return {"error": str(e), "expression": expression}


@mcp.tool
def lookup_company(name: str) -> dict:
    """Look up company information (mock data for demo purposes)."""
    seed = sum(ord(c) for c in name.lower())
    industries = ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing"]
    cities = ["San Francisco", "New York", "London", "Tokyo", "Berlin"]
    return {
        "name": name,
        "industry": industries[seed % len(industries)],
        "employees": (seed % 50 + 1) * 1000,
        "founded": 1970 + (seed % 54),
        "headquarters": cities[seed % len(cities)],
        "stock_ticker": name[:4].upper(),
        "annual_revenue_usd": f"${(seed % 100 + 1) * 10}M",
    }


@mcp.tool
def generate_uuid() -> str:
    """Generate a random UUID v4."""
    return str(uuid.uuid4())


@mcp.tool
def echo(message: str) -> str:
    """Echo back the provided message. Useful for testing connectivity."""
    return message


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)
