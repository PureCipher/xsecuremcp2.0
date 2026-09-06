from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.ccpa_request import (
    CcpaConsumer,
    CcpaEvidence,
    CcpaRequestPolicy,
)
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustGrant,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config


def fixture(operation="use", recipient="internal"):
    now = datetime.now(timezone.utc)
    ctx = PolicyEvaluationContext(
        actor_id="client",
        action="call_tool",
        resource_id="consumer-tool",
        metadata={"arguments": {"consumer": "alice"}},
        timestamp=now,
    )
    consumer = CcpaConsumer(
        "alice",
        "16_plus",
        False,
        False,
        False,
        False,
        frozenset(
            {"current_preferences_verified", "rights_request_authority_verified"}
        ),
    )
    evidence = CcpaEvidence(
        issuer="verifier",
        scope_id="business/server",
        actor_id="client",
        action=ctx.action,
        resource_id=ctx.resource_id,
        request_digest=request_digest(ctx.metadata),
        verified_at=now,
        expires_at=now + timedelta(seconds=30),
        session_active=True,
        device_compliant=True,
        risk_acceptable=True,
        operation=operation,
        recipient_kind=recipient,
        purpose_basis="expected",
        sensitive_information=False,
        uses_admt=False,
        consumers=(consumer,),
        facts=frozenset(
            {
                "complete_consumer_and_field_scope_verified",
                "purpose_and_minimization_verified",
                "recipient_authorized",
                "security_and_output_controls_verified",
                "non_discrimination_verified",
                "applicable_risk_assessment_verified",
                "retention_permitted",
                "third_party_contract_verified",
                "processor_contract_verified",
                "processor_use_restrictions_verified",
                "notice_at_collection_verified",
                "restricted_identifiers_excluded",
                "correction_scope_verified",
                "deletion_scope_and_exceptions_verified",
            }
        ),
    )
    policy = CcpaRequestPolicy(
        grants=(ZeroTrustGrant("client", "consumer-tool", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="business/server",
    )
    return policy, replace(ctx, ccpa_evidence=evidence)


async def decision(policy, ctx, **changes):
    return (
        await policy.evaluate(
            replace(ctx, ccpa_evidence=replace(ctx.ccpa_evidence, **changes))
        )
    ).decision.value


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation,recipient",
    [
        ("use", "internal"),
        ("collect", "internal"),
        ("store", "internal"),
        ("disclose", "service_provider"),
        ("disclose", "contractor"),
        ("sell", "third_party"),
        ("share", "third_party"),
        ("consumer_access", "consumer"),
        ("correct", "internal"),
        ("delete", "internal"),
    ],
)
async def test_permitted_operations_and_config_persistence(operation, recipient):
    p, c = fixture(operation, recipient)
    config = policy_provider_to_config(p)
    assert config["type"] == "ccpa_request"
    restored = load_policy(config)
    assert isinstance(restored, CcpaRequestPolicy)
    assert await decision(restored, c) == "allow"


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["sell", "share"])
@pytest.mark.parametrize(
    "preference", ["sale_sharing_opt_out", "global_privacy_control"]
)
async def test_any_consumers_opt_out_blocks_whole_batch(operation, preference):
    p, c = fixture(operation, "third_party")
    opted_out = replace(
        c.ccpa_evidence.consumers[0], consumer_id="bob", **{preference: True}
    )
    assert (
        await decision(p, c, consumers=(*c.ccpa_evidence.consumers, opted_out))
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "age,consent",
    [
        ("under_13", "parental_sale_sharing_consent_verified"),
        ("13_to_15", "minor_sale_sharing_consent_verified"),
    ],
)
async def test_minors_require_specific_opt_in(age, consent):
    p, c = fixture("share", "third_party")
    consumer = replace(c.ccpa_evidence.consumers[0], age_band=age)
    assert await decision(p, c, consumers=(consumer,)) == "deny"
    consumer = replace(consumer, facts=consumer.facts | {consent})
    assert await decision(p, c, consumers=(consumer,)) == "allow"
    assert (
        await decision(
            p, c, consumers=(replace(consumer, global_privacy_control=True),)
        )
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"operation": "unknown"},
        {"recipient_kind": "unknown"},
        {"purpose_basis": "unknown"},
        {"sensitive_information": None},
        {"uses_admt": None},
        {"uses_admt": True},
        {"consumers": ()},
        {"consumers": []},
    ],
)
async def test_missing_or_unsupported_classification_denies(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "missing",
    [
        "complete_consumer_and_field_scope_verified",
        "purpose_and_minimization_verified",
        "recipient_authorized",
        "security_and_output_controls_verified",
        "non_discrimination_verified",
        "applicable_risk_assessment_verified",
        "retention_permitted",
    ],
)
async def test_required_facts_are_conjunctive(missing):
    p, c = fixture()
    assert await decision(p, c, facts=c.ccpa_evidence.facts - {missing}) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation,recipient,missing",
    [
        ("collect", "internal", "notice_at_collection_verified"),
        ("disclose", "service_provider", "processor_contract_verified"),
        ("disclose", "contractor", "processor_use_restrictions_verified"),
        ("share", "third_party", "third_party_contract_verified"),
        ("consumer_access", "consumer", "restricted_identifiers_excluded"),
        ("correct", "internal", "correction_scope_verified"),
        ("delete", "internal", "deletion_scope_and_exceptions_verified"),
    ],
)
async def test_operation_specific_safeguards(operation, recipient, missing):
    p, c = fixture(operation, recipient)
    assert await decision(p, c, facts=c.ccpa_evidence.facts - {missing}) == "deny"


