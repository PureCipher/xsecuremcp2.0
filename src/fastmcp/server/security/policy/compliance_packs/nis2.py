"""NIS2 Directive (EU 2022/2555) compliance pack.

Encodes the subset of Directive (EU) 2022/2555 (on measures for a
high common level of cybersecurity across the Union) — commonly
called NIS2 — that is verifiable at an MCP tool-call boundary. NIS2
replaced the 2016 NIS Directive and significantly broadens the scope
of entities subject to cybersecurity risk-management obligations
across the EU.

The directive is risk-management-heavy: most of Article 21's
obligations (risk analysis, incident handling, business continuity,
supply chain security) describe organizational processes. A tool-call
boundary can verify that individual calls *produce the evidence* the
auditor needs to confirm those processes are operating — not that the
processes themselves exist.

Each rule carries a :class:`Citation` pointing at the EUR-Lex
consolidated directive text.

Scope decisions — explicitly not encoded here:

- Article 23 incident reporting is a post-event obligation with
  24/72-hour timelines; operators implement this via a separate
  notification pipeline.
- Article 24 use of certified ICT products is a procurement concern.
- Article 32 supervisory powers and Article 34 penalties are
  regulator-facing.

What IS encoded (Article 21(2) technical / operational measures):

- Art 21(2)(a) — policies on risk analysis and information security.
- Art 21(2)(b) — incident handling.
- Art 21(2)(d) — supply chain security.
- Art 21(2)(e) — security in network and information systems
  acquisition, development, and maintenance.
- Art 21(2)(g) — basic cyber hygiene practices and training.
- Art 21(2)(h) — policies and procedures regarding cryptography.
- Art 21(2)(i) — human resources security, access control policies,
  and asset management.
- Art 21(2)(j) — use of multi-factor authentication, continuous
  authentication, secured voice/video/text communications, and
  secured emergency communication.

Sources:

- EUR-Lex consolidated text:
  https://eur-lex.europa.eu/eli/dir/2022/2555/oj
- European Commission NIS2 portal:
  https://digital-strategy.ec.europa.eu/en/policies/nis2-directive
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_EURLEX_NIS2 = "https://eur-lex.europa.eu/eli/dir/2022/2555/oj"
_VERSION = "Directive (EU) 2022/2555"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="NIS2",
        article=article,
        url=_EURLEX_NIS2,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── Article 21(2)(a) — risk analysis & infosec ────────────────────


_ART_21_A_RISK_ANALYSIS = ComplianceRuleSpec(
    name="art21_2_a_risk_analysis",
    description=(
        "Article 21(2)(a) — policies on risk analysis and information "
        "system security. Calls on essential/important-entity systems "
        "must reference the risk assessment id motivating the action."
    ),
    tags=frozenset({"nis2_essential_entity", "nis2_important_entity"}),
    checks=(
        MetadataCheck(metadata_key="risk_assessment_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(a): Calls on scoped systems require a "
        "risk_assessment_id."
    ),
    citation=_cite("Article 21(2)(a)"),
)


# ── Article 21(2)(b) — incident handling ──────────────────────────


_ART_21_B_INCIDENT = ComplianceRuleSpec(
    name="art21_2_b_incident_handling",
    description=(
        "Article 21(2)(b) — incident handling. During an active "
        "incident, actions taken on the scoped system must carry the "
        "incident_id so the 24-hour early warning and 72-hour "
        "notification timelines can be reconstructed."
    ),
    tags=frozenset({"nis2_incident_active"}),
    checks=(
        MetadataCheck(metadata_key="incident_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(b): Actions during an active incident require "
        "an incident_id."
    ),
    citation=_cite("Article 21(2)(b)"),
)


# ── Article 21(2)(d) — supply chain security ──────────────────────


_ART_21_D_SUPPLY_CHAIN = ComplianceRuleSpec(
    name="art21_2_d_supply_chain",
    description=(
        "Article 21(2)(d) — supply chain security, including "
        "security-related aspects concerning the relationships between "
        "each entity and its direct suppliers or service providers. "
        "Third-party software installs must reference the supplier "
        "assessment id."
    ),
    tags=frozenset({"supplier_software_install", "third_party_dependency"}),
    checks=(
        MetadataCheck(metadata_key="supplier_assessment_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(d): Third-party software requires a "
        "supplier_assessment_id."
    ),
    citation=_cite("Article 21(2)(d)"),
)


# ── Article 21(2)(e) — secure acquisition, dev, maintenance ───────


_ART_21_E_SECURE_DEV = ComplianceRuleSpec(
    name="art21_2_e_secure_development",
    description=(
        "Article 21(2)(e) — security in network and information systems "
        "acquisition, development, and maintenance, including "
        "vulnerability handling and disclosure. Deploys must reference "
        "the build attestation that evidences the secure pipeline."
    ),
    tags=frozenset({"software_deploy", "firmware_update"}),
    checks=(
        MetadataCheck(metadata_key="build_attestation_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(e): Deploys require a build_attestation_id."
    ),
    citation=_cite("Article 21(2)(e)"),
)


# ── Article 21(2)(h) — cryptography ────────────────────────────────


_ART_21_H_CRYPTO = ComplianceRuleSpec(
    name="art21_2_h_cryptography_policy",
    description=(
        "Article 21(2)(h) — policies and procedures regarding the use "
        "of cryptography and, where appropriate, encryption."
    ),
    tags=frozenset({"nis2_sensitive_data_access"}),
    checks=(
        MetadataCheck(
            metadata_key="encryption_in_transit",
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls"}),
        ),
    ),
    deny_message=(
        "NIS2 Art 21(2)(h): Sensitive-data access requires TLS 1.2 or "
        "higher."
    ),
    citation=_cite("Article 21(2)(h)"),
)


# ── Article 21(2)(i) — HR / access control / asset management ─────


_ART_21_I_ACCESS_CONTROL = ComplianceRuleSpec(
    name="art21_2_i_access_control",
    description=(
        "Article 21(2)(i) — human resources security, access control "
        "policies, and asset management."
    ),
    tags=frozenset({"nis2_scoped_asset_access"}),
    checks=(
        MetadataCheck(metadata_key="asset_id"),
        MetadataCheck(metadata_key="access_control_decision_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(i): Asset access requires asset_id and "
        "access_control_decision_id."
    ),
    citation=_cite("Article 21(2)(i)"),
)


# ── Article 21(2)(j) — MFA / secure comms ─────────────────────────


_ART_21_J_MFA = ComplianceRuleSpec(
    name="art21_2_j_mfa_continuous_auth",
    description=(
        "Article 21(2)(j) — use of multi-factor authentication or "
        "continuous authentication solutions, secured voice, video and "
        "text communications, and secured emergency communication "
        "systems within the entity, where appropriate."
    ),
    tags=frozenset({"nis2_privileged_access", "nis2_admin_console"}),
    checks=(
        MetadataCheck(
            metadata_key="mfa_state",
            allowed_values=frozenset({"passed", "satisfied", "continuous"}),
        ),
    ),
    deny_message=(
        "NIS2 Art 21(2)(j): Privileged / admin-console access requires "
        "MFA (mfa_state=passed/satisfied/continuous)."
    ),
    citation=_cite("Article 21(2)(j)"),
)


# ── Article 21(2)(g) — basic cyber hygiene ────────────────────────


_ART_21_G_HYGIENE = ComplianceRuleSpec(
    name="art21_2_g_cyber_hygiene",
    description=(
        "Article 21(2)(g) — basic cyber hygiene practices and "
        "cybersecurity training. Calls triggered by low-privilege "
        "automation must carry a hygiene_attestation_id evidencing the "
        "operating user's most recent training."
    ),
    tags=frozenset({"nis2_user_initiated"}),
    checks=(
        MetadataCheck(metadata_key="hygiene_attestation_id"),
    ),
    deny_message=(
        "NIS2 Art 21(2)(g): User-initiated actions require a "
        "hygiene_attestation_id from the training programme."
    ),
    citation=_cite("Article 21(2)(g)"),
)


def build_nis2_policy(
    *,
    policy_id: str = "nis2-enforceable-pack",
    version: str = "1.0.0",
) -> ComplianceRulePolicy:
    """Return the NIS2 Directive enforceable rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _ART_21_A_RISK_ANALYSIS,
            _ART_21_B_INCIDENT,
            _ART_21_D_SUPPLY_CHAIN,
            _ART_21_E_SECURE_DEV,
            _ART_21_H_CRYPTO,
            _ART_21_I_ACCESS_CONTROL,
            _ART_21_J_MFA,
            _ART_21_G_HYGIENE,
        ],
        framework="NIS2",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_nis2_policy"]
