from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustEvidence,
    ZeroTrustGrant,
    ZeroTrustPolicy,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config


def fixture():
    now = datetime.now(timezone.utc)
    context = PolicyEvaluationContext(
        actor_id="client-1",
        action="call_tool",
        resource_id="student-search",
        metadata={"arguments": {"query": "allowed"}},
        timestamp=now,
    )
    evidence = ZeroTrustEvidence(
        "verifier",
        "tenant/server",
        "client-1",
        "call_tool",
        "student-search",
        request_digest(context.metadata),
        now,
        now + timedelta(seconds=30),
        True,
        True,
        True,
    )
    policy = ZeroTrustPolicy(
        grants=(
            ZeroTrustGrant("client-1", "student-search", frozenset({"call_tool"})),
        ),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="tenant/server",
    )
    return policy, replace(context, zero_trust_evidence=evidence)


@pytest.mark.anyio
async def test_exact_grant_and_serialization():
    policy, context = fixture()
    restored = load_policy(policy_provider_to_config(policy))
    assert isinstance(restored, ZeroTrustPolicy)
    assert (await restored.evaluate(context)).decision.value == "allow"
    assert (await ZeroTrustPolicy().evaluate(context)).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"actor_id": "admin"},
        {"resource_id": "tool:anything"},
        {"action": "delete"},
        {"metadata": {"role": "operator", "verified": "true"}},
        {"zero_trust_evidence": None},
    ],
)
async def test_no_implicit_privilege_or_argument_replay(change):
    policy, context = fixture()
    assert (await policy.evaluate(replace(context, **change))).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        {"scope_id": "other-tenant"},
        {"issuer": "untrusted"},
        {"actor_id": "other"},
        {"session_active": False},
        {"device_compliant": False},
        {"risk_acceptable": False},
        {"session_active": "true"},
    ],
)
async def test_bad_posture_or_identity_denies(change):
    policy, context = fixture()
    evidence = replace(context.zero_trust_evidence, **change)
    assert (
        await policy.evaluate(replace(context, zero_trust_evidence=evidence))
    ).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize("seconds", [-1, 30, 61])
async def test_evidence_time_boundaries(seconds):
    policy, context = fixture()
    assert (
        await policy.evaluate(
            replace(context, timestamp=context.timestamp + timedelta(seconds=seconds))
        )
    ).decision.value == "deny"


@pytest.mark.parametrize("resource", ["tool:*", "prefix?", "", "[abc]"])
def test_patterns_not_accepted(resource):
    with pytest.raises(ValueError):
        ZeroTrustGrant("client-1", resource, frozenset({"call_tool"}))


@pytest.mark.anyio
async def test_request_posture_rechecked_and_resolver_outage_denies():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine

    policy, context = fixture()
    calls = []

    async def resolve(request):
        calls.append(request)
        if len(calls) == 1:
            return context.zero_trust_evidence
        raise RuntimeError("unavailable")

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[policy]), zero_trust_evidence_resolver=resolve
    )
    assert (await middleware._evaluate(context)).decision.value == "allow"
    assert (await middleware._evaluate(context)).decision.value == "deny"
