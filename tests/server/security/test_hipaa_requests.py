from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.hipaa_request import (
    HipaaEvidence,
    HipaaPatient,
    HipaaRequestPolicy,
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
        resource_id="records",
        metadata={"arguments": {"patient": "alice"}},
        timestamp=now,
    )
    patient = HipaaPatient(
        "alice",
        "treatment",
        False,
        False,
        frozenset(
            {"current_patient_status_verified", "basis_treatment_conditions_verified"}
        ),
    )
    e = HipaaEvidence(
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
        effects=frozenset({"use"}),
        data_categories=frozenset({"phi"}),
        recipient_kind="internal",
        actor_business_associate=False,
        marketing=False,
        sale_of_phi=False,
        minimum_necessary_mode="required",
        patients=(patient,),
        facts=frozenset(
            {
                "complete_patient_field_and_effect_scope_verified",
                "identity_and_recipient_authority_verified",
                "permitted_purpose_scope_verified",
                "security_and_output_controls_verified",
                "audit_and_accounting_controls_verified",
                "applicable_additional_law_verified",
                "minimum_necessary_scope_verified",
            }
        ),
    )
    p = HipaaRequestPolicy(
        grants=(ZeroTrustGrant("client", "records", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="tenant/server",
    )
    return p, replace(c, hipaa_evidence=e)


async def decision(p, c, **changes):
    return (
        await p.evaluate(
            replace(c, hipaa_evidence=replace(c.hipaa_evidence, **changes))
        )
    ).decision.value


@pytest.mark.anyio
@pytest.mark.parametrize(
    "basis",
    [
        "treatment",
        "payment",
        "operations",
        "individual",
        "authorization",
        "directory",
        "care_involvement",
        "required_law",
        "public_health",
        "abuse_reporting",
        "health_oversight",
        "judicial",
        "law_enforcement",
        "decedents",
        "organ_donation",
        "research",
        "serious_threat",
        "special_government",
        "workers_compensation",
        "limited_data_set",
        "hhs_enforcement",
        "administrative_simplification",
    ],
)
async def test_each_ground_requires_verified_conditions(basis):
    p, c = fixture()
    patient = replace(
        c.hipaa_evidence.patients[0],
        disclosure_basis=basis,
        facts=frozenset(
            {
                "current_patient_status_verified",
                "valid_current_authorization_verified",
                "individual_or_representative_authority_verified",
                "limited_data_set_fields_verified",
                "data_use_agreement_verified",
            }
        ),
    )
    recipient = "individual" if basis == "individual" else "internal"
    assert await decision(p, c, patients=(patient,), recipient_kind=recipient) == "deny"
    patient = replace(
        patient, facts=patient.facts | {"basis_" + basis + "_conditions_verified"}
    )
    assert (
        await decision(p, c, patients=(patient,), recipient_kind=recipient) == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fact",
    [
        "complete_patient_field_and_effect_scope_verified",
        "identity_and_recipient_authority_verified",
        "permitted_purpose_scope_verified",
        "security_and_output_controls_verified",
        "audit_and_accounting_controls_verified",
        "applicable_additional_law_verified",
        "minimum_necessary_scope_verified",
    ],
)
async def test_common_safeguards_are_conjunctive(fact):
    p, c = fixture()
    assert await decision(p, c, facts=c.hipaa_evidence.facts - {fact}) == "deny"


@pytest.mark.anyio
async def test_treatment_exception_does_not_exempt_internal_use_or_payment():
    p, c = fixture()
    facts = (c.hipaa_evidence.facts - {"minimum_necessary_scope_verified"}) | {
        "minimum_necessary_exception_scope_verified",
        "provider_treatment_exchange_verified",
        "destination_authorized",
        "transmission_safeguards_verified",
    }
    assert (
        await decision(p, c, minimum_necessary_mode="treatment_disclosure", facts=facts)
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            effects=frozenset({"disclose"}),
            minimum_necessary_mode="treatment_disclosure",
            facts=facts,
        )
        == "allow"
    )
    payment = replace(
        c.hipaa_evidence.patients[0],
        disclosure_basis="payment",
        facts=frozenset(
            {"current_patient_status_verified", "basis_payment_conditions_verified"}
        ),
    )
    assert (
        await decision(
            p,
            c,
            effects=frozenset({"disclose"}),
            patients=(payment,),
            minimum_necessary_mode="treatment_disclosure",
            facts=facts,
        )
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            effects=frozenset({"disclose", "use"}),
            minimum_necessary_mode="treatment_disclosure",
            facts=facts,
        )
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mode,basis",
    [
        ("individual", "individual"),
        ("authorization", "authorization"),
        ("required_law", "required_law"),
        ("hhs", "hhs_enforcement"),
        ("administrative", "administrative_simplification"),
    ],
)
async def test_other_minimum_necessary_exceptions_need_matching_basis(mode, basis):
    p, c = fixture()
    patient = replace(
        c.hipaa_evidence.patients[0],
        disclosure_basis=basis,
        facts=frozenset(
            {
                "current_patient_status_verified",
                "basis_" + basis + "_conditions_verified",
                "valid_current_authorization_verified",
                "individual_or_representative_authority_verified",
            }
        ),
    )
    facts = c.hipaa_evidence.facts - {"minimum_necessary_scope_verified"}
    recipient = "individual" if basis == "individual" else "internal"
    assert (
        await decision(
            p,
            c,
            patients=(patient,),
            recipient_kind=recipient,
            minimum_necessary_mode=mode,
            facts=facts,
        )
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            patients=(patient,),
            recipient_kind=recipient,
            minimum_necessary_mode=mode,
            facts=facts | {"minimum_necessary_exception_scope_verified"},
        )
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes,scope",
    [
        ({"marketing": True}, "marketing_authorization_scope_verified"),
        ({"sale_of_phi": True}, "sale_authorization_remuneration_verified"),
        (
            {"data_categories": frozenset({"phi", "psychotherapy_notes"})},
            "psychotherapy_authorization_scope_verified",
        ),
    ],
)
async def test_sensitive_authorization_cannot_be_bypassed_by_treatment(changes, scope):
    p, c = fixture()
    patient = c.hipaa_evidence.patients[0]
    assert await decision(p, c, **changes) == "deny"
    patient = replace(
        patient, facts=patient.facts | {"valid_current_authorization_verified"}
    )
    assert await decision(p, c, patients=(patient,), **changes) == "deny"
    patient = replace(patient, facts=patient.facts | {scope})
    assert await decision(p, c, patients=(patient,), **changes) == "allow"
    assert (
        await decision(
            p, c, patients=(replace(patient, authorization_revoked=True),), **changes
        )
        == "deny"
    )


