from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.soc2_request import (
    Soc2Evidence,
    Soc2RequestPolicy,
)
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustGrant,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config


def fixture(effects=frozenset({"read"}), classification="internal"):
    # Sunday, outside the old global weekday gate; ordinary reads remain valid.
    now = datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc)
    c = PolicyEvaluationContext(
        actor_id="client",
        action="call_tool",
        resource_id="tool",
        metadata={"arguments": {"record": "a"}},
        timestamp=now,
    )
    e = Soc2Evidence(
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
        effects=effects,
        data_classification=classification,
        third_party_recipient=False,
        facts=frozenset(
            {
                "complete_effect_and_data_scope_verified",
                "least_privilege_verified",
                "input_validation_verified",
                "audit_capture_available",
                "incident_containment_clear",
                "capacity_budget_reserved",
                "processing_integrity_controls_verified",
                "output_delivery_controls_verified",
                "retention_and_use_permitted",
            }
        ),
    )
    p = Soc2RequestPolicy(
        grants=(ZeroTrustGrant("client", "tool", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="tenant/server",
    )
    return p, replace(c, soc2_evidence=e)


async def decision(p, c, **changes):
    return (
        await p.evaluate(replace(c, soc2_evidence=replace(c.soc2_evidence, **changes)))
    ).decision.value


@pytest.mark.anyio
async def test_read_outside_change_window_and_configuration_reload():
    p, c = fixture()
    config = policy_provider_to_config(p)
    assert config["type"] == "soc2_request"
    restored = load_policy(config)
    assert isinstance(restored, Soc2RequestPolicy)
    assert await decision(restored, c) == "allow"
    assert await decision(replace(p, grants=()), c) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fact",
    [
        "complete_effect_and_data_scope_verified",
        "least_privilege_verified",
        "input_validation_verified",
        "audit_capture_available",
        "incident_containment_clear",
        "capacity_budget_reserved",
        "processing_integrity_controls_verified",
        "output_delivery_controls_verified",
        "retention_and_use_permitted",
    ],
)
async def test_each_common_control_is_required(fact):
    p, c = fixture()
    assert await decision(p, c, facts=c.soc2_evidence.facts - {fact}) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"effects": frozenset()},
        {"effects": frozenset({"read", "unknown"})},
        {"effects": ["read"]},
        {"data_classification": "unknown"},
        {"third_party_recipient": None},
        {"facts": None},
    ],
)
async def test_incomplete_classification_denies(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
async def test_personal_confidential_data_needs_both_controls():
    p, c = fixture(classification="confidential_personal")
    confidential = {
        "confidential_access_verified",
        "confidential_output_protection_verified",
    }
    privacy = {
        "privacy_purpose_verified",
        "privacy_choice_and_authority_verified",
        "personal_data_scope_verified",
    }
    assert await decision(p, c, facts=c.soc2_evidence.facts | confidential) == "deny"
    assert await decision(p, c, facts=c.soc2_evidence.facts | privacy) == "deny"
    assert (
        await decision(p, c, facts=c.soc2_evidence.facts | confidential | privacy)
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "missing",
    ["destination_authorized", "transfer_protection_verified", "export_scope_verified"],
)
async def test_read_plus_export_cannot_skip_export_checks(missing):
    p, c = fixture(frozenset({"read", "export"}))
    facts = c.soc2_evidence.facts | {
        "destination_authorized",
        "transfer_protection_verified",
        "export_scope_verified",
    }
    assert await decision(p, c, facts=facts) == "allow"
    assert await decision(p, c, facts=facts - {missing}) == "deny"


@pytest.mark.anyio
async def test_third_party_requires_verified_contract_even_without_export_label():
    p, c = fixture()
    assert await decision(p, c, third_party_recipient=True) == "deny"
    facts = c.soc2_evidence.facts | {
        "vendor_risk_and_contract_verified",
        "destination_authorized",
        "transfer_protection_verified",
    }
    assert await decision(p, c, third_party_recipient=True, facts=facts) == "allow"


@pytest.mark.anyio
@pytest.mark.parametrize("effect", ["write", "delete", "configure", "deploy"])
async def test_mutation_needs_recovery_and_scope(effect):
    p, c = fixture(frozenset({effect}))
    assert await decision(p, c) == "deny"
    facts = c.soc2_evidence.facts | {
        "mutation_scope_verified",
        "recovery_controls_verified",
        "disposal_scope_and_method_verified",
        "independent_change_authority_verified",
        "approved_change_scope_verified",
        "change_window_verified",
        "change_validation_verified",
    }
    assert await decision(p, c, facts=facts, change_approver_id="reviewer") == "allow"
    assert (
        await decision(
            p,
            c,
            facts=facts - {"recovery_controls_verified"},
            change_approver_id="reviewer",
        )
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "missing",
    [
        "independent_change_authority_verified",
        "approved_change_scope_verified",
        "change_window_verified",
        "change_validation_verified",
    ],
)
async def test_system_change_needs_each_approval_condition(missing):
    p, c = fixture(frozenset({"read", "configure"}))
    facts = c.soc2_evidence.facts | {
        "mutation_scope_verified",
        "recovery_controls_verified",
        "independent_change_authority_verified",
        "approved_change_scope_verified",
        "change_window_verified",
        "change_validation_verified",
    }
    assert await decision(p, c, facts=facts, change_approver_id="client") == "deny"
    assert await decision(p, c, facts=facts, change_approver_id="reviewer") == "allow"
    assert (
        await decision(p, c, facts=facts - {missing}, change_approver_id="reviewer")
        == "deny"
    )


@pytest.mark.anyio
async def test_delete_only_can_proceed_after_retention_expires_but_not_read_delete():
    p, c = fixture(frozenset({"delete"}))
    facts = (c.soc2_evidence.facts - {"retention_and_use_permitted"}) | {
        "mutation_scope_verified",
        "recovery_controls_verified",
        "disposal_scope_and_method_verified",
    }
    assert await decision(p, c, facts=facts) == "allow"
    assert (
        await decision(p, c, effects=frozenset({"read", "delete"}), facts=facts)
        == "deny"
    )


@pytest.mark.anyio
async def test_cross_tenant_expiry_and_client_assertions_denied():
    p, c = fixture()
    for changes in [
        {"issuer": "attacker"},
        {"scope_id": "other"},
        {"actor_id": "other"},
        {"resource_id": "other"},
        {"action": "get_prompt"},
        {"request_digest": "forged"},
        {"verified_at": c.timestamp - timedelta(seconds=61)},
        {"expires_at": c.timestamp},
        {"session_active": False},
    ]:
        assert await decision(p, c, **changes) == "deny"
    assert (
        await p.evaluate(
            replace(c, soc2_evidence=None, metadata={"role": "admin", "verified": True})
        )
    ).decision.value == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"record": "b"}}))
    ).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "action",
    [
        "read_resource",
        "get_prompt",
        "list_tools",
        "list_resources",
        "list_resource_templates",
        "list_prompts",
    ],
)
async def test_each_mcp_action_needs_exact_grant(action):
    p, c = fixture()
    c = replace(c, action=action, soc2_evidence=replace(c.soc2_evidence, action=action))
    assert await decision(p, c) == "deny"
    p = replace(p, grants=(ZeroTrustGrant("client", "tool", frozenset({action})),))
    assert await decision(p, c) == "allow"


