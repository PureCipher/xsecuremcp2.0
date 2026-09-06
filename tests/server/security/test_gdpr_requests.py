from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.gdpr_request import (
    GdprEvidence,
    GdprRequestPolicy,
    GdprSubject,
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
        metadata={"arguments": {"subject": "alice"}},
        timestamp=now,
    )
    s = GdprSubject(
        "alice",
        "contract",
        "",
        False,
        False,
        False,
        False,
        frozenset({"contract_necessity", "current_subject_status_verified"}),
    )
    e = GdprEvidence(
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
        effects=frozenset({"read"}),
        data_categories=frozenset({"personal"}),
        recipient_kind="internal",
        international_transfer=False,
        transfer_basis="not_required",
        direct_marketing=False,
        significant_automated_decision=False,
        subjects=(s,),
        facts=frozenset(
            {
                "complete_subject_field_and_effect_scope_verified",
                "purpose_compatibility_verified",
                "data_minimization_verified",
                "accuracy_safeguards_verified",
                "security_and_output_controls_verified",
                "transparency_requirements_verified",
                "applicable_dpia_and_consultation_verified",
                "retention_permitted",
            }
        ),
    )
    p = GdprRequestPolicy(
        grants=(ZeroTrustGrant("client", "records", frozenset({"call_tool"})),),
        trusted_issuers=frozenset({"verifier"}),
        scope_id="tenant/server",
    )
    return p, replace(c, gdpr_evidence=e)


async def decision(p, c, **changes):
    return (
        await p.evaluate(replace(c, gdpr_evidence=replace(c.gdpr_evidence, **changes)))
    ).decision.value


@pytest.mark.anyio
@pytest.mark.parametrize(
    "basis,fact",
    [
        ("consent", "valid_current_consent"),
        ("contract", "contract_necessity"),
        ("legal_obligation", "applicable_legal_obligation"),
        ("vital_interests", "vital_interest_necessity"),
        ("public_interest", "public_task_legal_authority"),
        ("legitimate_interests", "legitimate_interest_balance"),
    ],
)
async def test_each_legal_basis_requires_its_own_verified_conditions(basis, fact):
    p, c = fixture()
    s = replace(
        c.gdpr_evidence.subjects[0],
        legal_basis=basis,
        facts=frozenset(
            {
                "current_subject_status_verified",
                "article8_applicability_and_authority_verified",
            }
        ),
    )
    assert await decision(p, c, subjects=(s,)) == "deny"
    assert (
        await decision(p, c, subjects=(replace(s, facts=s.facts | {fact}),)) == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "basis",
    [
        "explicit_consent",
        "employment_social_protection",
        "vital_interests",
        "nonprofit_members",
        "manifestly_public",
        "legal_claims",
        "substantial_public_interest",
        "health_care",
        "public_health",
        "research_archiving",
    ],
)
async def test_article9_is_additional_to_article6(basis):
    p, c = fixture()
    s = replace(c.gdpr_evidence.subjects[0], special_category_basis=basis)
    assert (
        await decision(
            p, c, data_categories=frozenset({"special_category"}), subjects=(s,)
        )
        == "deny"
    )
    s = replace(s, facts=s.facts | {"article9_" + basis + "_conditions_verified"})
    assert (
        await decision(
            p, c, data_categories=frozenset({"special_category"}), subjects=(s,)
        )
        == "allow"
    )
    assert (
        await decision(
            p,
            c,
            data_categories=frozenset({"special_category"}),
            subjects=(replace(s, legal_basis="unknown"),),
        )
        == "deny"
    )