@pytest.mark.anyio
async def test_one_restricted_patient_blocks_batch():
    p, c = fixture()
    patient = replace(
        c.hipaa_evidence.patients[0], patient_id="bob", request_restricted=True
    )
    assert (
        await decision(p, c, patients=(*c.hipaa_evidence.patients, patient)) == "deny"
    )


@pytest.mark.anyio
async def test_business_associate_actor_and_recipient_need_distinct_agreements():
    p, c = fixture()
    assert await decision(p, c, actor_business_associate=True) == "deny"
    assert await decision(p, c, recipient_kind="business_associate") == "deny"
    facts = c.hipaa_evidence.facts | {"actor_baa_and_instructions_verified"}
    assert await decision(p, c, actor_business_associate=True, facts=facts) == "allow"
    assert (
        await decision(
            p,
            c,
            actor_business_associate=True,
            recipient_kind="business_associate",
            facts=facts,
        )
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            actor_business_associate=True,
            recipient_kind="business_associate",
            facts=facts | {"recipient_baa_and_scope_verified"},
        )
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "effect,facts",
    [
        ("disclose", {"destination_authorized", "transmission_safeguards_verified"}),
        ("request", {"destination_authorized", "transmission_safeguards_verified"}),
        ("store", {"storage_safeguards_verified"}),
        ("delete", {"disposal_authority_and_method_verified"}),
        ("write", {"amendment_or_update_authority_verified"}),
    ],
)
async def test_combined_effects_cannot_skip_safeguards(effect, facts):
    p, c = fixture()
    assert await decision(p, c, effects=frozenset({"use", effect})) == "deny"
    assert (
        await decision(
            p,
            c,
            effects=frozenset({"use", effect}),
            facts=c.hipaa_evidence.facts | facts,
        )
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"patients": ()},
        {"effects": frozenset()},
        {"effects": frozenset({"unknown"})},
        {"data_categories": frozenset()},
        {"data_categories": frozenset({"phi", "part2_records"})},
        {"marketing": None},
        {"minimum_necessary_mode": "unknown"},
        {"facts": None},
        {"recipient_kind": "unknown"},
    ],
)
async def test_unknown_or_unsupported_states_deny(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
async def test_spoofing_binding_expiry_and_patient_evidence():
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
    ]:
        assert await decision(p, c, **changes) == "deny"
    for changes in [
        {"patient_id": ""},
        {"facts": frozenset()},
        {"facts": None},
        {"request_restricted": "false"},
    ]:
        assert (
            await decision(
                p, c, patients=(replace(c.hipaa_evidence.patients[0], **changes),)
            )
            == "deny"
        )
    assert await decision(p, c, patients=c.hipaa_evidence.patients * 2) == "deny"
    assert (
        await p.evaluate(
            replace(
                c,
                hipaa_evidence=None,
                metadata={"actor_role": "healthcare_provider", "purpose": "treatment"},
            )
        )
    ).decision.value == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"patient": "bob"}}))
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_serialization_runtime_and_catalog():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    p, c = fixture()
    restored = load_policy(policy_provider_to_config(p))
    assert isinstance(restored, HipaaRequestPolicy)
    assert await decision(restored, c) == "allow"
    calls = []

    async def resolve(ctx):
        calls.append(ctx)
        if len(calls) > 1:
            raise RuntimeError("unavailable")
        return c.hipaa_evidence

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), hipaa_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(c, hipaa_evidence=None))
    ).decision.value == "allow"
    assert (await middleware._evaluate(c)).decision.value == "deny"
    staged = (
        await TestSecurityAPIGovernance()
        ._make_api()
        .stage_policy_bundle("hipaa-health-data")
    )
    assert staged["status"] == "imported"
    ref = staged["proposal"]["metadata"]["catalog_reference"]
    assert ref["pack_version"] == "2.0.0"
    assert ref["source_urls"]


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
async def test_all_mcp_surfaces_need_exact_grants(action):
    p, c = fixture()
    c = replace(
        c, action=action, hipaa_evidence=replace(c.hipaa_evidence, action=action)
    )
    assert await decision(p, c) == "deny"
    p = replace(p, grants=(ZeroTrustGrant("client", "records", frozenset({action})),))
    assert await decision(p, c) == "allow"
