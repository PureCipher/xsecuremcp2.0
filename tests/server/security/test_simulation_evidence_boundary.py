from datetime import datetime, timezone
from typing import Any

import pytest

from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.provider import AllowAllPolicy
from purecipher.registry import PureCipherRegistry
from tests.server.security.test_strict_change_policy import fixture


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["disabled", "allow", "evidence_required", "error"])
async def test_simulation_never_claims_runtime_readiness(kind):
    class BrokenEngine:
        async def evaluate(self, context):
            raise RuntimeError("unavailable")

    engine: Any = None
    if kind == "allow":
        engine = PolicyEngine(providers=[AllowAllPolicy()])
    elif kind == "evidence_required":
        provider, _ = fixture()
        engine = PolicyEngine(providers=[provider])
    elif kind == "error":
        engine = BrokenEngine()
    registry = PureCipherRegistry(signing_secret="simulation-boundary-test-secret")
    result = await registry._simulate_policy(
        engine,
        slug="client",
        action="call_tool",
        resource_id="specific-tool",
        metadata={"approved": True, "verified": True},
        tags=[],
        timestamp=datetime.now(timezone.utc),
    )
    assert result["evaluation_mode"] == "policy_engine_only"
    assert result["evidence_resolvers_invoked"] is False
    assert result["runtime_readiness_verified"] is False
    assert result["limitations"]
    expected = {
        "disabled": "allow",
        "allow": "allow",
        "evidence_required": "deny",
        "error": "error",
    }
    assert result["decision"] == expected[kind]