@pytest.mark.anyio
async def test_consent_withdrawal_child_authority_and_mixed_subject_batch():
    p, c = fixture()
    s = replace(
        c.gdpr_evidence.subjects[0],
        legal_basis="consent",
        facts=frozenset({"current_subject_status_verified", "valid_current_consent"}),
    )
    assert await decision(p, c, subjects=(s,)) == "deny"
    s = replace(s, facts=s.facts | {"article8_applicability_and_authority_verified"})
    assert await decision(p, c, subjects=(s,)) == "allow"
    withdrawn = replace(s, subject_id="bob", consent_withdrawn=True)
    assert await decision(p, c, subjects=(s, withdrawn)) == "deny"
    special = replace(
        c.gdpr_evidence.subjects[0],
        special_category_basis="explicit_consent",
        consent_withdrawn=True,
        facts=c.gdpr_evidence.subjects[0].facts
        | {"article9_explicit_consent_conditions_verified"},
    )
    assert (
        await decision(
            p, c, data_categories=frozenset({"special_category"}), subjects=(special,)
        )
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fact",
    [
        "complete_subject_field_and_effect_scope_verified",
        "purpose_compatibility_verified",
        "data_minimization_verified",
        "accuracy_safeguards_verified",
        "security_and_output_controls_verified",
        "transparency_requirements_verified",
        "applicable_dpia_and_consultation_verified",
        "retention_permitted",
    ],
)
async def test_common_requirements_are_conjunctive(fact):
    p, c = fixture()
    assert await decision(p, c, facts=c.gdpr_evidence.facts - {fact}) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "basis,fact",
    [
        ("adequacy", "current_adequacy_scope_verified"),
        ("safeguards", "article46_safeguards_and_transfer_assessment_verified"),
        ("derogation", "specific_article49_conditions_verified"),
    ],
)
async def test_transfer_mechanisms_require_scope_security_and_conditions(basis, fact):
    p, c = fixture()
    facts = c.gdpr_evidence.facts | {
        "onward_transfer_controls_verified",
        "destination_authorized",
        "transfer_security_verified",
    }
    assert (
        await decision(
            p, c, international_transfer=True, transfer_basis=basis, facts=facts
        )
        == "deny"
    )
    assert (
        await decision(
            p,
            c,
            international_transfer=True,
            transfer_basis=basis,
            facts=facts | {fact},
        )
        == "allow"
    )
    assert (
        await decision(
            p,
            c,
            international_transfer=True,
            transfer_basis=basis,
            facts=(facts | {fact}) - {"onward_transfer_controls_verified"},
        )
        == "deny"
    )


@pytest.mark.anyio
async def test_marketing_objection_restriction_and_erasure():
    p, c = fixture()
    s = replace(c.gdpr_evidence.subjects[0], marketing_objected=True)
    assert await decision(p, c, direct_marketing=True, subjects=(s,)) == "deny"
    assert await decision(p, c, subjects=(s,)) == "allow"
    s = replace(s, processing_restricted=True)
    assert await decision(p, c, subjects=(s,)) == "deny"
    facts = (c.gdpr_evidence.facts - {"retention_permitted"}) | {
        "erasure_scope_and_exceptions_verified"
    }
    assert (
        await decision(p, c, effects=frozenset({"delete"}), subjects=(s,), facts=facts)
        == "allow"
    )
    assert (
        await decision(
            p, c, effects=frozenset({"read", "delete"}), subjects=(s,), facts=facts
        )
        == "deny"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "basis,fact",
    [
        ("public_interest", "public_task_legal_authority"),
        ("legitimate_interests", "legitimate_interest_balance"),
    ],
)
async def test_objected_processing_does_not_allow_a_generic_legal_basis(basis, fact):
    p, c = fixture()
    s = replace(
        c.gdpr_evidence.subjects[0],
        legal_basis=basis,
        processing_objected=True,
        facts=c.gdpr_evidence.subjects[0].facts | {fact},
    )
    assert await decision(p, c, subjects=(s,)) == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind,facts",
    [
        (
            "processor",
            {
                "processor_contract_and_instructions_verified",
                "subprocessor_authority_verified",
            },
        ),
        ("joint_controller", {"joint_controller_arrangement_verified"}),
        ("controller", {"recipient_controller_authority_verified"}),
        (
            "data_subject",
            {"subject_request_authority_verified", "other_persons_rights_protected"},
        ),
    ],
)
async def test_recipient_relationships_require_authority(kind, facts):
    p, c = fixture()
    assert await decision(p, c, recipient_kind=kind) == "deny"
    assert (
        await decision(p, c, recipient_kind=kind, facts=c.gdpr_evidence.facts | facts)
        == "allow"
    )


