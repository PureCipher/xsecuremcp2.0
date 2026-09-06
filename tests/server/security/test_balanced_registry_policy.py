from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustEvidence,
    ZeroTrustPolicy,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config
from fastmcp.server.security.policy.workbench import get_policy_bundle


def fixture():
    bundle = get_policy_bundle("registry-balanced")
    assert bundle is not None
    config = {
        **bundle["providers"][0],
        "trusted_issuers": ["verifier"],
        "scope_id": "tenant/server",
        "grants": [
            {
                "actor_id": "client",
                "resource_id": "specific-tool",
                "actions": ["call_tool"],
            }
        ],
    }
    p = load_policy(config)
    assert isinstance(p, ZeroTrustPolicy)
    now = datetime.now(timezone.utc)
    c = PolicyEvaluationContext(
        actor_id="client",
        action="call_tool",
        resource_id="specific-tool",
        metadata={"arguments": {"record": "a"}},
        timestamp=now,
    )
    e = ZeroTrustEvidence(
        issuer="verifier",
        scope_id="tenant/server",
        actor_id="client",
        action=c.action,
        resource_id=c.resource_id,
        request_digest=request_digest(c.metadata),
        verified_at=now,
        expires_at=now + timedelta(seconds=30),
        session_active=True,
        device_compliant=True,
        risk_acceptable=True,
    )
    return p, replace(c, zero_trust_evidence=e)


@pytest.mark.anyio
async def test_catalog_default_denies_even_admin_role_claim():
    bundle = get_policy_bundle("registry-balanced")
    assert bundle is not None and bundle["pack_version"] == "2.0.0"
    assert [p["type"] for p in bundle["providers"]] == ["zero_trust", "rate_limit"]
    p = load_policy(bundle["providers"][0])
    assert isinstance(p, ZeroTrustPolicy)
    for role in ["viewer", "publisher", "reviewer", "admin"]:
        c = PolicyEvaluationContext(
            actor_id="client",
            action="call_tool",
            resource_id="tool:any",
            metadata={"role": role},
        )
        assert (await p.evaluate(c)).decision.value == "deny"


@pytest.mark.anyio
async def test_exact_grant_and_config_persistence():
    p, c = fixture()
    restored = load_policy(policy_provider_to_config(p))
    assert isinstance(restored, ZeroTrustPolicy)
    assert restored.policy_id == "registry-balanced-access"
    assert (await restored.evaluate(c)).decision.value == "allow"
    for change in [
        {"actor_id": "another"},
        {"resource_id": "another-tool"},
        {"action": "manage_policy"},
        {"metadata": {"arguments": {"record": "b"}}},
    ]:
        assert (await restored.evaluate(replace(c, **change))).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "attacker"},
        {"scope_id": "another-tenant"},
        {"session_active": False},
        {"device_compliant": False},
        {"risk_acceptable": False},
    ],
)
async def test_trusted_posture_is_required(changes):
    p, c = fixture()
    assert (
        await p.evaluate(
            replace(c, zero_trust_evidence=replace(c.zero_trust_evidence, **changes))
        )
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_catalog_staging_retains_version_and_does_not_activate():
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    api = TestSecurityAPIGovernance()._make_api()
    before = api.get_policy_status()["providers"]
    staged = await api.stage_policy_bundle("registry-balanced")
    assert staged["status"] == "imported"
    ref = staged["proposal"]["metadata"]["catalog_reference"]
    assert ref["pack_version"] == "2.0.0"
    assert "product policy" in ref["regulation_reference"]
    assert api.get_policy_status()["providers"] == before
