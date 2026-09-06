"""SOC 2-aligned request safeguards; not an audit or attestation provider."""

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

SOURCE = "https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022"
EFFECTS = frozenset(
    {"read", "process", "write", "delete", "export", "configure", "deploy"}
)


@dataclass(frozen=True)
class Soc2Evidence(ZeroTrustEvidence):
    """The trusted resolver classifies all effects and verifies the relevant controls."""

    effects: frozenset[str]
    data_classification: str
    third_party_recipient: bool
    change_approver_id: str = ""
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class Soc2RequestPolicy(ZeroTrustPolicy):
    policy_id: str = "soc2-request-validation"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(allowed: bool, reason: str, criteria: str = "CC6") -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"SOC 2 {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="AICPA",
                        article=criteria,
                        url=SOURCE,
                        version="2017 Trust Services Criteria",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        e = context.soc2_evidence
        if not isinstance(e, Soc2Evidence):
            return result(False, "Trusted SOC 2 request evidence is required")
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
            or not e.effects <= EFFECTS
        ):
            return result(
                False, "Every operation effect must be classified", "CC6; PI1"
            )
        if e.data_classification not in {
            "public",
            "internal",
            "confidential",
            "personal",
            "confidential_personal",
        }:
            return result(False, "Missing or unknown data classification", "C1; P3-P4")
        if type(e.third_party_recipient) is not bool or not isinstance(
            e.facts, frozenset
        ):
            return result(False, "Malformed recipient or safeguard evidence")
        checks = [
            (
                {
                    "complete_effect_and_data_scope_verified",
                    "least_privilege_verified",
                    "input_validation_verified",
                },
                "Request scope, least privilege and inputs must be verified",
                "CC6; PI1",
            ),
            (
                {"audit_capture_available", "incident_containment_clear"},
                "Audit capture and incident admission must be verified",
                "CC7",
            ),
            (
                {"capacity_budget_reserved"},
                "Capacity budget must be reserved for this request",
                "A1",
            ),
            (
                {
                    "processing_integrity_controls_verified",
                    "output_delivery_controls_verified",
                },
                "Processing and delivery safeguards must be verified",
                "PI1",
            ),
        ]
        if e.data_classification in {"confidential", "confidential_personal"}:
            checks.append(
                (
                    {
                        "confidential_access_verified",
                        "confidential_output_protection_verified",
                    },
                    "Confidential data access and output protection are required",
                    "C1",
                )
            )
        if e.data_classification in {"personal", "confidential_personal"}:
            checks.append(
                (
                    {
                        "privacy_purpose_verified",
                        "privacy_choice_and_authority_verified",
                        "personal_data_scope_verified",
                    },
                    "Personal data purpose, current privacy choices and scope are required",
                    "P3-P6",
                )
            )
        if e.effects - {"delete"}:
            checks.append(
                (
                    {"retention_and_use_permitted"},
                    "Continued retention and use must be permitted",
                    "C1; P4",
                )
            )
        if "delete" in e.effects:
            checks.append(
                (
                    {"disposal_scope_and_method_verified"},
                    "Disposal scope and method must be verified",
                    "CC6; C1; P4",
                )
            )
        if "export" in e.effects:
            checks.append(
                (
                    {
                        "destination_authorized",
                        "transfer_protection_verified",
                        "export_scope_verified",
                    },
                    "Export destination, protection and data scope are required",
                    "CC6; C1; P6",
                )
            )
        if e.third_party_recipient:
            checks.append(
                (
                    {
                        "vendor_risk_and_contract_verified",
                        "destination_authorized",
                        "transfer_protection_verified",
                    },
                    "Third-party risk, contract and transfer safeguards are required",
                    "CC9; P6",
                )
            )
        if e.effects & {"write", "delete", "configure", "deploy"}:
            checks.append(
                (
                    {"mutation_scope_verified", "recovery_controls_verified"},
                    "Mutation scope and recovery controls must be verified",
                    "CC8; A1; PI1",
                )
            )
        if e.effects & {"configure", "deploy"}:
            if (
                not isinstance(e.change_approver_id, str)
                or not e.change_approver_id.strip()
                or e.change_approver_id == context.actor_id
            ):
                return result(
                    False,
                    "System changes require an independent authorized approver",
                    "CC6; CC8",
                )
            checks.append(
                (
                    {
                        "independent_change_authority_verified",
                        "approved_change_scope_verified",
                        "change_window_verified",
                        "change_validation_verified",
                    },
                    "System change approval, scope, window and validation are required",
                    "CC8",
                )
            )
        for required, reason, criteria in checks:
            if not required <= e.facts:
                return result(False, reason, criteria)
        return result(
            True,
            "All applicable request safeguards verified",
            "CC6-CC9; A1; PI1; C1; P3-P6",
        )
