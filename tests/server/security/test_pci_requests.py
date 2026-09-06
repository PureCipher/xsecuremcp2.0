from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.pci_request import (
    PciEvidence,
    PciRequestPolicy,
)
from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustGrant,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config


def fixture(operation="display", elements=frozenset({"pan"})):
    now = datetime.now(timezone.utc)
    context = PolicyEvaluationContext(
        actor_id="client",
        action="call_tool",
        resource_id="payment-tool",
        metadata={"arguments": {"transaction_id": "fixture"}},
        timestamp=now,
    )
    evidence = PciEvidence(
        issuer="verifier",
        scope_id="merchant/server",
        actor_id="client",
        action=context.action,
        resource_id=context.resource_id,
        request_digest=request_digest(context.metadata),
        verified_at=now,
        expires_at=now + timedelta(seconds=30),
        session_active=True,
        device_compliant=True,
        risk_acceptable=True,
        operation=operation,
        data_elements=elements,
        authorization_stage="pre_authorization",
        pan_presentation="masked",
        exposes_sad_to_client=False,
        facts=frozenset(
            {
                "business_need_verified",
                "record_and_field_scope_matches",
                "recipient_authorized",
                "audit_data_protection_verified",
                "pan_masking_verified",
                "payment_authorization_scope_verified",
                "secure_deletion_scope_verified",
                "retention_permitted",
                "pan_storage_unreadable",
                "strong_cryptography_verified",
                "destination_authenticated",
            }
        ),
    )
    policy = PciRequestPolicy(
        grants=(ZeroTrustGrant("client", "payment-tool", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="merchant/server",
    )
    return policy, replace(context, pci_evidence=evidence)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation", ["display", "process", "transmit", "store", "delete"]
)
async def test_pan_operations_and_config_reload(operation):
    policy, context = fixture(operation)
    config = policy_provider_to_config(policy)
    assert config["type"] == "pci_request"
    restored = load_policy(config)
    assert isinstance(restored, PciRequestPolicy)
    assert (await restored.evaluate(context)).decision.value == "allow"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "element", ["track_data", "card_verification_code", "pin", "pin_block"]
)
@pytest.mark.parametrize("operation", ["display", "process", "transmit", "store"])
async def test_post_authorization_sad_denied_even_with_valid_role_and_encryption(
    element, operation
):
    policy, context = fixture(operation, frozenset({element}))
    context = replace(
        context,
        pci_evidence=replace(
            context.pci_evidence, authorization_stage="post_authorization"
        ),
    )
    assert (await policy.evaluate(context)).decision.value == "deny"


@pytest.mark.anyio
async def test_sad_deletion_remains_possible_after_authorization():
    policy, context = fixture("delete", frozenset({"card_verification_code"}))
    context = replace(
        context,
        pci_evidence=replace(
            context.pci_evidence, authorization_stage="post_authorization"
        ),
    )
    assert (await policy.evaluate(context)).decision.value == "allow"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation,missing",
    [
        ("display", "pan_masking_verified"),
        ("store", "pan_storage_unreadable"),
        ("store", "retention_permitted"),
        ("transmit", "strong_cryptography_verified"),
        ("transmit", "destination_authenticated"),
        ("process", "recipient_authorized"),
        ("delete", "secure_deletion_scope_verified"),
    ],
)
async def test_required_protections_cannot_be_waived(operation, missing):
    policy, context = fixture(operation)
    context = replace(
        context,
        pci_evidence=replace(
            context.pci_evidence, facts=context.pci_evidence.facts - {missing}
        ),
    )
    assert (await policy.evaluate(context)).decision.value == "deny"


@pytest.mark.anyio
async def test_full_pan_needs_separate_business_authority():
    policy, context = fixture()
    evidence = replace(context.pci_evidence, pan_presentation="full")
    assert (
        await policy.evaluate(replace(context, pci_evidence=evidence))
    ).decision.value == "deny"
    evidence = replace(
        evidence, facts=evidence.facts | {"full_pan_business_need_verified"}
    )
    assert (
        await policy.evaluate(replace(context, pci_evidence=evidence))
    ).decision.value == "allow"


@pytest.mark.anyio
async def test_sad_never_returned_to_agent_and_preauth_storage_requires_crypto():
    policy, context = fixture("store", frozenset({"card_verification_code"}))
    assert (await policy.evaluate(context)).decision.value == "allow"
    e = context.pci_evidence
    for changed in [
        replace(e, exposes_sad_to_client=True),
        replace(e, facts=e.facts - {"strong_cryptography_verified"}),
    ]:
        assert (
            await policy.evaluate(replace(context, pci_evidence=changed))
        ).decision.value == "deny"


@pytest.mark.anyio
async def test_forged_role_metadata_and_cross_merchant_evidence_denied():
    policy, context = fixture()
    assert (
        await policy.evaluate(
            replace(
                context,
                pci_evidence=None,
                metadata={"role": "admin", "processor_role": "payment_processor"},
            )
        )
    ).decision.value == "deny"
    assert (
        await policy.evaluate(
            replace(
                context, pci_evidence=replace(context.pci_evidence, scope_id="other")
            )
        )
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_pci_resolver_is_invoked_and_outage_denies():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine

    policy, context = fixture()
    calls = []

    async def resolve(request):
        calls.append(request)
        if len(calls) == 1:
            return context.pci_evidence
        raise RuntimeError("unavailable")

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[policy]), pci_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(context, pci_evidence=None))
    ).decision.value == "allow"
    assert (await middleware._evaluate(context)).decision.value == "deny"


@pytest.mark.anyio
async def test_pci_pack_can_be_staged_with_version_and_sources():
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    api = TestSecurityAPIGovernance()._make_api()
    staged = await api.stage_policy_bundle("pci-dss-cardholder-data")
    assert staged["status"] == "imported"
    reference = staged["proposal"]["metadata"]["catalog_reference"]
    assert reference["pack_version"] == "2.0.0"
    assert "4.0.1" in reference["regulation_reference"]
    assert reference["source_urls"]


@pytest.mark.anyio
async def test_mixed_pan_and_sad_does_not_bypass_sad_restriction():
    policy, context = fixture("display", frozenset({"pan", "card_verification_code"}))
    assert (await policy.evaluate(context)).decision.value == "deny"
