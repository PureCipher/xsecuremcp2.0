"""PCI DSS request safeguards; external verifier supplies authenticated facts."""

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

SAD = frozenset({"track_data", "card_verification_code", "pin", "pin_block"})
ACCOUNT_DATA = SAD | {"pan", "cardholder_name", "expiration_date", "service_code"}


@dataclass(frozen=True)
class PciEvidence(ZeroTrustEvidence):
    operation: str
    data_elements: frozenset[str]
    authorization_stage: str
    pan_presentation: str
    exposes_sad_to_client: bool
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class PciRequestPolicy(ZeroTrustPolicy):
    policy_id: str = "pci-dss-request-validation"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(
            allowed: bool, reason: str, requirement: str = "7; 8"
        ) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"PCI DSS {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="PCI SSC",
                        article="Requirements " + requirement,
                        url="https://www.pcisecuritystandards.org/document_library/",
                        version="PCI DSS v4.0.1 (June 2024)",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        evidence = context.pci_evidence
        if not isinstance(evidence, PciEvidence):
            return result(False, "Trusted PCI request evidence is required")
        admission = await super().evaluate(
            replace(context, zero_trust_evidence=evidence)
        )
        if admission.decision != PolicyDecision.ALLOW:
            return result(False, admission.reason.split(": ", 1)[-1])
        if context.action in {
            "list_tools",
            "list_resources",
            "list_resource_templates",
            "list_prompts",
        }:
            return result(True, "Component discovery is explicitly authorized", "7; 8")
        if not evidence.data_elements or not evidence.data_elements <= ACCOUNT_DATA:
            return result(False, "Missing or unknown account-data classification", "3")
        if evidence.operation not in {
            "display",
            "process",
            "transmit",
            "store",
            "delete",
        }:
            return result(False, "Unknown operation", "3; 7")
        if evidence.authorization_stage not in {
            "pre_authorization",
            "post_authorization",
            "not_applicable",
        }:
            return result(False, "Unknown authorization stage", "3.3")
        required = {
            "business_need_verified",
            "record_and_field_scope_matches",
            "recipient_authorized",
            "audit_data_protection_verified",
        }
        if not required <= evidence.facts:
            return result(
                False,
                "Missing verified need, scope, recipient or audit protection",
                "7; 10",
            )
        sad = bool(evidence.data_elements & SAD)
        if sad:
            if (
                evidence.exposes_sad_to_client is not False
                or evidence.operation == "display"
            ):
                return result(
                    False,
                    "SAD must not be exposed to the MCP client by this pack",
                    "3.3",
                )
            if (
                evidence.operation != "delete"
                and evidence.authorization_stage != "pre_authorization"
            ):
                return result(
                    False,
                    "Post-authorization SAD use/retention is not supported",
                    "3.3.1",
                )
            if (
                evidence.operation != "delete"
                and "payment_authorization_scope_verified" not in evidence.facts
            ):
                return result(
                    False,
                    "SAD requires a verified payment authorization purpose",
                    "3.3",
                )
        if evidence.operation == "delete":
            if "secure_deletion_scope_verified" not in evidence.facts:
                return result(
                    False,
                    "Deletion scope and destruction method must be verified",
                    "3.2; 3.3",
                )
        if evidence.operation == "store":
            if "retention_permitted" not in evidence.facts:
                return result(False, "Storage exceeds approved retention", "3.2.1")
            if (
                "pan" in evidence.data_elements
                and "pan_storage_unreadable" not in evidence.facts
            ):
                return result(False, "Stored PAN protection is not verified", "3.5.1")
            if sad and "strong_cryptography_verified" not in evidence.facts:
                return result(
                    False,
                    "Pre-authorization SAD storage requires strong cryptography",
                    "3.3.2",
                )
        if (
            evidence.operation == "transmit"
            and not {"strong_cryptography_verified", "destination_authenticated"}
            <= evidence.facts
        ):
            return result(
                False,
                "Transmission protection or destination identity is missing",
                "4.2.1",
            )
        if "pan" in evidence.data_elements and evidence.operation == "display":
            if evidence.pan_presentation == "masked":
                if "pan_masking_verified" not in evidence.facts:
                    return result(False, "PAN masking must be verified", "3.4.1")
            elif evidence.pan_presentation == "full":
                if "full_pan_business_need_verified" not in evidence.facts:
                    return result(
                        False,
                        "Full PAN requires verified documented business need",
                        "3.4.1",
                    )
            else:
                return result(False, "Unknown PAN presentation", "3.4.1")
        return result(
            True,
            "Requested data operation satisfies verified safeguards",
            "3; 4; 7; 8; 10",
        )
