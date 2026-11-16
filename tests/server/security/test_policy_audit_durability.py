"""Regression coverage for durable, denial-aware policy auditing."""

from __future__ import annotations

from fastmcp import Client
from fastmcp.server.security.config import (
    PolicyConfig,
    ProvenanceConfig,
    SecurityConfig,
)
from fastmcp.server.security.policy.audit import PolicyAuditLog
from fastmcp.server.security.policy.provider import PolicyDecision
from fastmcp.server.security.provenance.records import ProvenanceAction
from securemcp import SecureMCP


async def test_call_denial_survives_discovery_noise_and_reaches_provenance() -> None:
    audit = PolicyAuditLog(max_entries=10)
    server = SecureMCP(
        "durable-policy-audit",
        security=SecurityConfig(
            policy=PolicyConfig(
                policy_file={"type": "denylist", "denied": ["admin-reset"]},
                audit_log=audit,
            ),
            provenance=ProvenanceConfig(ledger_id="policy-denials"),
        ),
    )

    @server.tool(name="admin-reset")
    def admin_reset() -> str:
        return "reset"

    for index in range(19):

        @server.tool(name=f"tool-{index}")
        def routine_tool() -> str:
            return "ok"

    async with Client(server) as client:
        denied = await client.call_tool(
            "admin-reset",
            {},
            raise_on_error=False,
        )
        assert denied.is_error is True

        for _ in range(4):
            await client.list_tools()

    retained = audit.query(
        action="call_tool",
        resource_id="admin-reset",
        decision=PolicyDecision.DENY,
    )
    assert len(retained) == 1
    assert audit.size == audit.max_entries

    security_context = server.security_context
    assert security_context is not None
    ledger = security_context.provenance_ledger
    assert ledger is not None
    durable = ledger.get_records(
        action=ProvenanceAction.ACCESS_DENIED,
        resource_id="admin-reset",
    )
    assert len(durable) == 1
    assert durable[0].metadata["requested_action"] == "call_tool"
    assert ledger.verify_chain()
    assert ledger.verify_tree()
