"""FERPA request authorization using evidence supplied by a trusted server adapter.

This module does not manage institutional workflows or accept client attestations.
Evidence is request-bound, short-lived, and supplied outside MCP arguments.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from fastmcp.server.security.policy.provider import (
    Citation,
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

# Each set names externally verified facts, not client-selectable booleans.
# Conditional duties are assessed by the adapter for the actual request.
FERPA_BASES: dict[str, tuple[str, frozenset[str]]] = {
    "consent": (
        "99.30",
        frozenset(
            {"signed_dated_consent", "signer_has_rights", "consent_scope_matches"}
        ),
    ),
    "school_official": (
        "99.31(a)(1)",
        frozenset(
            {
                "school_official_criteria_met",
                "legitimate_educational_interest",
                "contractor_conditions_met_if_applicable",
            }
        ),
    ),
    "school_transfer": (
        "99.31(a)(2); 99.34",
        frozenset({"enrollment_or_transfer_purpose", "transfer_notice_conditions_met"}),
    ),
    "audit_evaluation": (
        "99.31(a)(3); 99.35",
        frozenset(
            {
                "authorized_representative",
                "education_program_audit_purpose",
                "audit_agreement_conditions_met",
                "audit_use_and_destruction_limits_met",
            }
        ),
    ),
    "financial_aid": (
        "99.31(a)(4)",
        frozenset({"financial_aid_purpose", "aid_disclosure_necessary"}),
    ),
    "state_local_authority": (
        "99.31(a)(5); 99.38",
        frozenset(
            {
                "applicable_state_statutory_authority",
                "juvenile_justice_conditions_met_if_applicable",
            }
        ),
    ),
    "study": (
        "99.31(a)(6)",
        frozenset(
            {
                "permitted_study_purpose",
                "study_agreement_scope_matches",
                "study_access_and_destruction_limits_met",
            }
        ),
    ),
    "accreditation": (
        "99.31(a)(7)",
        frozenset({"accrediting_organization", "accreditation_function_scope"}),
    ),
    "dependent_parent": (
        "99.31(a)(8)",
        frozenset({"parent_relationship_verified", "tax_dependency_verified"}),
    ),
    "judicial": (
        "99.31(a)(9)",
        frozenset(
            {
                "judicial_or_litigation_authority_valid",
                "judicial_scope_matches",
                "judicial_notice_conditions_met",
            }
        ),
    ),
    "emergency": (
        "99.31(a)(10); 99.36",
        frozenset(
            {
                "articulable_significant_threat",
                "recipient_needs_information_for_protection",
                "emergency_scope_and_duration_match",
            }
        ),
    ),
    "directory": (
        "99.31(a)(11); 99.37",
        frozenset(
            {
                "directory_fields_designated",
                "directory_notice_conditions_met",
                "directory_objection_period_elapsed",
                "directory_disclosure_not_prohibited_by_optout",
                "directory_recipient_and_use_limits_met",
            }
        ),
    ),
    "rights_holder": (
        "99.31(a)(12); 99.4; 99.5; 99.10; 99.12",
        frozenset({"rights_holder_verified", "inspection_scope_permitted"}),
    ),
    "victim": (
        "99.31(a)(13); 99.39",
        frozenset(
            {
                "victim_identity_verified",
                "qualifying_disciplinary_offense",
                "final_results_only",
                "other_student_identity_limits_met",
            }
        ),
    ),
    "disciplinary_results": (
        "99.31(a)(14); 99.39",
        frozenset(
            {
                "qualifying_disciplinary_offense",
                "violation_determined",
                "permitted_result_date",
                "final_results_only",
                "other_student_identity_limits_met",
            }
        ),
    ),
    "alcohol_drugs_parent": (
        "99.31(a)(15)",
        frozenset(
            {
                "parent_relationship_verified",
                "student_under_21_at_disclosure",
                "postsecondary_violation_determined",
                "state_law_allows_disclosure",
            }
        ),
    ),
    "sex_offender_registry": (
        "99.31(a)(16)",
        frozenset(
            {"authorized_registration_source", "registration_disclosure_scope_matches"}
        ),
    ),
    "deidentified": (
        "99.31(b)",
        frozenset(
            {
                "pii_removed",
                "reasonable_reidentification_determination",
                "cumulative_release_risk_assessed",
                "research_code_conditions_met_if_applicable",
            }
        ),
    ),
}
COMMON_FACTS = frozenset(
    {
        "classification_verified",
        "client_authorized",
        "recipient_authenticated",
        "subject_scope_matches",
        "record_scope_matches",
        "recipient_scope_matches",
        "purpose_matches",
        "authority_current",
        "disclosure_recordkeeping_conditions_met",
        "redisclosure_conditions_met",
        "contested_statement_conditions_met",
    }
)


def request_digest(metadata: dict[str, Any]) -> str:
    """Bind evidence to the complete request metadata, including MCP arguments."""
    encoded = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class FerpaEvidence:
    """Produced only by a trusted server-side verifier for this specific request.

    The verifier authenticates external evidence, checks revocation on each request,
    and determines applicable conditions. Constructing this Python object is a
    trust boundary; do not deserialize it from MCP arguments or simulation JSON.
    """

    evidence_id: str
    issuer: str
    scope_id: str
    actor_id: str
    action: str
    resource_id: str
    request_digest: str
    subject_ids: tuple[str, ...]
    recipient_id: str
    purpose: str
    classification: str
    basis: str
    verified_at: datetime
    expires_at: datetime
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class FerpaRequestPolicy:
    trusted_issuers: frozenset[str] = field(default_factory=frozenset)
    scope_id: str = ""
    max_evidence_age_seconds: int = 60
    policy_id: str = "ferpa-request-validation"
    version: str = "2.0.0"

    def __post_init__(self) -> None:
        if not 1 <= self.max_evidence_age_seconds <= 300:
            raise ValueError("FERPA evidence age must be between 1 and 300 seconds")

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        section = "99.30; 99.31(c)"

        def result(decision: PolicyDecision, reason: str) -> PolicyResult:
            return PolicyResult(
                decision=decision,
                reason=f"FERPA {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="FERPA",
                        article=f"34 CFR {section}",
                        url="https://www.ecfr.gov/current/title-34/subtitle-A/part-99",
                        version="34 CFR Part 99",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        # Component discovery does not disclose student records. Execution is
        # always checked, including untagged tools/resources/prompts.
        if context.action in {
            "list_tools",
            "list_resources",
            "list_resource_templates",
            "list_prompts",
        }:
            return result(
                PolicyDecision.DEFER, "Discovery remains subject to other policies"
            )
        evidence = context.ferpa_evidence
        if not isinstance(evidence, FerpaEvidence):
            return result(PolicyDecision.DENY, "Trusted request evidence is required")
        if not self.scope_id or evidence.scope_id != self.scope_id:
            return result(
                PolicyDecision.DENY,
                "Evidence belongs to a different server or tenant scope",
            )
        if not evidence.issuer or evidence.issuer not in self.trusted_issuers:
            return result(PolicyDecision.DENY, "Evidence issuer is not trusted")
        try:
            if (
                not evidence.evidence_id
                or not context.actor_id
                or evidence.actor_id != context.actor_id
                or evidence.action != context.action
                or evidence.resource_id != context.resource_id
                or evidence.request_digest != request_digest(context.metadata)
            ):
                return result(
                    PolicyDecision.DENY, "Evidence does not match the request"
                )
            now = context.timestamp
            if any(
                t.tzinfo is None or t.utcoffset() is None
                for t in (now, evidence.verified_at, evidence.expires_at)
            ):
                return result(
                    PolicyDecision.DENY,
                    "Timezone-aware evidence timestamps are required",
                )
            if not (
                evidence.verified_at <= now < evidence.expires_at
            ) or now - evidence.verified_at > timedelta(
                seconds=self.max_evidence_age_seconds
            ):
                return result(
                    PolicyDecision.DENY, "Evidence is expired, stale or future-dated"
                )
        except (TypeError, ValueError, OverflowError):
            return result(PolicyDecision.DENY, "Request evidence cannot be validated")
        if evidence.classification == "not_education_record":
            if "record_exclusion_verified" not in evidence.facts:
                return result(PolicyDecision.DENY, "Record exclusion is not verified")
            return result(
                PolicyDecision.DEFER,
                "Verified record exclusion; other policies still apply",
            )
        if evidence.classification not in {
            "education_record",
            "directory_information",
            "deidentified",
        }:
            return result(PolicyDecision.DENY, "Unknown record classification")
        if (
            (
                evidence.classification != "deidentified"
                and (not evidence.subject_ids or not all(evidence.subject_ids))
            )
            or not evidence.recipient_id
            or not evidence.purpose
        ):
            return result(
                PolicyDecision.DENY, "Subject, recipient and purpose are required"
            )
        selected = FERPA_BASES.get(evidence.basis)
        if selected is None:
            return result(PolicyDecision.DENY, "Unsupported disclosure authority")
        section, requirements = selected
        if (
            evidence.basis == "directory"
            and evidence.classification != "directory_information"
        ):
            return result(
                PolicyDecision.DENY,
                "Directory authority cannot release other education records",
            )
        if (evidence.basis == "deidentified") != (
            evidence.classification == "deidentified"
        ):
            return result(
                PolicyDecision.DENY,
                "De-identification authority and classification disagree",
            )
        common = (
            COMMON_FACTS
            if evidence.basis != "deidentified"
            else frozenset({"classification_verified", "record_scope_matches"})
        )
        missing = (common | requirements) - evidence.facts
        if missing:
            return result(
                PolicyDecision.DENY,
                "Missing verified conditions: " + ", ".join(sorted(missing)),
            )
        return result(
            PolicyDecision.ALLOW,
            "Request satisfies verified " + evidence.basis + " conditions",
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version