@pytest.mark.anyio
async def test_resolver_outage_denies_and_catalog_preserves_sources():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    p, c = fixture()

    async def resolve(ctx):
        raise RuntimeError("unavailable")

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), soc2_evidence_resolver=resolve
    )
    assert (await middleware._evaluate(c)).decision.value == "deny"
    staged = (
        await TestSecurityAPIGovernance()
        ._make_api()
        .stage_policy_bundle("soc2-trust-services")
    )
    assert staged["status"] == "imported"
    ref = staged["proposal"]["metadata"]["catalog_reference"]
    assert ref["pack_version"] == "2.0.0"
    assert ref["source_urls"]


@pytest.mark.anyio
async def test_live_resolver_supplies_bound_evidence_and_missing_result_denies():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine

    p, c = fixture()
    calls = []

    async def resolve(ctx):
        calls.append(ctx)
        if len(calls) > 1:
            return None
        now = datetime.now(timezone.utc)
        return replace(
            c.soc2_evidence, verified_at=now, expires_at=now + timedelta(seconds=30)
        )

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), soc2_evidence_resolver=resolve
    )
    request = replace(c, soc2_evidence=None)
    assert (await middleware._evaluate(request)).decision.value == "allow"
    assert (await middleware._evaluate(request)).decision.value == "deny"
    assert calls == [request, request]
