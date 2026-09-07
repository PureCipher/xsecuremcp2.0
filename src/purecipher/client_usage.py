"""Display-only estimates from persisted tool-call events; not a billing meter."""

from datetime import datetime, timedelta
from typing import Any


def is_tool_call(row: Any) -> bool:
    action = getattr(row, "action", None)
    return (
        getattr(action, "value", action) == "tool_called"
        and getattr(row, "resource_id", None) != "__list_tools__"
    )


def estimated_tokens(row: Any) -> dict[str, Any] | None:
    if not is_tool_call(row):
        return None
    metadata = getattr(row, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    values = [metadata.get(key) for key in ("input_tokens", "output_tokens")]
    if any(type(value) is not int or value < 0 for value in values):
        return None
    return {
        "input_tokens": values[0],
        "output_tokens": values[1],
        "total_tokens": sum(values),
        "measurement": "estimated",
        "method": "characters_divided_by_4",
    }


def summarize_token_usage(rows: list[Any], now: datetime) -> dict[str, Any]:
    calls = [
        row
        for row in rows
        if is_tool_call(row)
        and getattr(row, "timestamp", None) is not None
        and now - timedelta(hours=24) <= row.timestamp <= now
    ]
    estimates = [usage for row in calls if (usage := estimated_tokens(row)) is not None]
    # A missing measurement must not be represented as measured zero.
    known = bool(estimates) or not calls
    totals = {
        key: sum(item[key] for item in estimates) if known else None
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    return {
        **totals,
        "measurement": "estimated",
        "method": "characters_divided_by_4",
        "calls_with_usage": len(estimates),
        "calls_without_usage": len(calls) - len(estimates),
        "record_limit": 1000,
        "window_may_be_truncated": len(rows) >= 1000,
    }
