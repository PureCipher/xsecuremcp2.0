"""HIPAA request safeguards using authenticated patient-specific evidence."""

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

SOURCE = (
    "https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html"
)
BASES = {
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
}


@dataclass(frozen=True)
class HipaaPatient:
    patient_id: str
    disclosure_basis: str
    request_restricted: bool
    authorization_revoked: bool
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class HipaaEvidence(ZeroTrustEvidence):
    effects: frozenset[str]
    data_categories: frozenset[str]
    recipient_kind: str
    actor_business_associate: bool
    marketing: bool
    sale_of_phi: bool
    minimum_necessary_mode: str
    patients: tuple[HipaaPatient, ...]
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class HipaaRequestPolicy(ZeroTrustPolicy):
    policy_id: str = "hipaa-request-validation"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(
            allowed: bool, reason: str, sections: str = "164.502; 164.514"
        ) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"HIPAA {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="HHS",
                        article="45 CFR " + sections,
                        url=SOURCE,
                        version="45 CFR Parts 160 and 164; reviewed 2026-09-06",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        e = context.hipaa_evidence
        if not isinstance(e, HipaaEvidence):
            return result(False, "Trusted HIPAA request evidence is required")
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
            <= {"use", "request", "disclose", "store", "delete", "write"}
        ):
            return result(False, "Every request effect must be classified")
        if (
            not isinstance(e.data_categories, frozenset)
            or not e.data_categories
            or not e.data_categories <= {"phi", "psychotherapy_notes", "part2_records"}
        ):
            return result(False, "Missing or unknown PHI classification")
        if "part2_records" in e.data_categories:
            return result(
                False,
                "Part 2 records require a dedicated additional policy; unsupported here",
            )
        if not isinstance(e.facts, frozenset) or any(
            type(v) is not bool
            for v in (e.actor_business_associate, e.marketing, e.sale_of_phi)
        ):
            return result(False, "Malformed role or purpose evidence")
        if e.recipient_kind not in {
            "internal",
            "provider",
            "health_plan",
            "business_associate",
            "individual",
            "public_authority",
            "other",
        }:
            return result(False, "Unknown recipient relationship")
        required = {
            "complete_patient_field_and_effect_scope_verified",
            "identity_and_recipient_authority_verified",
            "permitted_purpose_scope_verified",
            "security_and_output_controls_verified",
            "audit_and_accounting_controls_verified",
            "applicable_additional_law_verified",
        }
        if not required <= e.facts:
            return result(
                False,
                "Missing scope, authority, purpose, security, accountability or additional-law evidence",
                "164.312; 164.514; 164.528",
            )
        if (
            e.actor_business_associate
            and "actor_baa_and_instructions_verified" not in e.facts
        ):
            return result(
                False,
                "Business-associate actor requires verified agreement and instructions",
                "164.502(e); 164.504(e)",
            )
        if (
            e.recipient_kind == "business_associate"
            and "recipient_baa_and_scope_verified" not in e.facts
        ):
            return result(
                False,
                "Business-associate recipient agreement and scope must be verified",
                "164.502(e); 164.504(e)",
            )
        if (
            e.effects & {"request", "disclose"}
            and not {"destination_authorized", "transmission_safeguards_verified"}
            <= e.facts
        ):
            return result(
                False,
                "Data exchange destination and safeguards are required",
                "164.312(e); 164.514(h)",
            )
        if "store" in e.effects and "storage_safeguards_verified" not in e.facts:
            return result(
                False, "Storage safeguards must be verified", "164.306; 164.312"
            )
        if (
            "delete" in e.effects
            and "disposal_authority_and_method_verified" not in e.facts
        ):
            return result(
                False, "Disposal authority and method must be verified", "164.310(d)"
            )
        if (
            "write" in e.effects
            and "amendment_or_update_authority_verified" not in e.facts
        ):
            return result(False, "Update authority must be verified", "164.526")
        exemptions = {
            "treatment_disclosure": "treatment",
            "individual": "individual",
            "authorization": "authorization",
            "required_law": "required_law",
            "hhs": "hhs_enforcement",
            "administrative": "administrative_simplification",
        }
        if e.minimum_necessary_mode == "required":
            if "minimum_necessary_scope_verified" not in e.facts:
                return result(
                    False,
                    "Minimum necessary scope must be verified",
                    "164.502(b); 164.514(d)",
                )
        elif (
            e.minimum_necessary_mode not in exemptions
            or "minimum_necessary_exception_scope_verified" not in e.facts
        ):
            return result(
                False, "Minimum-necessary exception is missing or unknown", "164.502(b)"
            )
        elif e.minimum_necessary_mode == "treatment_disclosure" and (
            not e.effects <= {"request", "disclose"}
            or "provider_treatment_exchange_verified" not in e.facts
        ):
            return result(
                False,
                "Treatment exception is limited to verified provider exchanges",
                "164.502(b)(2)(i)",
            )
        if not isinstance(e.patients, tuple) or not e.patients:
            return result(False, "Every affected patient requires current evidence")
        ids: set[str] = set()
        for patient in e.patients:
            if (
                not isinstance(patient, HipaaPatient)
                or not isinstance(patient.patient_id, str)
                or not patient.patient_id.strip()
                or patient.patient_id in ids
            ):
                return result(False, "Invalid or duplicate patient evidence")
            ids.add(patient.patient_id)
            if not isinstance(patient.facts, frozenset) or any(
                type(v) is not bool
                for v in (patient.request_restricted, patient.authorization_revoked)
            ):
                return result(
                    False, "Unknown patient restriction or authorization state"
                )
            if "current_patient_status_verified" not in patient.facts:
                return result(
                    False,
                    "Patient restrictions and authorization status must be current",
                    "164.508; 164.522",
                )
            if patient.request_restricted:
                return result(
                    False,
                    "An applicable patient restriction blocks this request",
                    "164.522",
                )
            basis = patient.disclosure_basis
            if (
                basis not in BASES
                or "basis_" + basis + "_conditions_verified" not in patient.facts
            ):
                return result(
                    False,
                    "The specific permitted-use/disclosure conditions are missing",
                    "164.502; 164.506; 164.508; 164.510; 164.512; 164.514",
                )
            if (
                e.minimum_necessary_mode != "required"
                and basis != exemptions[e.minimum_necessary_mode]
            ):
                return result(
                    False,
                    "Minimum-necessary exception does not match the disclosure basis",
                    "164.502(b)",
                )
            if basis == "individual" and (
                e.recipient_kind != "individual"
                or "individual_or_representative_authority_verified"
                not in patient.facts
            ):
                return result(
                    False,
                    "Individual or personal-representative authority must be verified",
                    "164.502(g); 164.524",
                )
            if basis == "limited_data_set" and (
                "psychotherapy_notes" in e.data_categories
                or not {
                    "limited_data_set_fields_verified",
                    "data_use_agreement_verified",
                }
                <= patient.facts
            ):
                return result(
                    False,
                    "Limited data set requires verified fields and data-use agreement",
                    "164.514(e)",
                )
            needs_authorization = (
                basis == "authorization"
                or e.marketing
                or e.sale_of_phi
                or "psychotherapy_notes" in e.data_categories
            )
            if needs_authorization and (
                patient.authorization_revoked
                or "valid_current_authorization_verified" not in patient.facts
            ):
                return result(
                    False, "Valid current authorization is required", "164.508"
                )
            for applies, fact in [
                (e.marketing, "marketing_authorization_scope_verified"),
                (e.sale_of_phi, "sale_authorization_remuneration_verified"),
                (
                    "psychotherapy_notes" in e.data_categories,
                    "psychotherapy_authorization_scope_verified",
                ),
            ]:
                if applies and fact not in patient.facts:
                    return result(
                        False, "Special authorization scope is missing", "164.508(a)"
                    )
        return result(
            True,
            "All applicable request safeguards verified",
            "164.502-164.514; 164.522; 164.312",
        )
