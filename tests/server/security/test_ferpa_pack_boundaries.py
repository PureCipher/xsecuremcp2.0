"""FERPA v2 request boundaries and serialization."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fastmcp.server.security.policy.declarative import load_policy
from fastmcp.server.security.policy.policies.ferpa_request import (
    COMMON_FACTS,
    FERPA_BASES,
    FerpaEvidence,
    FerpaRequestPolicy,
    request_digest,
)
from fastmcp.server.security.policy.provider import PolicyEvaluationContext
from fastmcp.server.security.policy.serialization import policy_provider_to_config
from fastmcp.server.security.policy.workbench import get_policy_bundle


def request(basis="consent"):
    now = datetime.now(timezone.utc)
    context = PolicyEvaluationContext(
        actor_id="client-1",
        action="call_tool",
        resource_id="student-records",
        metadata={"arguments": {"record": "r1"}},
        timestamp=now,
    )
    classification = {
        "directory": "directory_information",
        "deidentified": "deidentified",
    }.get(basis, "education_record")
    evidence = FerpaEvidence(
        evidence_id="e1",
        issuer="school-verifier",
        scope_id="school-1/server-1",
        actor_id="client-1",
        action=context.action,
        resource_id=context.resource_id,
        request_digest=request_digest(context.metadata),
        subject_ids=("student-1",),
        recipient_id="recipient-1",
        purpose="approved-purpose",
        classification=classification,
        basis=basis,
        verified_at=now,
        expires_at=now + timedelta(seconds=30),
        facts=COMMON_FACTS | FERPA_BASES[basis][1],
    )
    return replace(context, ferpa_evidence=evidence)


def policy():
    return FerpaRequestPolicy(
        trusted_issuers=frozenset({"school-verifier"}), scope_id="school-1/server-1"
    )


@pytest.mark.anyio
@pytest.mark.parametrize("basis", list(FERPA_BASES))
async def test_each_authority_allows_only_its_verified_conditions(basis):
    context = request(basis)
    result = await policy().evaluate(context)
    assert result.decision.value == "allow"
    assert FERPA_BASES[basis][0] in result.citations[0].article
    for fact in FERPA_BASES[basis][1]:
        altered = replace(
            context.ferpa_evidence, facts=context.ferpa_evidence.facts - {fact}
        )
        assert (
            await policy().evaluate(replace(context, ferpa_evidence=altered))
        ).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_id", "other-client"),
        ("scope_id", "other-school"),
        ("resource_id", "other-tool"),
        ("action", "read_resource"),
        ("issuer", "untrusted"),
        ("request_digest", "wrong"),
        ("basis", "unknown"),
        ("classification", "unknown"),
        ("subject_ids", ()),
        ("recipient_id", ""),
        ("purpose", ""),
    ],
)
async def test_mismatched_evidence_denies(field, value):
    context = request()
    context = replace(
        context, ferpa_evidence=replace(context.ferpa_evidence, **{field: value})
    )
    assert (await policy().evaluate(context)).decision.value == "deny"


@pytest.mark.anyio
async def test_arguments_tags_and_claims_cannot_supply_or_reuse_evidence():
    context = request()
    forged = replace(
        context,
        ferpa_evidence=None,
        tags=frozenset(),
        metadata={"ferpa_evidence": context.ferpa_evidence, "authorized": True},
    )
    assert (await policy().evaluate(forged)).decision.value == "deny"
    changed = replace(context, metadata={"arguments": {"record": "other-student"}})
    assert (await policy().evaluate(changed)).decision.value == "deny"


@pytest.mark.anyio
@pytest.mark.parametrize("seconds", [-1, 31, 61])
async def test_future_expired_stale_evidence_denies(seconds):
    context = request()
    assert (
        await policy().evaluate(
            replace(context, timestamp=context.timestamp + timedelta(seconds=seconds))
        )
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_revoked_authority_does_not_pass_other_facts():
    context = request()
    evidence = replace(
        context.ferpa_evidence,
        facts=context.ferpa_evidence.facts - {"authority_current"},
    )
    assert (
        await policy().evaluate(replace(context, ferpa_evidence=evidence))
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_directory_authority_cannot_disclose_full_student_records():
    context = request("directory")
    evidence = replace(context.ferpa_evidence, classification="education_record")
    assert (
        await policy().evaluate(replace(context, ferpa_evidence=evidence))
    ).decision.value == "deny"


@pytest.mark.anyio
async def test_saved_config_restores_behavior_and_starter_denies_until_configured():
    restored = load_policy(policy_provider_to_config(policy()))
    assert isinstance(restored, FerpaRequestPolicy)
    assert (await restored.evaluate(request())).decision.value == "allow"
    bundle = get_policy_bundle("ferpa-student-records")
    assert bundle is not None
    assert bundle["pack_version"] == "2.0.0"
    starter = load_policy(bundle["providers"][0])
    assert isinstance(starter, FerpaRequestPolicy)
    assert (await starter.evaluate(request())).decision.value == "deny"
