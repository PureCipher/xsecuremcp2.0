"""Request-time CCPA safeguards based exclusively on server-verified evidence."""

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

SOURCE = "https://cppa.ca.gov/regulations/pdf/ccpa_statute_eff_20260101.pdf"


@dataclass(frozen=True)
class CcpaConsumer:
    """Current preferences for one consumer; the resolver must cover every record."""

    consumer_id: str
    age_band: str
    sale_sharing_opt_out: bool
    global_privacy_control: bool
    sensitive_use_limited: bool
    deletion_restricted: bool
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CcpaEvidence(ZeroTrustEvidence):
    operation: str
    recipient_kind: str
    purpose_basis: str
    sensitive_information: bool
    uses_admt: bool
    consumers: tuple[CcpaConsumer, ...]
    facts: frozenset[str] = field(default_factory=frozenset)


@dataclass
class CcpaRequestPolicy(ZeroTrustPolicy):
    policy_id: str = "ccpa-request-validation"
    version: str = "2.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        def result(
            allowed: bool, reason: str, sections: str = "7002; 7060"
        ) -> PolicyResult:
            return PolicyResult(
                decision=PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
                reason=f"CCPA/CPRA {self.version}: {reason}",
                policy_id=self.policy_id,
                citations=(
                    Citation(
                        source="California Privacy Protection Agency",
                        article="11 CCR §§ " + sections,
                        url=SOURCE,
                        version="Effective January 1, 2026",
                        retrieved_at="2026-09-06",
                    ),
                ),
            )

        e = context.ccpa_evidence
        if not isinstance(e, CcpaEvidence):
            return result(False, "Trusted CCPA request evidence is required")
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
        if e.operation not in {
            "collect",
            "use",
            "disclose",
            "sell",
            "share",
            "store",
            "consumer_access",
            "correct",
            "delete",
        }:
            return result(False, "Unknown operation")
        if e.recipient_kind not in {
            "internal",
            "consumer",
            "service_provider",
            "contractor",
            "third_party",
        }:
            return result(False, "Unknown recipient classification", "7050-7053")
        if type(e.sensitive_information) is not bool or type(e.uses_admt) is not bool:
            return result(False, "Missing data or ADMT classification")
        if e.uses_admt:
            return result(
                False,
                "ADMT requires a dedicated assessment; unsupported by this pack",
                "7200-7222",
            )
        if not isinstance(e.facts, frozenset):
            return result(False, "Malformed request safeguards")
        required = {
            "complete_consumer_and_field_scope_verified",
            "purpose_and_minimization_verified",
            "recipient_authorized",
            "security_and_output_controls_verified",
            "non_discrimination_verified",
            "applicable_risk_assessment_verified",
        }
        if not required <= e.facts:
            return result(
                False,
                "Missing scope, purpose, security, recipient, non-discrimination or risk evidence",
                "7002; 7080; 7150-7157",
            )
        if e.purpose_basis not in {"expected", "compatible", "consented"}:
            return result(False, "Purpose is not verified as permitted", "7002")
        if e.operation == "collect" and "notice_at_collection_verified" not in e.facts:
            return result(False, "Collection notice must be verified", "7012")
        if e.operation != "delete" and "retention_permitted" not in e.facts:
            return result(False, "Retention or continued use is not permitted", "7002")
        if e.recipient_kind in {"service_provider", "contractor"}:
            if e.operation in {"sell", "share"}:
                return result(
                    False,
                    "Sale/sharing cannot use the service-provider exception",
                    "7050-7051",
                )
            if (
                not {
                    "processor_contract_verified",
                    "processor_use_restrictions_verified",
                }
                <= e.facts
            ):
                return result(
                    False,
                    "Processor contract and reuse/combination restrictions are required",
                    "7050-7051",
                )
        if (
            e.recipient_kind == "third_party"
            and "third_party_contract_verified" not in e.facts
        ):
            return result(
                False,
                "Third-party contract and purpose restrictions must be verified",
                "7052-7053",
            )
        if e.operation in {"sell", "share"} and e.recipient_kind != "third_party":
            return result(
                False, "Sale/sharing requires third-party classification", "7052-7053"
            )
        if e.operation == "consumer_access":
            if (
                e.recipient_kind != "consumer"
                or "restricted_identifiers_excluded" not in e.facts
            ):
                return result(
                    False,
                    "Consumer disclosure must exclude prohibited identifiers",
                    "7024(d)",
                )
        if e.operation == "correct" and "correction_scope_verified" not in e.facts:
            return result(False, "Correction scope is not verified", "7023")
        if (
            e.operation == "delete"
            and "deletion_scope_and_exceptions_verified" not in e.facts
        ):
            return result(
                False,
                "Deletion scope and applicable exceptions must be verified",
                "7022",
            )
        if not isinstance(e.consumers, tuple) or not e.consumers:
            return result(False, "Every affected consumer must have current evidence")
        ids: set[str] = set()
        for c in e.consumers:
            if (
                not isinstance(c, CcpaConsumer)
                or not isinstance(c.consumer_id, str)
                or not c.consumer_id.strip()
                or c.consumer_id in ids
            ):
                return result(False, "Invalid or duplicate consumer evidence")
            ids.add(c.consumer_id)
            if any(
                type(v) is not bool
                for v in (
                    c.sale_sharing_opt_out,
                    c.global_privacy_control,
                    c.sensitive_use_limited,
                    c.deletion_restricted,
                )
            ):
                return result(False, "Unknown consumer preference state", "7025-7027")
            if not isinstance(c.facts, frozenset):
                return result(False, "Malformed consumer safeguards")
            if "current_preferences_verified" not in c.facts:
                return result(
                    False, "Current consumer preferences are required", "7025-7028"
                )
            if c.deletion_restricted and e.operation not in {
                "consumer_access",
                "correct",
                "delete",
            }:
                return result(
                    False, "Consumer data is restricted pending deletion", "7022"
                )
            if (
                e.purpose_basis == "consented"
                and "specific_informed_consent_verified" not in c.facts
            ):
                return result(
                    False,
                    "New purpose requires valid current specific consent",
                    "7002; 7004",
                )
            if (
                e.operation in {"consumer_access", "correct", "delete"}
                and "rights_request_authority_verified" not in c.facts
            ):
                return result(
                    False,
                    "Consumer or authorized-agent authority is required",
                    "7060-7063",
                )
            if e.operation in {"sell", "share"}:
                if c.sale_sharing_opt_out or c.global_privacy_control:
                    return result(
                        False, "Sale/sharing blocked by opt-out or GPC", "7025-7026"
                    )
                if c.age_band not in {"under_13", "13_to_15", "16_plus"}:
                    return result(
                        False, "Sale/sharing age eligibility is unknown", "7070-7071"
                    )
                consent = {
                    "under_13": "parental_sale_sharing_consent_verified",
                    "13_to_15": "minor_sale_sharing_consent_verified",
                }.get(c.age_band)
                if consent and consent not in c.facts:
                    return result(
                        False,
                        "Age-appropriate sale/sharing opt-in is required",
                        "7070-7071",
                    )
            if (
                e.sensitive_information
                and e.operation not in {"consumer_access", "correct", "delete"}
                and "sensitive_permitted_purpose_verified" not in e.facts
            ):
                if c.sensitive_use_limited:
                    return result(
                        False,
                        "Sensitive-information use exceeds the consumer limit",
                        "7027",
                    )
                if "sensitive_notice_or_consent_verified" not in c.facts:
                    return result(
                        False,
                        "Sensitive-information notice/consent basis is missing",
                        "7014; 7027",
                    )
        return result(
            True,
            "Request satisfies verified consumer privacy safeguards",
            "7002; 7022-7028; 7050-7071; 7080",
        )
