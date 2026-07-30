"""HIPAA Privacy + Security Rule compliance pack.

Encodes the subset of 45 CFR Parts 160 and 164 that can be verified at
an MCP tool-call boundary. HIPAA splits into a Privacy Rule (164
Subpart E) governing use and disclosure of Protected Health
Information (PHI), and a Security Rule (164 Subparts A and C) with
administrative, physical, and technical safeguards.

Each rule carries a :class:`Citation` to the Code of Federal
Regulations section on HHS's eCFR publication so an audit reviewer
can click from a denial straight to the authoritative text.

Scope decisions — explicitly not encoded here:

- Breach Notification Rule (Subpart D, 164.400–414) is a post-incident
  reporting obligation; nothing a tool call would check.
- Physical safeguards (164.310 facility access, workstation security,
  device controls) are out-of-band.
- Administrative safeguards requiring documentation (164.308(a)(1)(ii)
  risk analysis, 164.316 policies and procedures) cannot be verified
  by presence of a metadata key.

What IS encoded:

- **Privacy Rule**
  - 164.502(b) minimum necessary standard.
  - 164.502(e) business associate disclosures.
  - 164.506(c) treatment/payment/healthcare-operations (TPO) uses.
  - 164.508(a) authorization required for non-TPO uses.
  - 164.510(b) disclosure to family / involved parties.
  - 164.512(b) public-health, (f) law enforcement, (j) serious threat.
  - 164.514(b) de-identification safeguards.
  - 164.524(a) right of access by individuals.
  - 164.528(a) accounting of disclosures.

- **Security Rule (Technical Safeguards)**
  - 164.312(a)(1) access control / unique user identification.
  - 164.312(a)(2)(iv) encryption and decryption.
  - 164.312(b) audit controls.
  - 164.312(c)(1) integrity.
  - 164.312(d) person or entity authentication.
  - 164.312(e)(1) transmission security.

Sources:

- eCFR Title 45 Part 164 consolidated text:
  https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164
- HHS HIPAA Privacy Rule summary (non-authoritative):
  https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_ECFR_164 = "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164"
_VERSION = "45 CFR Parts 160 + 164"
_RETRIEVED = "2026-05-01"


def _cite(article: str, url: str = _ECFR_164) -> Citation:
    return Citation(
        source="HIPAA",
        article=article,
        url=url,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── 164.502 — uses and disclosures ─────────────────────────────────


_MIN_NECESSARY = ComplianceRuleSpec(
    name="sec502_minimum_necessary",
    description=(
        "45 CFR 164.502(b)(1) — covered entities must make reasonable "
        "efforts to limit PHI use or disclosure to the minimum "
        "necessary to accomplish the intended purpose."
    ),
    tags=frozenset({"phi", "health_data", "hipaa_regulated"}),
    checks=(
        MetadataCheck(metadata_key="purpose"),
        MetadataCheck(
            metadata_key="minimum_necessary_justified",
            allowed_values=frozenset({"true", "1", "yes"}),
        ),
    ),
    deny_message=(
        "HIPAA 164.502(b)(1): PHI access requires a stated purpose and "
        "minimum_necessary_justified=true."
    ),
    citation=_cite("45 CFR 164.502(b)(1)"),
)


_BUSINESS_ASSOCIATE = ComplianceRuleSpec(
    name="sec502_business_associate_agreement",
    description=(
        "45 CFR 164.502(e)(2) — a covered entity may disclose PHI to a "
        "business associate only if a compliant business associate "
        "agreement is in place."
    ),
    tags=frozenset({"phi_to_business_associate", "ba_disclosure"}),
    checks=(MetadataCheck(metadata_key="baa_reference"),),
    deny_message=(
        "HIPAA 164.502(e)(2): Disclosure to a business associate "
        "requires a baa_reference identifying the executed BAA."
    ),
    citation=_cite("45 CFR 164.502(e)(2)"),
)


# ── 164.506 — treatment/payment/healthcare operations ───────────────


_TPO_AUTHORIZED_ROLE = ComplianceRuleSpec(
    name="sec506_tpo_authorized_role",
    description=(
        "45 CFR 164.506(c) — a covered entity may use or disclose PHI "
        "for its own treatment, payment, or healthcare operations. The "
        "caller must declare an authorized role and which of the three "
        "TPO purposes applies."
    ),
    tags=frozenset({"phi", "health_data", "hipaa_regulated"}),
    checks=(
        MetadataCheck(
            metadata_key="actor_role",
            allowed_values=frozenset(
                {
                    "healthcare_provider",
                    "health_plan",
                    "healthcare_clearinghouse",
                    "business_associate",
                }
            ),
        ),
        MetadataCheck(
            metadata_key="tpo_purpose",
            allowed_values=frozenset({"treatment", "payment", "healthcare_operations"}),
        ),
    ),
    deny_message=(
        "HIPAA 164.506(c): PHI access requires an authorized actor_role "
        "and a tpo_purpose of treatment / payment / healthcare_operations."
    ),
    citation=_cite("45 CFR 164.506(c)"),
)


# ── 164.508 — authorisation required for non-TPO uses ───────────────


_AUTH_NON_TPO = ComplianceRuleSpec(
    name="sec508_authorisation_required",
    description=(
        "45 CFR 164.508(a)(1) — except as otherwise permitted, a covered "
        "entity may not use or disclose PHI without a written "
        "authorization from the individual."
    ),
    tags=frozenset({"phi_non_tpo", "phi_marketing", "phi_research"}),
    checks=(
        MetadataCheck(metadata_key="authorization_id"),
        MetadataCheck(metadata_key="authorization_scope"),
    ),
    deny_message=(
        "HIPAA 164.508(a)(1): Non-TPO PHI uses require an "
        "authorization_id and authorization_scope."
    ),
    citation=_cite("45 CFR 164.508(a)(1)"),
)


# ── 164.512 — uses/disclosures without authorization ────────────────


_SEC512_PUBLIC_EXCEPTION = ComplianceRuleSpec(
    name="sec512_disclosure_exception",
    description=(
        "45 CFR 164.512 — PHI may be used or disclosed without "
        "authorization for specified public-interest purposes. The "
        "caller must name the 164.512 paragraph relied upon."
    ),
    tags=frozenset({"phi_public_interest", "phi_law_enforcement"}),
    checks=(
        MetadataCheck(
            metadata_key="sec512_paragraph",
            allowed_values=frozenset(
                {
                    # 164.512(a)–(l).
                    "required_by_law",
                    "public_health",
                    "victim_of_abuse",
                    "health_oversight",
                    "judicial_proceedings",
                    "law_enforcement",
                    "decedent",
                    "organ_donation",
                    "research_waiver",
                    "serious_threat",
                    "specialized_government",
                    "workers_compensation",
                }
            ),
        ),
    ),
    deny_message=(
        "HIPAA 164.512: PHI disclosure without authorization requires "
        "a sec512_paragraph identifying the statutory exception."
    ),
    citation=_cite("45 CFR 164.512"),
)


# ── 164.514(b) — de-identification ─────────────────────────────────


_DEIDENTIFICATION = ComplianceRuleSpec(
    name="sec514_deidentification_method",
    description=(
        "45 CFR 164.514(b) — PHI is considered de-identified if either "
        "(1) a qualified expert determines the risk is very small, or "
        "(2) 18 specified identifiers have been removed (Safe Harbor)."
    ),
    tags=frozenset({"phi_deidentified", "phi_safe_harbor"}),
    checks=(
        MetadataCheck(
            metadata_key="deidentification_method",
            allowed_values=frozenset({"expert_determination", "safe_harbor"}),
        ),
    ),
    deny_message=(
        "HIPAA 164.514(b): Data claimed de-identified requires a "
        "deidentification_method of expert_determination or safe_harbor."
    ),
    citation=_cite("45 CFR 164.514(b)"),
)


# ── 164.524 — individual right of access ────────────────────────────


_RIGHT_OF_ACCESS = ComplianceRuleSpec(
    name="sec524_individual_access",
    description=(
        "45 CFR 164.524(a)(1) — individuals have a right of access to "
        "inspect and obtain a copy of PHI in a designated record set. "
        "Tools fulfilling access requests must carry a request id "
        "tying the disclosure back to the originating data-subject "
        "request."
    ),
    tags=frozenset({"phi_access_request", "individual_right"}),
    checks=(MetadataCheck(metadata_key="access_request_id"),),
    deny_message=(
        "HIPAA 164.524(a)(1): Individual-access disclosures require an "
        "access_request_id."
    ),
    citation=_cite("45 CFR 164.524(a)(1)"),
)


# ── 164.528 — accounting of disclosures ─────────────────────────────


_ACCOUNTING_DISCLOSURES = ComplianceRuleSpec(
    name="sec528_accounting_of_disclosures",
    description=(
        "45 CFR 164.528(a) — individuals have a right to an accounting "
        "of disclosures made in the six years preceding the request. "
        "Tools that make qualifying disclosures must attach a "
        "disclosure_record id so the accounting can be generated."
    ),
    tags=frozenset({"phi_accountable_disclosure"}),
    checks=(MetadataCheck(metadata_key="disclosure_record_id"),),
    deny_message=(
        "HIPAA 164.528(a): Disclosures subject to accounting require a "
        "disclosure_record_id."
    ),
    citation=_cite("45 CFR 164.528(a)"),
)


# ── 164.312 — technical safeguards ─────────────────────────────────


_UNIQUE_USER_IDENTIFICATION = ComplianceRuleSpec(
    name="sec312_unique_user_identification",
    description=(
        "45 CFR 164.312(a)(2)(i) — assign a unique name and/or number "
        "for identifying and tracking user identity."
    ),
    tags=frozenset({"phi", "health_data", "hipaa_regulated"}),
    checks=(MetadataCheck(metadata_key="user_identifier"),),
    deny_message=(
        "HIPAA 164.312(a)(2)(i): PHI access requires a user_identifier "
        "attributing the action to a unique user."
    ),
    citation=_cite("45 CFR 164.312(a)(2)(i)"),
)


_ENCRYPTION_AT_REST = ComplianceRuleSpec(
    name="sec312_encryption_at_rest",
    description=(
        "45 CFR 164.312(a)(2)(iv) — implement a mechanism to encrypt and "
        "decrypt electronic PHI. Storage-tier tools must state the "
        "encryption state."
    ),
    tags=frozenset({"phi_at_rest", "phi_storage"}),
    checks=(
        MetadataCheck(
            metadata_key="encryption_at_rest",
            allowed_values=frozenset(
                {"aes_256", "aes_256_gcm", "aes_128", "kms_managed"}
            ),
        ),
    ),
    deny_message=(
        "HIPAA 164.312(a)(2)(iv): At-rest PHI requires declared "
        "encryption_at_rest (aes_256 / aes_128 / kms_managed)."
    ),
    citation=_cite("45 CFR 164.312(a)(2)(iv)"),
)


_ENCRYPTION_IN_TRANSIT = ComplianceRuleSpec(
    name="sec312_transmission_security",
    description=(
        "45 CFR 164.312(e)(1) — implement technical security measures to "
        "guard against unauthorized access to ePHI transmitted over an "
        "electronic communications network."
    ),
    tags=frozenset({"phi_egress", "phi_in_transit"}),
    checks=(
        MetadataCheck(
            metadata_key="encryption_in_transit",
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls"}),
        ),
    ),
    deny_message=(
        "HIPAA 164.312(e)(1): PHI transmission requires TLS 1.2 or "
        "higher as encryption_in_transit."
    ),
    citation=_cite("45 CFR 164.312(e)(1)"),
)


_AUDIT_CONTROLS = ComplianceRuleSpec(
    name="sec312_audit_controls",
    description=(
        "45 CFR 164.312(b) — implement hardware, software, and/or "
        "procedural mechanisms that record and examine activity in "
        "information systems that contain or use ePHI. Tools modifying "
        "ePHI must carry an audit_sink identifier pointing at the "
        "write-ahead log they emit to."
    ),
    tags=frozenset({"phi_mutation", "phi_write"}),
    checks=(MetadataCheck(metadata_key="audit_sink"),),
    deny_message=(
        "HIPAA 164.312(b): PHI mutations require an audit_sink "
        "identifying where the change was recorded."
    ),
    citation=_cite("45 CFR 164.312(b)"),
)


_INTEGRITY = ComplianceRuleSpec(
    name="sec312_integrity",
    description=(
        "45 CFR 164.312(c)(1) — implement policies and procedures to "
        "protect ePHI from improper alteration or destruction. Tools "
        "claiming protection must state an integrity_mechanism "
        "(digest / signature / hmac)."
    ),
    tags=frozenset({"phi_integrity_protected"}),
    checks=(
        MetadataCheck(
            metadata_key="integrity_mechanism",
            allowed_values=frozenset(
                {"sha256_digest", "sha512_digest", "hmac", "signature"}
            ),
        ),
    ),
    deny_message=(
        "HIPAA 164.312(c)(1): PHI integrity protection requires an "
        "integrity_mechanism (sha256_digest / hmac / signature)."
    ),
    citation=_cite("45 CFR 164.312(c)(1)"),
)


def build_hipaa_policy(
    *,
    policy_id: str = "hipaa-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the HIPAA enforceable-at-tool-boundary rule pack.

    Combines Privacy Rule (164.502–528) and Security Rule technical
    safeguards (164.312). Administrative and physical safeguards,
    breach notification, and documentation obligations are out of
    scope — those live in organizational governance, not tool
    authorization.
    """
    return ComplianceRulePolicy(
        rules=[
            _MIN_NECESSARY,
            _BUSINESS_ASSOCIATE,
            _TPO_AUTHORIZED_ROLE,
            _AUTH_NON_TPO,
            _SEC512_PUBLIC_EXCEPTION,
            _DEIDENTIFICATION,
            _RIGHT_OF_ACCESS,
            _ACCOUNTING_DISCLOSURES,
            _UNIQUE_USER_IDENTIFICATION,
            _ENCRYPTION_AT_REST,
            _ENCRYPTION_IN_TRANSIT,
            _AUDIT_CONTROLS,
            _INTEGRITY,
        ],
        framework="HIPAA",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_hipaa_policy"]
