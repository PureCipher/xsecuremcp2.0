from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.published_tools import (
    PublishedToolEvidence,
    PublishedToolsPolicy,
)
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustGrant,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config


def fixture():
    now = datetime.now(timezone.utc)
    c = PolicyEvaluationContext(
        actor_id="client",
        action="call_tool",
        resource_id="tool",
        metadata={"arguments": {"query": "example"}},
        timestamp=now,
    )
    e = PublishedToolEvidence(
        issuer="registry-verifier",
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
        listing_id="listing",
        listing_version="1.2.3",
        manifest_digest="a" * 64,
        publication_status="published",
        revoked=False,
        signature_valid=True,
        component_binding_verified=True,
        effects=frozenset({"read"}),
    )
    p = PublishedToolsPolicy(
        grants=(ZeroTrustGrant("client", "tool", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"registry-verifier"}),
        scope_id="tenant/server",
    )
    return p, replace(c, published_tool_evidence=e)


async def decision(p, c, **changes):
    return (
        await p.evaluate(
            replace(
                c, published_tool_evidence=replace(c.published_tool_evidence, **changes)
            )
        )
    ).decision.value


@pytest.mark.anyio
async def test_published_readonly_tool_and_config_reload():
    p, c = fixture()
    config = policy_provider_to_config(p)
    assert config["type"] == "published_tools"
    restored = load_policy(config)
    assert isinstance(restored, PublishedToolsPolicy)
    assert await decision(restored, c) == "allow"
    assert await decision(p, c, effects=frozenset({"compute"})) == "allow"
    assert await decision(replace(p, grants=()), c) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"publication_status": "draft"},
        {"publication_status": "pending"},
        {"publication_status": "suspended"},
        {"revoked": True},
        {"revoked": "false"},
        {"signature_valid": False},
        {"signature_valid": "true"},
        {"component_binding_verified": False},
        {"listing_id": ""},
        {"listing_version": ""},
        {"manifest_digest": ""},
        {"manifest_digest": "g" * 64},
        {"effects": frozenset()},
        {"effects": frozenset({"read", "write"})},
        {"effects": frozenset({"delete"})},
        {"effects": frozenset({"unknown"})},
    ],
)
async def test_unpublished_unverified_or_mutating_tools_deny(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "action",
    [
        "submit_listing",
        "review_listing",
        "manage_policy",
        "read_resource",
        "get_prompt",
        "unknown",
    ],
)
async def test_admin_and_non_tool_surfaces_deny_even_with_exact_grant(action):
    p, c = fixture()
    c = replace(
        c,
        action=action,
        published_tool_evidence=replace(c.published_tool_evidence, action=action),
    )
    p = replace(p, grants=(ZeroTrustGrant("client", "tool", frozenset({action})),))
    assert await decision(p, c) == "deny"


@pytest.mark.anyio
async def test_discovery_needs_published_safe_component_and_exact_grant():
    p, c = fixture()
    c = replace(
        c,
        action="list_tools",
        published_tool_evidence=replace(c.published_tool_evidence, action="list_tools"),
    )
    assert await decision(p, c) == "deny"
    p = replace(
        p, grants=(ZeroTrustGrant("client", "tool", frozenset({"list_tools"})),)
    )
    assert await decision(p, c) == "allow"
    assert await decision(p, c, publication_status="draft") == "deny"
    assert await decision(p, c, effects=frozenset({"write"})) == "deny"


@pytest.mark.anyio
async def test_untrusted_tags_and_cross_request_evidence_cannot_allow():
    p, c = fixture()
    forged = replace(
        c,
        published_tool_evidence=None,
        tags=frozenset({"published"}),
        metadata={"published": True, "readOnlyHint": True},
    )
    assert (await p.evaluate(forged)).decision.value == "deny"
    for changes in [
        {"issuer": "attacker"},
        {"scope_id": "other"},
        {"actor_id": "other"},
        {"resource_id": "other"},
        {"action": "list_tools"},
        {"request_digest": "forged"},
        {"verified_at": c.timestamp - timedelta(seconds=61)},
        {"expires_at": c.timestamp},
    ]:
        assert await decision(p, c, **changes) == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"query": "different"}}))
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_runtime_resolver_and_catalog_staging():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    p, c = fixture()
    calls = []

    async def resolve(ctx):
        calls.append(ctx)
        if len(calls) > 1:
            raise RuntimeError("registry unavailable")
        return c.published_tool_evidence

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), published_tool_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(c, published_tool_evidence=None))
    ).decision.value == "allow"
    assert (await middleware._evaluate(c)).decision.value == "deny"
    staged = (
        await TestSecurityAPIGovernance()
        ._make_api()
        .stage_policy_bundle("published-tools-only")
    )
    assert staged["status"] == "imported"
    ref = staged["proposal"]["metadata"]["catalog_reference"]
    assert ref["pack_version"] == "2.0.0"
    assert "product policy" in ref["regulation_reference"]
