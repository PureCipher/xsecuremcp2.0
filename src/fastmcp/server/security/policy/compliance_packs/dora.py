"""DORA (EU 2022/2554) compliance pack.

Encodes the subset of Regulation (EU) 2022/2554 on digital operational
resilience for the financial sector — commonly called the Digital
Operational Resilience Act (DORA) — that is verifiable at an MCP
tool-call boundary. DORA applies to a wide range of financial
entities (credit institutions, investment firms, payment institutions,
crypto-asset service providers, etc.) plus their critical third-party
ICT service providers.

Each rule carries a :class:`Citation` pointing at the EUR-Lex
consolidated regulation text.

Scope decisions — explicitly not encoded here:

- Article 5 governance and organization is a board/management
  obligation.
- Articles 17–23 incident classification and reporting timelines are
  post-event, handled by a separate notification pipeline.
- Articles 26–27 digital operational resilience testing is periodic.
- Articles 28–44 third-party ICT risk monitoring is
  contract-lifecycle management.

What IS encoded (technical requirements from Articles 6–16):

- Art 6 — ICT risk management framework (identify scoped action).
- Art 7 — ICT systems, protocols and tools.
- Art 8 — identification of ICT-supported business functions.
- Art 9 — protection and prevention (integrity, encryption).
- Art 10 — detection mechanisms.
- Art 11 — response and recovery.
- Art 13 — learning and evolving.
- Art 16 — simplified ICT risk management (applicable to smaller
  entities; we check attestation that the simplified framework is
  the one being applied).

Sources:

- EUR-Lex consolidated text:
  https://eur-lex.europa.eu/eli/reg/2022/2554/oj
- European Supervisory Authorities (ESAs) DORA page:
  https://www.eba.europa.eu/activities/single-rulebook/dora
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_EURLEX_DORA = "https://eur-lex.europa.eu/eli/reg/2022/2554/oj"
_VERSION = "Regulation (EU) 2022/2554"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="DORA",
        article=article,
        url=_EURLEX_DORA,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── Article 6 — ICT risk management framework ────────────────────


_ART_6 = ComplianceRuleSpec(
    name="art6_ict_risk_framework",
    description=(
        "Article 6 — financial entities shall have a sound, "
        "comprehensive and well-documented ICT risk management "
        "framework. Actions on scoped ICT systems must reference the "
        "risk framework document id."
    ),
    tags=frozenset({"dora_scoped_system"}),
    checks=(
        MetadataCheck(metadata_key="ict_risk_framework_id"),
    ),
    deny_message=(
        "DORA Art 6: Scoped-system actions require an "
        "ict_risk_framework_id."
    ),
    citation=_cite("Article 6"),
)


# ── Article 9 — protection and prevention ────────────────────────


_ART_9_INTEGRITY = ComplianceRuleSpec(
    name="art9_integrity_protection",
    description=(
        "Article 9(2) — financial entities shall design, procure, and "
        "implement ICT security policies, procedures, protocols, and "
        "tools that aim to ensure the resilience, continuity, and "
        "availability of ICT systems, as well as preserve the "
        "authenticity, integrity, and confidentiality of data."
    ),
    tags=frozenset({"dora_scoped_data_write"}),
    checks=(
        MetadataCheck(
            metadata_key="integrity_mechanism",
            allowed_values=frozenset(
                {"sha256_digest", "sha512_digest", "hmac", "signature"}
            ),
        ),
    ),
    deny_message=(
        "DORA Art 9(2): Writes to scoped data require an "
        "integrity_mechanism."
    ),
    citation=_cite("Article 9(2)"),
)


_ART_9_ENCRYPTION = ComplianceRuleSpec(
    name="art9_encryption",
    description=(
        "Article 9(2) — alongside integrity, financial entities must "
        "preserve confidentiality. Sensitive ICT data must be encrypted "
        "in transit."
    ),
    tags=frozenset({"dora_sensitive_ict_data_transit"}),
    checks=(
        MetadataCheck(
            metadata_key="encryption_in_transit",
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls"}),
        ),
    ),
    deny_message=(
        "DORA Art 9(2): Sensitive ICT data in transit requires TLS "
        "1.2 or higher."
    ),
    citation=_cite("Article 9(2)"),
)


# ── Article 10 — detection mechanisms ────────────────────────────


_ART_10_DETECTION = ComplianceRuleSpec(
    name="art10_detection",
    description=(
        "Article 10 — financial entities shall have in place mechanisms "
        "to promptly detect anomalous activities. Monitored calls must "
        "emit a detection telemetry id."
    ),
    tags=frozenset({"dora_scoped_system"}),
    checks=(
        MetadataCheck(metadata_key="detection_telemetry_id"),
    ),
    deny_message=(
        "DORA Art 10: Scoped-system calls require a "
        "detection_telemetry_id."
    ),
    citation=_cite("Article 10"),
)


# ── Article 11 — response and recovery ───────────────────────────


_ART_11_RECOVERY = ComplianceRuleSpec(
    name="art11_response_recovery",
    description=(
        "Article 11(1) — as part of the ICT risk management framework, "
        "financial entities shall put in place a comprehensive ICT "
        "business continuity policy and response and recovery plans. "
        "Recovery operations must reference the recovery plan id."
    ),
    tags=frozenset({"recovery_operation", "continuity_invocation"}),
    checks=(
        MetadataCheck(metadata_key="recovery_plan_id"),
    ),
    deny_message=(
        "DORA Art 11(1): Recovery operations require a "
        "recovery_plan_id."
    ),
    citation=_cite("Article 11(1)"),
)


_ART_11_BACKUP = ComplianceRuleSpec(
    name="art11_backup_restore",
    description=(
        "Article 12 — financial entities shall develop and document "
        "backup policies and procedures specifying the scope of the "
        "data subject to backup. Backup restorations must reference "
        "the backup policy id."
    ),
    tags=frozenset({"dora_backup_restore"}),
    checks=(
        MetadataCheck(metadata_key="backup_policy_id"),
    ),
    deny_message=(
        "DORA Art 12: Backup restoration requires a backup_policy_id."
    ),
    citation=_cite("Article 12"),
)


# ── Article 28 — third-party ICT services ────────────────────────


_ART_28_THIRD_PARTY = ComplianceRuleSpec(
    name="art28_third_party_provider",
    description=(
        "Article 28(1) — financial entities shall manage ICT "
        "third-party risk as an integral part of their ICT risk "
        "management framework. Calls routed through an ICT third-party "
        "service provider must carry the contractual arrangement id."
    ),
    tags=frozenset({"third_party_ict_service"}),
    checks=(
        MetadataCheck(metadata_key="contractual_arrangement_id"),
    ),
    deny_message=(
        "DORA Art 28(1): Third-party ICT calls require a "
        "contractual_arrangement_id."
    ),
    citation=_cite("Article 28(1)"),
)


# ── Article 13 — learning and evolving ───────────────────────────


_ART_13_LEARNING = ComplianceRuleSpec(
    name="art13_lessons_learnt",
    description=(
        "Article 13(4) — after a significant ICT-related incident, "
        "financial entities shall perform a post-incident review. "
        "Post-incident corrective actions must carry the review id."
    ),
    tags=frozenset({"post_incident_action"}),
    checks=(
        MetadataCheck(metadata_key="post_incident_review_id"),
    ),
    deny_message=(
        "DORA Art 13(4): Post-incident corrective actions require a "
        "post_incident_review_id."
    ),
    citation=_cite("Article 13(4)"),
)


def build_dora_policy(
    *,
    policy_id: str = "dora-enforceable-pack",
    version: str = "1.0.0",
) -> ComplianceRulePolicy:
    """Return the DORA enforceable-at-tool-boundary rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _ART_6,
            _ART_9_INTEGRITY,
            _ART_9_ENCRYPTION,
            _ART_10_DETECTION,
            _ART_11_RECOVERY,
            _ART_11_BACKUP,
            _ART_28_THIRD_PARTY,
            _ART_13_LEARNING,
        ],
        framework="DORA",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_dora_policy"]