@pytest.mark.anyio
async def test_sensitive_use_limit_and_consented_purpose_compose():
    p, c = fixture()
    consumer = replace(c.ccpa_evidence.consumers[0], sensitive_use_limited=True)
    assert (
        await decision(p, c, sensitive_information=True, consumers=(consumer,))
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            sensitive_information=True,
            consumers=(consumer,),
            facts=c.ccpa_evidence.facts | {"sensitive_permitted_purpose_verified"},
        )
        == "allow"
    )
    assert await decision(p, c, sensitive_information=True) == "deny"
    consumer = replace(
        consumer,
        sensitive_use_limited=False,
        facts=consumer.facts | {"sensitive_notice_or_consent_verified"},
    )
    assert (
        await decision(p, c, sensitive_information=True, consumers=(consumer,))
        == "allow"
    )
    assert (
        await decision(p, c, purpose_basis="consented", consumers=(consumer,)) == "deny"
    )
    consumer = replace(
        consumer, facts=consumer.facts | {"specific_informed_consent_verified"}
    )
    assert (
        await decision(p, c, purpose_basis="consented", consumers=(consumer,))
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["consumer_access", "correct", "delete"])
async def test_rights_actions_need_subject_authority(operation):
    p, c = fixture(operation, "consumer")
    consumer = replace(
        c.ccpa_evidence.consumers[0], facts=frozenset({"current_preferences_verified"})
    )
    assert await decision(p, c, consumers=(consumer,)) == "deny"


@pytest.mark.anyio
async def test_deletion_restriction_blocks_reuse_but_permits_verified_deletion():
    p, c = fixture()
    consumer = replace(c.ccpa_evidence.consumers[0], deletion_restricted=True)
    assert await decision(p, c, consumers=(consumer,)) == "deny"
    assert (
        await decision(
            p,
            c,
            operation="delete",
            consumers=(consumer,),
            facts=c.ccpa_evidence.facts - {"retention_permitted"},
        )
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"consumer_id": ""},
        {"global_privacy_control": "false"},
        {"sale_sharing_opt_out": None},
        {"age_band": "unknown"},
        {"facts": frozenset()},
    ],
)
async def test_ambiguous_consumer_status_cannot_allow_sale(changes):
    p, c = fixture("sell", "third_party")
    assert (
        await decision(
            p, c, consumers=(replace(c.ccpa_evidence.consumers[0], **changes),)
        )
        == "deny"
    )


@pytest.mark.anyio
async def test_duplicate_subject_and_processor_sale_and_wrong_access_recipient_deny():
    p, c = fixture()
    assert await decision(p, c, consumers=c.ccpa_evidence.consumers * 2) == "deny"
    assert (
        await decision(p, c, operation="sell", recipient_kind="service_provider")
        == "deny"
    )
    assert (
        await decision(p, c, operation="consumer_access", recipient_kind="third_party")
        == "deny"
    )


@pytest.mark.anyio
async def test_evidence_binding_expiry_spoofing_and_grants():
    p, c = fixture()
    for changes in [
        {"issuer": "attacker"},
        {"scope_id": "other"},
        {"actor_id": "other"},
        {"resource_id": "other"},
        {"action": "read_resource"},
        {"request_digest": "forged"},
        {"verified_at": c.timestamp - timedelta(minutes=2)},
        {"expires_at": c.timestamp},
        {"session_active": False},
    ]:
        assert await decision(p, c, **changes) == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"consumer": "bob"}}))
    ).decision.value == "deny"
    assert (
        await p.evaluate(
            replace(
                c,
                ccpa_evidence=None,
                metadata={"verified": True, "consumer_opt_out_verified": "false"},
            )
        )
    ).decision.value == "deny"
    assert await decision(replace(p, grants=()), c) == "deny"


@pytest.mark.anyio
async def test_middleware_resolver_and_outage():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine

    p, c = fixture()
    calls = []

    async def resolve(ctx):
        calls.append(ctx)
        if len(calls) > 1:
            raise RuntimeError("offline")
        return c.ccpa_evidence

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), ccpa_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(c, ccpa_evidence=None))
    ).decision.value == "allow"
    assert (await middleware._evaluate(c)).decision.value == "deny"


@pytest.mark.anyio
async def test_catalog_staging_preserves_sources():
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    staged = (
        await TestSecurityAPIGovernance()
        ._make_api()
        .stage_policy_bundle("ccpa-consumer-privacy")
    )
    assert staged["status"] == "imported"
    ref = staged["proposal"]["metadata"]["catalog_reference"]
    assert ref["pack_version"] == "2.0.0"
    assert "2026" in ref["regulation_reference"]
    assert ref["source_urls"]


@pytest.mark.anyio
async def test_malformed_facts_and_restricted_rights_request():
    p, c = fixture()
    assert await decision(p, c, facts=None) == "deny"
    consumer = replace(c.ccpa_evidence.consumers[0], facts=None)
    assert await decision(p, c, consumers=(consumer,)) == "deny"
    consumer = replace(c.ccpa_evidence.consumers[0], sensitive_use_limited=True)
    assert (
        await decision(
            p, c, operation="delete", sensitive_information=True, consumers=(consumer,)
        )
        == "allow"
    )


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
async def test_mcp_surfaces_require_exact_action_and_bound_evidence(action):
    p, c = fixture()
    c = replace(c, action=action, ccpa_evidence=replace(c.ccpa_evidence, action=action))
    assert await decision(p, c) == "deny"
    p = replace(
        p, grants=(ZeroTrustGrant("client", "consumer-tool", frozenset({action})),)
    )
    assert await decision(p, c) == "allow"
