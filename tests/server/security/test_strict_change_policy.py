from dataclasses import replace
from datetime import timedelta

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.strict_change import (
    CHANGE_ACTIONS,
    MCP_ACTIONS,
    ChangeEvidence,
    StrictChangePolicy,
)
from fastmcp.server.security.policy.policies.zero_trust import ZeroTrustGrant
from fastmcp.server.security.policy.serialization import policy_provider_to_config
from tests.server.security.test_balanced_registry_policy import fixture as base_fixture

FACTS = frozenset(
    {
        "complete_effect_and_target_scope_verified",
        "audit_capture_available",
        "approver_authority_verified",
        "separation_of_duties_verified",
        "approved_change_scope_verified",
        "change_validation_verified",
        "recovery_controls_verified",
    }
)


def fixture():
    p, c = base_fixture()
    e = ChangeEvidence(
        **vars(c.zero_trust_evidence),
        effects=frozenset({"write"}),
        facts=FACTS,
        approval_id="approval-1",
        requester_id="requester",
        approver_id="approver",
        approval_request_digest=c.zero_trust_evidence.request_digest,
        approval_action=c.action,
        approval_resource_id=c.resource_id,
        approval_revoked=False,
        approval_issued_at=c.timestamp - timedelta(seconds=10),
        approval_expires_at=c.timestamp + timedelta(seconds=30),
        window_start=c.timestamp,
        window_end=c.timestamp + timedelta(seconds=30),
    )
    return StrictChangePolicy(
        grants=p.grants,
        trusted_issuers=p.trusted_issuers,
        scope_id=p.scope_id,
        max_evidence_age_seconds=p.max_evidence_age_seconds,
    ), replace(c, change_evidence=e)


async def decision(p, c, **changes):
    return (
        await p.evaluate(
            replace(c, change_evidence=replace(c.change_evidence, **changes))
        )
    ).decision.value


@pytest.mark.anyio
async def test_exact_change_and_config_reload():
    p, c = fixture()
    config = policy_provider_to_config(p)
    assert config["type"] == "strict_change"
    restored = load_policy(config)
    assert isinstance(restored, StrictChangePolicy)
    assert await decision(restored, c) == "allow"
    assert await decision(replace(p, grants=()), c) == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"record": "other"}}))
    ).decision.value == "deny"
    assert (
        await p.evaluate(
            replace(
                c,
                change_evidence=None,
                metadata={"role": "admin", "approval_granted": True},
            )
        )
    ).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"effects": frozenset()},
        {"effects": frozenset({"unknown"})},
        {"approval_id": ""},
        {"requester_id": ""},
        {"approver_id": ""},
        {"approver_id": "client"},
        {"approver_id": "requester"},
        {"approval_revoked": True},
        {"approval_revoked": "false"},
        {"approval_request_digest": "wrong"},
        {"approval_action": "read_resource"},
        {"approval_resource_id": "other"},
        {"approval_issued_at": None},
        {"window_end": None},
        {"issuer": "attacker"},
        {"scope_id": "other"},
        {"actor_id": "other"},
        {"request_digest": "wrong"},
        {"session_active": False},
        {"risk_acceptable": False},
        {"device_compliant": False},
    ],
)
async def test_invalid_evidence_denied(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize("fact", sorted(FACTS))
async def test_each_fact_required(fact):
    p, c = fixture()
    assert await decision(p, c, facts=FACTS - {fact}) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field", ["approval_issued_at", "approval_expires_at", "window_start", "window_end"]
)
async def test_window_and_approval_times(field):
    p, c = fixture()
    assert await decision(p, c, **{field: c.timestamp.replace(tzinfo=None)}) == "deny"
    invalid = (
        c.timestamp + timedelta(seconds=1)
        if field in {"approval_issued_at", "window_start"}
        else c.timestamp
    )
    assert await decision(p, c, **{field: invalid}) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize("action", sorted(MCP_ACTIONS | CHANGE_ACTIONS | {"unknown"}))
async def test_read_and_change_action_boundaries(action):
    p, c = fixture()
    p = replace(
        p, grants=(ZeroTrustGrant(c.actor_id, c.resource_id, frozenset({action})),)
    )
    c = replace(
        c,
        action=action,
        change_evidence=replace(
            c.change_evidence, action=action, approval_action=action
        ),
    )
    expected = "deny" if action == "unknown" else "allow"
    assert await decision(p, c) == expected
    expected_read = "allow" if action in MCP_ACTIONS else "deny"
    assert (
        await decision(
            p, c, effects=frozenset({"read"}), approval_id="", window_start=None
        )
        == expected_read
    )
    assert (
        await decision(p, c, effects=frozenset({"read", "write"}), approval_id="")
        == "deny"
    )


@pytest.mark.anyio
async def test_runtime_resolver_and_staging():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    p, c = fixture()

    async def resolve(ctx):
        return c.change_evidence

    async def outage(ctx):
        raise RuntimeError("unavailable")

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), change_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(c, change_evidence=None))
    ).decision.value == "allow"
    middleware.change_evidence_resolver = outage
    assert (await middleware._evaluate(c)).decision.value == "deny"
    middleware.change_evidence_resolver = None
    assert (
        await middleware._evaluate(replace(c, change_evidence=None))
    ).decision.value == "deny"
    api = TestSecurityAPIGovernance()._make_api()
    before = api.get_policy_status()["providers"]
    staged = await api.stage_policy_bundle("registry-strict-change-control")
    assert staged["status"] == "imported"
    assert (
        staged["proposal"]["metadata"]["catalog_reference"]["pack_version"] == "2.0.0"
    )
    assert api.get_policy_status()["providers"] == before
