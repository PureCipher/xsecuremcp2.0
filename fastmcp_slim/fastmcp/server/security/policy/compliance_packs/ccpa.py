"""CCPA / CPRA compliance pack.

Encodes the subset of the California Consumer Privacy Act (Cal. Civ.
Code § 1798.100 et seq.), as amended by the California Privacy Rights
Act, that is verifiable at an MCP tool-call boundary. The statute
creates consumer rights (to know, delete, correct, opt out) and
obligations for businesses that sell or share personal information
(PI) or handle sensitive personal information (SPI).

Each rule carries a :class:`Citation` pointing at the California
Legislative Information site, which hosts the authoritative statute
text.

Scope decisions — explicitly not encoded here:

- Notice-at-collection (§ 1798.100(b)) is a UI requirement outside
  the tool-call boundary.
- Section 1798.135 opt-out button styling is a web-property concern.
- Enforcement by the California Privacy Protection Agency (CPPA) is
  a consequence of violation, not a pre-condition.

What IS encoded:

- § 1798.100 — right to know what PI is collected.
- § 1798.105 — right to delete.
- § 1798.106 — right to correct.
- § 1798.110 — right to know specific pieces of PI.
- § 1798.120 — right to opt out of sale / sharing.
- § 1798.121 — right to limit use of sensitive PI.
- § 1798.125 — no retaliation for exercising rights.
- § 1798.140(ae) — sensitive personal information definitions.

Sources:

- California Legislative Information — Civil Code Division 3 Part 4
  Title 1.81.5:
  https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5
- California Attorney General CCPA landing page:
  https://oag.ca.gov/privacy/ccpa
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_LEGINFO = (
    "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml"
    "?division=3.&part=4.&lawCode=CIV&title=1.81.5"
)
_VERSION = "CCPA/CPRA (Cal. Civ. Code §§ 1798.100-199.100)"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="CCPA",
        article=article,
        url=_LEGINFO,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── § 1798.100 — right to know ─────────────────────────────────────


_SEC_100_PURPOSE = ComplianceRuleSpec(
    name="sec100_disclosed_purpose",
    description=(
        "§ 1798.100(a) — a business collecting a consumer's personal "
        "information shall inform the consumer of the categories of PI "
        "collected and the purposes for which it will be used. Tools "
        "collecting PI must declare the processing purpose so the "
        "disclosure is verifiable."
    ),
    tags=frozenset({"california_pi", "ccpa_regulated", "personal_information"}),
    checks=(MetadataCheck(metadata_key="processing_purpose"),),
    deny_message=(
        "CCPA § 1798.100(a): California PI collection requires a "
        "declared processing_purpose."
    ),
    citation=_cite("§ 1798.100(a)"),
)


# ── § 1798.105 — right to delete ───────────────────────────────────


_SEC_105_DELETE = ComplianceRuleSpec(
    name="sec105_deletion_verified",
    description=(
        "§ 1798.105(c) — a business that receives a verifiable consumer "
        "request to delete shall delete the consumer's personal "
        "information from its records and direct any service providers "
        "to do the same. Deletion tools must carry the verified "
        "request id."
    ),
    tags=frozenset({"ccpa_deletion_workflow", "consumer_deletion"}),
    checks=(MetadataCheck(metadata_key="verified_request_id"),),
    deny_message=(
        "CCPA § 1798.105(c): Deletion workflow requires a "
        "verified_request_id from the identity-verification step."
    ),
    citation=_cite("§ 1798.105(c)"),
)


# ── § 1798.106 — right to correct ──────────────────────────────────


_SEC_106_CORRECT = ComplianceRuleSpec(
    name="sec106_correction_request",
    description=(
        "§ 1798.106 — a consumer shall have the right to request that a "
        "business that maintains inaccurate personal information about "
        "the consumer correct such inaccurate information."
    ),
    tags=frozenset({"ccpa_correction_workflow"}),
    checks=(MetadataCheck(metadata_key="correction_request_id"),),
    deny_message=(
        "CCPA § 1798.106: Correction workflow requires a correction_request_id."
    ),
    citation=_cite("§ 1798.106"),
)


# ── § 1798.120 — right to opt out of sale or sharing ───────────────


_SEC_120_OPT_OUT = ComplianceRuleSpec(
    name="sec120_opt_out_check",
    description=(
        "§ 1798.120(a) — a consumer shall have the right, at any time, "
        "to direct a business that sells or shares personal information "
        "about the consumer to third parties not to sell or share. "
        "Calls performing a sale or share must verify opt-out state."
    ),
    tags=frozenset({"pi_sale", "pi_share", "ad_personalization"}),
    checks=(
        MetadataCheck(
            metadata_key="opt_out_status",
            allowed_values=frozenset({"not_opted_out", "opted_in"}),
        ),
    ),
    deny_message=(
        "CCPA § 1798.120(a): Sale or share of California PI requires "
        "opt_out_status=not_opted_out (consumer has not opted out)."
    ),
    citation=_cite("§ 1798.120(a)"),
)


# ── § 1798.121 — right to limit use of sensitive personal info ─────


_SEC_121_LIMIT_SPI = ComplianceRuleSpec(
    name="sec121_limit_sensitive_pi",
    description=(
        "§ 1798.121(a) — a consumer shall have the right, at any time, "
        "to direct a business that collects sensitive personal "
        "information about the consumer to limit its use or disclosure "
        "to that use which is necessary to perform the services or "
        "provide the goods reasonably expected."
    ),
    tags=frozenset(
        {
            "sensitive_pi",
            "california_spi",
            "ssn",
            "drivers_license",
            "financial_account",
            "geolocation_precise",
            "race_ethnicity",
            "religious_beliefs",
            "union_membership",
            "personal_communications",
            "genetic_data",
            "biometric_identifier",
            "health_info_nonhipaa",
            "sexual_orientation",
        }
    ),
    checks=(
        MetadataCheck(
            metadata_key="spi_use_necessity",
            allowed_values=frozenset(
                {
                    "perform_services",
                    "provide_goods",
                    "security_incident",
                    "short_term_transient_use",
                    "authentic_function",
                }
            ),
        ),
    ),
    deny_message=(
        "CCPA § 1798.121(a): Sensitive PI use requires a stated "
        "necessity (perform_services / provide_goods / "
        "security_incident / ...) limited to what is reasonably "
        "expected."
    ),
    citation=_cite("§ 1798.121(a)"),
)


# ── § 1798.125 — no retaliation for exercising rights ──────────────


_SEC_125_NON_RETALIATION = ComplianceRuleSpec(
    name="sec125_non_retaliation",
    description=(
        "§ 1798.125(a)(1) — a business shall not discriminate against a "
        "consumer because the consumer exercised any of the consumer's "
        "rights. Differential-pricing or service-denial tools must "
        "declare the financial_incentive_id tying the differential to a "
        "qualifying, disclosed program."
    ),
    tags=frozenset({"ccpa_differential_pricing", "ccpa_service_denial"}),
    checks=(MetadataCheck(metadata_key="financial_incentive_id"),),
    deny_message=(
        "CCPA § 1798.125(a)(1): Differential pricing / service denial "
        "requires a financial_incentive_id pointing at a disclosed "
        "incentive program."
    ),
    citation=_cite("§ 1798.125(a)(1)"),
)


# ── § 1798.100(d) — service provider contract ─────────────────────


_SEC_100_D_SERVICE_PROVIDER = ComplianceRuleSpec(
    name="sec100_d_service_provider_contract",
    description=(
        "§ 1798.100(d) — a business that collects personal information "
        "shall enter into a contract with any third party to which it "
        "discloses PI, including a certification that the third party "
        "understands the restrictions."
    ),
    tags=frozenset({"ccpa_service_provider_disclosure"}),
    checks=(MetadataCheck(metadata_key="service_provider_contract_id"),),
    deny_message=(
        "CCPA § 1798.100(d): Disclosure to a service provider requires "
        "a service_provider_contract_id."
    ),
    citation=_cite("§ 1798.100(d)"),
)


def build_ccpa_policy(
    *,
    policy_id: str = "ccpa-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the CCPA/CPRA enforceable-at-tool-boundary rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _SEC_100_PURPOSE,
            _SEC_105_DELETE,
            _SEC_106_CORRECT,
            _SEC_120_OPT_OUT,
            _SEC_121_LIMIT_SPI,
            _SEC_125_NON_RETALIATION,
            _SEC_100_D_SERVICE_PROVIDER,
        ],
        framework="CCPA",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_ccpa_policy"]
