"""Client-facing regression tests for SecureMCP policy denials."""

from __future__ import annotations

import pytest

from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.server.security.config import PolicyConfig, SecurityConfig
from securemcp import SecureMCP


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_tool_policy_denial_is_a_client_visible_error(mode: str) -> None:
    server = SecureMCP(
        "policy-denial",
        security=SecurityConfig(
            policy=PolicyConfig(
                policy_file={"type": "denylist", "denied": ["admin-reset"]}
            )
        ),
    )

    @server.tool(name="admin-reset")
    def admin_reset() -> str:
        return "reset"

    async with Client(server, mode=mode) as client:
        result = await client.call_tool(
            "admin-reset",
            {},
            raise_on_error=False,
        )

        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("admin-reset", {})

    assert result.is_error is True
    message = result.content[0].text
    assert "Policy violation (denylist-policy)" in message
    assert "matches denylist pattern 'admin-reset'" in message
    assert "Internal server error" not in message
    assert message in str(exc_info.value)
