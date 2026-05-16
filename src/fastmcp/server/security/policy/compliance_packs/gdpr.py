"""GDPR (EU 2016/679) compliance pack.

Encodes the subset of the General Data Protection Regulation that can
be mechanically verified at an MCP tool-call boundary. Each rule
carries a :class:`Citation` back to the authoritative EUR-Lex text so
audit entries can be aggregated by article.

Scope decisions — explicitly not encoded here:

- Article 13/14 transparency notices, Article 30 records of processing
  and Article 35 Data Protection Impact Assessments are procedural
  documents that exist outside a tool call. No metadata value the
  caller could attach would prove a DPIA actually happened, so these
  are left to governance workflows outside the kernel.
- Article 24/25 controller accountability is partially covered via
  the ``data_minimization_scope`` rule (Art 25(1) data minimisation)
  but the broader accountability obligation requires organizational
  process that the kernel cannot check.
- Article 83 fines are a consequence, not a pre-condition.

What IS encoded:

- Article 5 lawfulness/fairness/transparency principles — enforced
  via ``purpose`` and ``data_minimization_scope`` metadata checks.
- Article 6 — legal basis for processing personal data.
- Article 7 — demonstrable consent when consent is the basis.
- Article 9 — special category data additional safeguards.
- Article 17 — right to erasure signalling.
- Article 22 — automated decision-making + profiling constraints.
- Article 25 — data-minimisation / purpose-limitation proof.
- Article 32 — security of processing (encryption-in-transit claim).
- Article 44–49 — cross-border transfer safeguards.

Sources:

- EUR-Lex consolidated text:
  https://eur-lex.europa.eu/eli/reg/2016/679/oj
- Article-by-article references:
  https://gdpr-info.eu/ (editorial, not authoritative)

All URLs below point at EUR-Lex; all ``version`` fields read
``"2016/679"`` because GDPR has not been amended since enactment.
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

# Root URL for the consolidated regulation — each rule points at the
# specific article on EUR-Lex via ``#d1e...`` fragments. A plain root
# link is used where the anchor isn't stable.
_EURLEX_GDPR = "https://eur-lex.europa.eu/eli/reg/2016/679/oj"
_VERSION = "2016/679"
_RETRIEVED = "2026-05-01"


def _cite(article: str, url: str = _EURLEX_GDPR) -> Citation:
    return Citation(
        source="GDPR",
        article=article,
        url=url,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── Article 5 — principles relating to processing of personal data ─


_ART_5_PURPOSE = ComplianceRuleSpec(
    name="art5_purpose_limitation",
    description=(
        "GDPR Article 5(1)(b) — personal data shall be collected for "
        "specified, explicit and legitimate purposes. The caller must "
        "state the processing purpose on every access."
    ),
    tags=frozenset({"pii", "personal_data", "gdpr_regulated"}),
    checks=(
        MetadataCheck(metadata_key="processing_purpose"),
    ),
    deny_message=(
        "GDPR Art 5(1)(b): Personal-data access requires a stated "
        "processing_purpose (purpose limitation)."
    ),
    allow_message="GDPR Art 5(1)(b): purpose-limited access granted.",
    citation=_cite("Article 5(1)(b)"),
)

_ART_5_MINIMIZATION = ComplianceRuleSpec(
    name="art5_data_minimization",
    description=(
        "GDPR Article 5(1)(c) — personal data shall be adequate, "
        "relevant and limited to what is necessary. Callers must "
        "declare the minimization scope (e.g. 'customer_support', "
        "'fraud_investigation', 'billing')."
    ),
    tags=frozenset({"pii", "personal_data", "gdpr_regulated"}),
    checks=(
        MetadataCheck(metadata_key="data_minimization_scope"),
    ),
    deny_message=(
        "GDPR Art 5(1)(c): Personal-data access requires a "
        "data_minimization_scope declaration."
    ),
    citation=_cite("Article 5(1)(c)"),
)

_ART_5_STORAGE_LIMIT = ComplianceRuleSpec(
    name="art5_storage_limitation",
    description=(
        "GDPR Article 5(1)(e) — kept in a form permitting identification "
        "for no longer than necessary. Callers that retain personal data "
        "beyond the request must declare a retention_period (ISO-8601 "
        "duration) so the recipient can enforce it."
    ),
    tags=frozenset({"pii_retention", "personal_data_retention"}),
    checks=(
        MetadataCheck(metadata_key="retention_period"),
    ),
    deny_message=(
        "GDPR Art 5(1)(e): Retention of personal data requires an "
        "explicit retention_period."
    ),
    citation=_cite("Article 5(1)(e)"),
)


# ── Article 6 — lawfulness of processing ────────────────────────────


_ART_6_LEGAL_BASIS = ComplianceRuleSpec(
    name="art6_legal_basis",
    description=(
        "GDPR Article 6(1) — processing is lawful only if and to the "
        "extent that at least one of the six stated bases applies. "
        "The caller must identify which."
    ),
    tags=frozenset({"pii", "personal_data", "gdpr_regulated"}),
    checks=(
        MetadataCheck(
            metadata_key="legal_basis",
            allowed_values=frozenset(
                {
                    # Article 6(1)(a)–(f), stated verbatim in the regulation.
                    "consent",
                    "contract",
                    "legal_obligation",
                    "vital_interests",
                    "public_interest",
                    "legitimate_interests",
                }
            ),
        ),
    ),
    deny_message=(
        "GDPR Art 6(1): Processing requires a lawful basis "
        "(consent / contract / legal_obligation / vital_interests / "
        "public_interest / legitimate_interests)."
    ),
    citation=_cite("Article 6(1)"),
)


# ── Article 7 — conditions for consent ──────────────────────────────


_ART_7_CONSENT_PROOF = ComplianceRuleSpec(
    name="art7_consent_demonstrable",
    description=(
        "GDPR Article 7(1) — the controller shall be able to demonstrate "
        "that the data subject has consented. When the claimed legal "
        "basis is consent, the caller must attach an opaque "
        "consent_record_id pointing at the audit trail entry that "
        "proves the consent."
    ),
    tags=frozenset({"consent_required", "pii_consent"}),
    checks=(
        MetadataCheck(metadata_key="consent_record_id"),
    ),
    deny_message=(
        "GDPR Art 7(1): Consent-based processing requires a "
        "consent_record_id proving the data subject's consent."
    ),
    citation=_cite("Article 7(1)"),
)


# ── Article 9 — special categories of personal data ─────────────────


_ART_9_SPECIAL_CATEGORY = ComplianceRuleSpec(
    name="art9_special_category_safeguard",
    description=(
        "GDPR Article 9(2) — processing of special-category data "
        "(racial/ethnic origin, political opinions, religious beliefs, "
        "trade-union membership, genetic/biometric data, health data, "
        "sex life or sexual orientation) is prohibited unless one of "
        "the listed exceptions applies. The caller must state which."
    ),
    tags=frozenset(
        {
            "special_category",
            "art9_data",
            "health_data",
            "biometric_data",
            "genetic_data",
            "sensitive_personal_data",
        }
    ),
    checks=(
        MetadataCheck(
            metadata_key="art9_exception",
            allowed_values=frozenset(
                {
                    # Article 9(2)(a)–(j) exceptions.
                    "explicit_consent",
                    "employment_social_security",
                    "vital_interests",
                    "foundation_association",
                    "manifestly_public",
                    "legal_claims",
                    "substantial_public_interest",
                    "preventive_occupational_medicine",
                    "public_health",
                    "archiving_research",
                }
            ),
        ),
    ),
    deny_message=(
        "GDPR Art 9(2): Special-category data access requires an "
        "art9_exception (e.g. explicit_consent, public_health, "
        "legal_claims)."
    ),
    citation=_cite("Article 9(2)"),
)


# ── Article 17 — right to erasure ──────────────────────────────────


_ART_17_ERASURE = ComplianceRuleSpec(
    name="art17_erasure_request",
    description=(
        "GDPR Article 17(1) — the data subject shall have the right "
        "to obtain erasure of personal data without undue delay. "
        "Tools tagged as erasure-workflows must declare the erasure_basis "
        "that motivated the request so downstream systems can honor it."
    ),
    tags=frozenset({"erasure_request", "right_to_be_forgotten"}),
    checks=(
        MetadataCheck(
            metadata_key="erasure_basis",
            allowed_values=frozenset(
                {
                    # Article 17(1)(a)–(f) grounds.
                    "no_longer_necessary",
                    "consent_withdrawn",
                    "objection_upheld",
                    "unlawfully_processed",
                    "legal_obligation",
                    "child_consent",
                }
            ),
        ),
    ),
    deny_message=(
        "GDPR Art 17(1): Erasure workflow requires an erasure_basis "
        "matching one of the six stated grounds."
    ),
    citation=_cite("Article 17(1)"),
)


# ── Article 22 — automated individual decision-making ──────────────


_ART_22_AUTOMATED_DECISION = ComplianceRuleSpec(
    name="art22_automated_decision_safeguard",
    description=(
        "GDPR Article 22(1) — the data subject shall have the right not "
        "to be subject to a decision based solely on automated processing "
        "which produces legal or similarly significant effects, unless "
        "one of the Article 22(2) exceptions applies."
    ),
    tags=frozenset({"automated_decision", "profiling", "art22_decision"}),
    checks=(
        MetadataCheck(
            metadata_key="art22_basis",
            allowed_values=frozenset(
                {
                    # Article 22(2)(a)–(c) exceptions.
                    "contract_necessity",
                    "union_member_state_law",
                    "explicit_consent",
                }
            ),
        ),
        MetadataCheck(metadata_key="human_review_available"),
    ),
    deny_message=(
        "GDPR Art 22(1): Solely automated decisions require both an "
        "art22_basis and a human_review_available attestation."
    ),
    citation=_cite("Article 22"),
)


# ── Article 32 — security of processing ────────────────────────────


_ART_32_ENCRYPTION = ComplianceRuleSpec(
    name="art32_encryption_in_transit",
    description=(
        "GDPR Article 32(1)(a) — taking into account the state of the "
        "art, the controller shall implement appropriate technical "
        "measures including encryption of personal data. When personal "
        "data leaves the trust boundary, the caller must declare the "
        "encryption_in_transit state."
    ),
    tags=frozenset({"pii_egress", "personal_data_egress"}),
    checks=(
        MetadataCheck(
            metadata_key="encryption_in_transit",
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls"}),
        ),
    ),
    deny_message=(
        "GDPR Art 32(1)(a): Egress of personal data requires "
        "encryption_in_transit to be tls_1_2 or higher."
    ),
    citation=_cite("Article 32(1)(a)"),
)

_ART_32_PSEUDONYMIZATION = ComplianceRuleSpec(
    name="art32_pseudonymisation",
    description=(
        "GDPR Article 32(1)(a) — pseudonymisation is explicitly named "
        "as an appropriate technical measure. Tools that bulk-read "
        "personal data for analytics must declare a pseudonymisation "
        "state (raw / pseudonymised / anonymised)."
    ),
    tags=frozenset({"pii_analytics", "bulk_read"}),
    checks=(
        MetadataCheck(
            metadata_key="pseudonymisation_state",
            allowed_values=frozenset(
                {"pseudonymised", "anonymised", "raw_with_justification"}
            ),
        ),
    ),
    deny_message=(
        "GDPR Art 32(1)(a): Bulk analytics over personal data require "
        "an explicit pseudonymisation_state."
    ),
    citation=_cite("Article 32(1)(a)"),
)


# ── Articles 44–49 — transfers to third countries ──────────────────


_ART_44_TRANSFER_SAFEGUARD = ComplianceRuleSpec(
    name="art44_cross_border_transfer",
    description=(
        "GDPR Article 44 — transfers of personal data to a third country "
        "or international organisation may take place only if the "
        "conditions laid down in Chapter V are complied with. The caller "
        "must state the safeguard relied upon."
    ),
    tags=frozenset({"cross_border_transfer", "third_country_transfer"}),
    checks=(
        MetadataCheck(
            metadata_key="transfer_safeguard",
            allowed_values=frozenset(
                {
                    # Articles 45–49 enumerate safeguards:
                    # 45 adequacy decision, 46 appropriate safeguards
                    # (SCCs, BCRs, approved codes of conduct, certification),
                    # 49 derogations.
                    "adequacy_decision",
                    "standard_contractual_clauses",
                    "binding_corporate_rules",
                    "code_of_conduct",
                    "certification_mechanism",
                    "explicit_derogation",
                }
            ),
        ),
        MetadataCheck(metadata_key="destination_country"),
    ),
    deny_message=(
        "GDPR Art 44–49: Cross-border transfers require a "
        "transfer_safeguard and a destination_country."
    ),
    citation=_cite("Article 44"),
)


# ── Pack factory ──────────────────────────────────────────────────


def build_gdpr_policy(
    *,
    policy_id: str = "gdpr-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the GDPR enforceable-at-tool-boundary rule pack.

    All rules are evaluated under the default ``require_all_rules=True``
    semantics: if a tag matches, every check for every matching rule
    must pass. Callers that want opt-in per rule should compose this
    pack with a policy workbench filter rather than tweaking rule
    flags.

    The returned :class:`ComplianceRulePolicy` is suitable for the
    default capability bundle's ``providers`` list or any pack-selector
    UI backed by the plugin registry.
    """
    return ComplianceRulePolicy(
        rules=[
            _ART_5_PURPOSE,
            _ART_5_MINIMIZATION,
            _ART_5_STORAGE_LIMIT,
            _ART_6_LEGAL_BASIS,
            _ART_7_CONSENT_PROOF,
            _ART_9_SPECIAL_CATEGORY,
            _ART_17_ERASURE,
            _ART_22_AUTOMATED_DECISION,
            _ART_32_ENCRYPTION,
            _ART_32_PSEUDONYMIZATION,
            _ART_44_TRANSFER_SAFEGUARD,
        ],
        framework="GDPR",
        policy_id=policy_id,
        version=version,
    )


# Rule exports for tests and downstream composition.
__all__ = [
    "build_gdpr_policy",
]
