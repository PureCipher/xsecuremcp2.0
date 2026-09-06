"""GDPR request admission using authenticated, current, subject-specific evidence."""

from dataclasses import dataclass, field, replace

from fastmcp.server.security.policy.policies.zero_trust import (
    ZeroTrustEvidence,
    ZeroTrustPolicy,
)
from fastmcp.server.security.policy.provider import (
    Citation,
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

SOURCE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504"
BASES = {
    "consent": "valid_current_consent",
    "contract": "contract_necessity",
    "legal_obligation": "applicable_legal_obligation",
    "vital_interests": "vital_interest_necessity",
    "public_interest": "public_task_legal_authority",
    "legitimate_interests": "legitimate_interest_balance",
}
SPECIAL = {
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
}


@dataclass(frozen=True)
class GdprSubject:
    subject_id: str
    legal_basis: str
    special_category_basis: str
    consent_withdrawn: bool
    processing_restricted: bool
    processing_objected: bool
    marketing_objected: bool
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class GdprEvidence(ZeroTrustEvidence):
    effects: frozenset[str]
    data_categories: frozenset[str]
    recipient_kind: str
    international_transfer: bool
    transfer_basis: str
    direct_marketing: bool
    significant_automated_decision: bool
    subjects: tuple[GdprSubject, ...]
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class GdprRequestPolicy(ZeroTrustPolicy):
    policy_id: str = "gdpr-request-validation"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(
            allowed: bool, reason: str, articles: str = "5; 6; 32"
        ) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"GDPR {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="EUR-Lex",
                        article="Articles " + articles,
                        url=SOURCE,
                        version="Regulation (EU) 2016/679; consolidated 2016-05-04",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        e = context.gdpr_evidence
        if not isinstance(e, GdprEvidence):
            return result(False, "Trusted GDPR request evidence is required")
        admission = await super().evaluate(replace(context, zero_trust_evidence=e))
        if admission.decision != PolicyDecision.ALLOW:
            return result(False, admission.reason.split(": ", 1)[-1])
        if context.action in {
            "list_tools",
            "list_resources",
            "list_resource_templates",
            "list_prompts",
        }:
            return result(True, "Component discovery is explicitly authorized")
        if (
            not isinstance(e.effects, frozenset)
            or not e.effects
            or not e.effects
            <= {
                "collect",
                "read",
                "process",
                "store",
                "write",
                "delete",
                "disclose",
                "export",
            }
        ):
            return result(False, "Missing or unknown operation effects")
        if (
            not isinstance(e.data_categories, frozenset)
            or not e.data_categories
            or not e.data_categories
            <= {"personal", "special_category", "criminal_offence"}
        ):
            return result(
                False, "Missing or unknown personal-data classification", "9; 10"
            )
        if not isinstance(e.facts, frozenset) or any(
            type(v) is not bool
            for v in (
                e.international_transfer,
                e.direct_marketing,
                e.significant_automated_decision,
            )
        ):
            return result(False, "Malformed request safeguards")
        if e.significant_automated_decision:
            return result(
                False,
                "Significant automated decisions require a dedicated policy; unsupported here",
                "22",
            )
        required = {
            "complete_subject_field_and_effect_scope_verified",
            "purpose_compatibility_verified",
            "data_minimization_verified",
            "accuracy_safeguards_verified",
            "security_and_output_controls_verified",
            "transparency_requirements_verified",
            "applicable_dpia_and_consultation_verified",
        }
        if not required <= e.facts:
            return result(
                False,
                "Missing scope, purpose, minimization, accuracy, security, transparency or impact evidence",
                "5; 13; 14; 25; 32; 35; 36",
            )
        if e.effects != {"delete"} and "retention_permitted" not in e.facts:
            return result(
                False, "Continued use or retention is not permitted", "5(1)(e)"
            )
        if (
            "delete" in e.effects
            and "erasure_scope_and_exceptions_verified" not in e.facts
        ):
            return result(False, "Erasure scope and exceptions must be verified", "17")
        if (
            "write" in e.effects
            and "rectification_or_update_authority_verified" not in e.facts
        ):
            return result(False, "Update authority must be verified", "5; 16")
        if e.recipient_kind not in {
            "internal",
            "data_subject",
            "processor",
            "controller",
            "joint_controller",
        }:
            return result(False, "Unknown recipient relationship", "26; 28; 29")
        recipient_facts = {
            "processor": {
                "processor_contract_and_instructions_verified",
                "subprocessor_authority_verified",
            },
            "joint_controller": {"joint_controller_arrangement_verified"},
            "controller": {"recipient_controller_authority_verified"},
            "data_subject": {
                "subject_request_authority_verified",
                "other_persons_rights_protected",
            },
        }
        if not recipient_facts.get(e.recipient_kind, set()) <= e.facts:
            return result(
                False,
                "Recipient authority or required arrangement is missing",
                "15; 26; 28; 29",
            )
        if (
            e.effects & {"disclose", "export"}
            and not {
                "destination_authorized",
                "disclosure_scope_verified",
                "transfer_security_verified",
            }
            <= e.facts
        ):
            return result(
                False,
                "Disclosure destination, scope and protection must be verified",
                "5; 32",
            )
        if e.international_transfer:
            transfer_facts = {
                "adequacy": "current_adequacy_scope_verified",
                "safeguards": "article46_safeguards_and_transfer_assessment_verified",
                "derogation": "specific_article49_conditions_verified",
            }
            if (
                e.transfer_basis not in transfer_facts
                or transfer_facts[e.transfer_basis] not in e.facts
            ):
                return result(
                    False,
                    "International transfer mechanism is missing or unverified",
                    "44-49",
                )
            if (
                not {
                    "onward_transfer_controls_verified",
                    "destination_authorized",
                    "transfer_security_verified",
                }
                <= e.facts
            ):
                return result(
                    False,
                    "Transfer destination, security and onward-transfer safeguards are required",
                    "44-49",
                )
        elif e.transfer_basis != "not_required":
            return result(False, "Transfer classification is inconsistent", "44-49")
        if (
            "criminal_offence" in e.data_categories
            and "article10_authority_and_safeguards_verified" not in e.facts
        ):
            return result(False, "Criminal-offence data authority is required", "10")
        if not isinstance(e.subjects, tuple) or not e.subjects:
            return result(False, "Every affected subject needs current evidence")
        ids: set[str] = set()
        for subject in e.subjects:
            if (
                not isinstance(subject, GdprSubject)
                or not isinstance(subject.subject_id, str)
                or not subject.subject_id.strip()
                or subject.subject_id in ids
            ):
                return result(False, "Invalid or duplicate subject evidence")
            ids.add(subject.subject_id)
            if not isinstance(subject.facts, frozenset) or any(
                type(v) is not bool
                for v in (
                    subject.consent_withdrawn,
                    subject.processing_restricted,
                    subject.processing_objected,
                    subject.marketing_objected,
                )
            ):
                return result(False, "Unknown subject preference state", "7; 18; 21")
            if "current_subject_status_verified" not in subject.facts:
                return result(False, "Subject status must be current", "7; 18; 21")
            if (
                subject.legal_basis not in BASES
                or BASES[subject.legal_basis] not in subject.facts
            ):
                return result(
                    False, "Applicable Article 6 basis has not been verified", "6"
                )
            if subject.legal_basis == "consent":
                if (
                    subject.consent_withdrawn
                    or "article8_applicability_and_authority_verified"
                    not in subject.facts
                ):
                    return result(
                        False,
                        "Consent is withdrawn or age/jurisdiction authority is missing",
                        "7; 8",
                    )
            if subject.processing_restricted and e.effects != {"delete"}:
                return result(
                    False, "Restricted processing is blocked by this pack", "18"
                )
            if e.direct_marketing and subject.marketing_objected:
                return result(
                    False,
                    "Direct marketing is blocked by the subject objection",
                    "21(2)-(3)",
                )
            if subject.processing_objected and subject.legal_basis in {
                "public_interest",
                "legitimate_interests",
            }:
                return result(
                    False,
                    "Objected processing requires a dedicated exception assessment",
                    "21",
                )
            if "special_category" in e.data_categories:
                if (
                    subject.special_category_basis not in SPECIAL
                    or "article9_"
                    + subject.special_category_basis
                    + "_conditions_verified"
                    not in subject.facts
                ):
                    return result(
                        False, "Applicable Article 9 conditions are missing", "9"
                    )
                if (
                    subject.special_category_basis == "explicit_consent"
                    and subject.consent_withdrawn
                ):
                    return result(
                        False,
                        "Explicit special-category consent was withdrawn",
                        "7; 9(2)(a)",
                    )
        return result(
            True,
            "All applicable request safeguards verified",
            "5-10; 13-18; 21; 26; 28; 32; 35; 36; 44-49",
        )
