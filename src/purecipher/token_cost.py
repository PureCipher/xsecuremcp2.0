"""Token cost estimation for MCP tool definitions."""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using chars/4 heuristic."""
    return max(1, len(text) // 4) if text else 0


def estimate_definition_tokens(manifest_dict: dict[str, Any]) -> int:
    """Estimate the context-window token cost of a tool's schema definition.

    This is the "idle cost" — tokens consumed on every LLM message just
    by having the tool connected, even when it's never called.
    """
    parts: list[str] = []
    for key in ("tool_name", "description"):
        val = manifest_dict.get(key)
        if val:
            parts.append(str(val))

    for key in ("permissions", "tags"):
        val = manifest_dict.get(key)
        if isinstance(val, list) and val:
            parts.append(json.dumps(val, separators=(",", ":")))

    for key in ("data_flows", "resource_access"):
        val = manifest_dict.get(key)
        if isinstance(val, list) and val:
            parts.append(json.dumps(val, separators=(",", ":"), default=str))

    input_schema = manifest_dict.get("input_schema")
    if isinstance(input_schema, dict):
        parts.append(json.dumps(input_schema, separators=(",", ":"), default=str))

    output_schema = manifest_dict.get("output_schema")
    if isinstance(output_schema, dict):
        parts.append(json.dumps(output_schema, separators=(",", ":"), default=str))

    return estimate_tokens(" ".join(parts))


def estimate_call_tokens(
    arguments: dict[str, Any] | str | None,
    result_content: Any = None,
) -> tuple[int, int]:
    """Estimate input and output tokens for a single tool call.

    Returns (input_tokens, output_tokens).
    """
    if isinstance(arguments, dict):
        input_text = json.dumps(arguments, separators=(",", ":"), default=str)
    elif isinstance(arguments, str):
        input_text = arguments
    else:
        input_text = ""

    if isinstance(result_content, str):
        output_text = result_content
    elif isinstance(result_content, dict):
        output_text = json.dumps(result_content, separators=(",", ":"), default=str)
    elif isinstance(result_content, list):
        pieces: list[str] = []
        for block in result_content:
            text = getattr(block, "text", None)
            if text:
                pieces.append(str(text))
            elif isinstance(block, dict) and block.get("text"):
                pieces.append(str(block["text"]))
            elif isinstance(block, str):
                pieces.append(block)
        output_text = " ".join(pieces)
    else:
        output_text = ""

    return estimate_tokens(input_text), estimate_tokens(output_text)