@pytest.mark.anyio
async def test_criminal_data_export_and_write_each_add_requirements():
    p, c = fixture()
    assert (
        await decision(p, c, data_categories=frozenset({"criminal_offence"})) == "deny"
    )
    assert (
        await decision(
            p,
            c,
            data_categories=frozenset({"criminal_offence"}),
            facts=c.gdpr_evidence.facts
            | {"article10_authority_and_safeguards_verified"},
        )
        == "allow"
    )
    assert await decision(p, c, effects=frozenset({"read", "export"})) == "deny"
    export = c.gdpr_evidence.facts | {
        "destination_authorized",
        "disclosure_scope_verified",
        "transfer_security_verified",
    }
    assert (
        await decision(p, c, effects=frozenset({"read", "export"}), facts=export)
        == "allow"
    )
    assert await decision(p, c, effects=frozenset({"write"})) == "deny"
    assert (
        await decision(
            p,
            c,
            effects=frozenset({"write"}),
            facts=c.gdpr_evidence.facts
            | {"rectification_or_update_authority_verified"},
        )
        == "allow"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"effects": frozenset()},
        {"effects": frozenset({"read", "unknown"})},
        {"data_categories": frozenset()},
        {"subjects": ()},
        {"international_transfer": None},
        {"transfer_basis": "adequacy"},
        {"recipient_kind": "unknown"},
        {"significant_automated_decision": True},
        {"facts": None},
    ],
)
async def test_unknown_and_unsupported_states_deny(changes):
    p, c = fixture()
    assert await decision(p, c, **changes) == "deny"


@pytest.mark.anyio
async def test_malformed_subject_spoofing_binding_and_expiry():
    p, c = fixture()
    s = c.gdpr_evidence.subjects[0]
    for changed in [
        replace(s, subject_id=""),
        replace(s, consent_withdrawn="false"),
        replace(s, facts=frozenset()),
        replace(s, facts=None),
    ]:
        assert await decision(p, c, subjects=(changed,)) == "deny"
    assert await decision(p, c, subjects=(s, s)) == "deny"
    for changed in [
        {"scope_id": "other"},
        {"issuer": "attacker"},
        {"actor_id": "other"},
        {"resource_id": "other"},
        {"action": "get_prompt"},
        {"request_digest": "forged"},
        {"verified_at": c.timestamp - timedelta(seconds=61)},
        {"expires_at": c.timestamp},
    ]:
        assert await decision(p, c, **changed) == "deny"
    assert (
        await p.evaluate(replace(c, metadata={"arguments": {"subject": "bob"}}))
    ).decision.value == "deny"
    assert (
        await p.evaluate(
            replace(
                c,
                gdpr_evidence=None,
                metadata={"legal_basis": "consent", "verified": True},
            )
        )
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_persistence_and_runtime_resolver():
    from fastmcp.server.security.middleware.policy_enforcement import (
        PolicyEnforcementMiddleware,
    )
    from fastmcp.server.security.policy.engine import PolicyEngine
    from tests.server.security.test_policy_governance_gaps import (
        TestSecurityAPIGovernance,
    )

    p, c = fixture()
    restored = load_policy(policy_provider_to_config(p))
    assert isinstance(restored, GdprRequestPolicy)
    assert await decision(restored, c) == "allow"
    calls = []

    async def resolve(ctx):
        calls.append(ctx)
        if len(calls) > 1:
            raise RuntimeError("unavailable")
        return c.gdpr_evidence

    middleware = PolicyEnforcementMiddleware(
        PolicyEngine(providers=[p]), gdpr_evidence_resolver=resolve
    )
    assert (
        await middleware._evaluate(replace(c, gdpr_evidence=None))
    ).decision.value == "allow"
    assert (await middleware._evaluate(c)).decision.value == "deny"
    staged = (
        await TestSecurityAPIGovernance()
        ._make_api()
        .stage_policy_bundle("gdpr-data-protection")
    )
    assert staged["status"] == "imported"
    assert (
        staged["proposal"]["metadata"]["catalog_reference"]["pack_version"] == "2.0.0"
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
async def test_mcp_surfaces_require_exact_grants(action):
    p, c = fixture()
    c = replace(c, action=action, gdpr_evidence=replace(c.gdpr_evidence, action=action))
    assert await decision(p, c) == "deny"
    p = replace(p, grants=(ZeroTrustGrant("client", "records", frozenset({action})),))
    assert await decision(p, c) == "allow"
