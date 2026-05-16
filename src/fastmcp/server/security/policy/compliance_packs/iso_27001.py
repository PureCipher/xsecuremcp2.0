"""ISO/IEC 27001:2022 Annex A compliance pack.

Encodes the subset of ISO/IEC 27001:2022 Annex A controls (93 total,
across four themes: Organizational, People, Physical, Technological)
that are verifiable at an MCP tool-call boundary.

Unlike HIPAA/GDPR/CCPA, ISO 27001 is a standard, not a regulation —
attaching this pack to a listing asserts "calls through this listing
produce the evidence an ISMS internal auditor expects", not
"compliant with statute X". The control structure in Annex A is
referenced exactly as published by ISO/IEC.

Controls included (all from the Technological theme, Section 8):

- A.5.15 — Access control.
- A.8.2 — Privileged access rights.
- A.8.3 — Information access restriction.
- A.8.5 — Secure authentication.
- A.8.8 — Management of technical vulnerabilities.
- A.8.10 — Information deletion.
- A.8.11 — Data masking.
- A.8.12 — Data leakage prevention.
- A.8.15 — Logging.
- A.8.20 — Networks security.
- A.8.23 — Web filtering.
- A.8.24 — Use of cryptography.
- A.8.33 — Test information.

What IS NOT encoded:

- Annex A.5 Organizational controls (policies, roles, ISMS scope) are
  documentation requirements.
- Annex A.6 People controls (screening, awareness training) are HR
  processes.
- Annex A.7 Physical controls are out-of-band.

Sources:

- ISO/IEC 27001:2022 purchase page (standard text is not free, but
  the control catalogue is published on the ISO website):
  https://www.iso.org/standard/27001
- Annex A control titles (the rule citations reference these titles
  verbatim so the mapping is unambiguous):
  https://www.iso.org/obp/ui/#iso:std:iso-iec:27001:ed-3:v1:en
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_ISO_27001 = "https://www.iso.org/standard/27001"
_VERSION = "ISO/IEC 27001:2022"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="ISO-27001",
        article=article,
        url=_ISO_27001,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── A.5.15 — Access control ────────────────────────────────────────


_A_5_15 = ComplianceRuleSpec(
    name="a5_15_access_control",
    description=(
        "A.5.15 — rules to control physical and logical access to "
        "information and other associated assets shall be established "
        "and implemented based on business and information security "
        "requirements."
    ),
    tags=frozenset({"iso27001_scoped", "information_asset"}),
    checks=(
        MetadataCheck(metadata_key="access_policy_id"),
    ),
    deny_message=(
        "ISO 27001 A.5.15: Access to information assets requires an "
        "access_policy_id identifying the authorizing rule."
    ),
    citation=_cite("Annex A.5.15"),
)


# ── A.8.2 — Privileged access rights ───────────────────────────────


_A_8_2 = ComplianceRuleSpec(
    name="a8_2_privileged_access",
    description=(
        "A.8.2 — the allocation and use of privileged access rights "
        "shall be restricted and managed. Privileged operations must "
        "declare the privileged_role and the originating approval."
    ),
    tags=frozenset({"privileged_access", "admin_access"}),
    checks=(
        MetadataCheck(metadata_key="privileged_role"),
        MetadataCheck(metadata_key="privilege_approval_id"),
    ),
    deny_message=(
        "ISO 27001 A.8.2: Privileged access requires a privileged_role "
        "and a privilege_approval_id."
    ),
    citation=_cite("Annex A.8.2"),
)


# ── A.8.3 — Information access restriction ────────────────────────


_A_8_3 = ComplianceRuleSpec(
    name="a8_3_information_access_restriction",
    description=(
        "A.8.3 — access to information and application system functions "
        "shall be restricted in accordance with the topic-specific "
        "policy on access control."
    ),
    tags=frozenset({"iso27001_application_function"}),
    checks=(
        MetadataCheck(metadata_key="function_scope"),
    ),
    deny_message=(
        "ISO 27001 A.8.3: Application function access requires a "
        "function_scope identifier."
    ),
    citation=_cite("Annex A.8.3"),
)


# ── A.8.5 — Secure authentication ─────────────────────────────────


_A_8_5 = ComplianceRuleSpec(
    name="a8_5_secure_authentication",
    description=(
        "A.8.5 — secure authentication technologies and procedures "
        "shall be implemented based on information access restrictions "
        "and the topic-specific policy on access control. High-risk "
        "access must carry an authentication_strength of at least "
        "multi_factor."
    ),
    tags=frozenset({"high_risk_access", "critical_system_access"}),
    checks=(
        MetadataCheck(
            metadata_key="authentication_strength",
            allowed_values=frozenset(
                {"multi_factor", "hardware_token", "webauthn"}
            ),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.5: High-risk access requires "
        "authentication_strength of multi_factor / hardware_token / "
        "webauthn."
    ),
    citation=_cite("Annex A.8.5"),
)


# ── A.8.8 — Management of technical vulnerabilities ───────────────


_A_8_8 = ComplianceRuleSpec(
    name="a8_8_vulnerability_management",
    description=(
        "A.8.8 — information about technical vulnerabilities of "
        "information systems in use shall be obtained, the "
        "organization's exposure to such vulnerabilities evaluated, "
        "and appropriate measures taken. Tools deploying software must "
        "declare the vulnerability_scan_id from the most recent scan."
    ),
    tags=frozenset({"software_deploy", "patch_apply"}),
    checks=(
        MetadataCheck(metadata_key="vulnerability_scan_id"),
    ),
    deny_message=(
        "ISO 27001 A.8.8: Deploy operations require a "
        "vulnerability_scan_id from a recent scan."
    ),
    citation=_cite("Annex A.8.8"),
)


# ── A.8.10 — Information deletion ─────────────────────────────────


_A_8_10 = ComplianceRuleSpec(
    name="a8_10_information_deletion",
    description=(
        "A.8.10 — information stored in information systems, devices or "
        "in any other storage media shall be deleted when no longer "
        "required."
    ),
    tags=frozenset({"data_deletion_workflow"}),
    checks=(
        MetadataCheck(
            metadata_key="deletion_method",
            allowed_values=frozenset(
                {
                    "cryptographic_erasure",
                    "degaussing",
                    "physical_destruction",
                    "secure_wipe",
                    "overwrite_dod_5220",
                }
            ),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.10: Deletion workflows require a deletion_method."
    ),
    citation=_cite("Annex A.8.10"),
)


# ── A.8.11 — Data masking ─────────────────────────────────────────


_A_8_11 = ComplianceRuleSpec(
    name="a8_11_data_masking",
    description=(
        "A.8.11 — data masking shall be used in accordance with the "
        "organization's topic-specific policy on access control, "
        "business requirements, and applicable legislation."
    ),
    tags=frozenset({"non_prod_data_clone", "analytics_data_clone"}),
    checks=(
        MetadataCheck(
            metadata_key="masking_technique",
            allowed_values=frozenset(
                {
                    "tokenization",
                    "pseudonymisation",
                    "generalisation",
                    "suppression",
                    "perturbation",
                }
            ),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.11: Non-prod clones / analytics exports of "
        "sensitive data require a masking_technique."
    ),
    citation=_cite("Annex A.8.11"),
)


# ── A.8.12 — Data leakage prevention ─────────────────────────────


_A_8_12 = ComplianceRuleSpec(
    name="a8_12_data_leakage_prevention",
    description=(
        "A.8.12 — data leakage prevention measures shall be applied to "
        "systems, networks, and any other devices that process, store, "
        "or transmit sensitive information."
    ),
    tags=frozenset({"bulk_export", "dlp_scoped"}),
    checks=(
        MetadataCheck(metadata_key="dlp_inspection_id"),
    ),
    deny_message=(
        "ISO 27001 A.8.12: Bulk exports require a dlp_inspection_id "
        "from the DLP gateway."
    ),
    citation=_cite("Annex A.8.12"),
)


# ── A.8.15 — Logging ──────────────────────────────────────────────


_A_8_15 = ComplianceRuleSpec(
    name="a8_15_logging",
    description=(
        "A.8.15 — logs that record activities, exceptions, faults and "
        "other relevant events shall be produced, stored, protected and "
        "analysed."
    ),
    tags=frozenset({"iso27001_scoped"}),
    checks=(
        MetadataCheck(metadata_key="log_stream_id"),
    ),
    deny_message=(
        "ISO 27001 A.8.15: Scoped calls require a log_stream_id for "
        "the event log."
    ),
    citation=_cite("Annex A.8.15"),
)


# ── A.8.20 — Networks security ────────────────────────────────────


_A_8_20 = ComplianceRuleSpec(
    name="a8_20_networks_security",
    description=(
        "A.8.20 — networks and network devices shall be secured, "
        "managed and controlled to protect information in systems and "
        "applications. Network-egress tools must declare the network "
        "segmentation zone."
    ),
    tags=frozenset({"network_egress", "cross_segment_traffic"}),
    checks=(
        MetadataCheck(
            metadata_key="network_zone",
            allowed_values=frozenset(
                {
                    "public",
                    "perimeter",
                    "internal",
                    "restricted",
                    "secret",
                }
            ),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.20: Network egress requires a declared "
        "network_zone."
    ),
    citation=_cite("Annex A.8.20"),
)


# ── A.8.24 — Use of cryptography ─────────────────────────────────


_A_8_24 = ComplianceRuleSpec(
    name="a8_24_use_of_cryptography",
    description=(
        "A.8.24 — rules for the effective use of cryptography, "
        "including cryptographic key management, shall be defined and "
        "implemented. Crypto operations must reference the approved "
        "algorithm and key length."
    ),
    tags=frozenset({"crypto_operation"}),
    checks=(
        MetadataCheck(
            metadata_key="crypto_algorithm",
            allowed_values=frozenset(
                {
                    "aes_256_gcm",
                    "aes_128_gcm",
                    "chacha20_poly1305",
                    "rsa_3072",
                    "rsa_4096",
                    "ecdsa_p256",
                    "ecdsa_p384",
                    "ed25519",
                }
            ),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.24: Crypto operations require an approved "
        "crypto_algorithm."
    ),
    citation=_cite("Annex A.8.24"),
)


# ── A.8.33 — Test information ─────────────────────────────────────


_A_8_33 = ComplianceRuleSpec(
    name="a8_33_test_information",
    description=(
        "A.8.33 — test information shall be appropriately selected, "
        "protected and managed. Non-production environments reading "
        "production-derived data must attest a test_data_provenance "
        "(either synthetic or masked)."
    ),
    tags=frozenset({"non_prod_environment", "test_data_access"}),
    checks=(
        MetadataCheck(
            metadata_key="test_data_provenance",
            allowed_values=frozenset({"synthetic", "masked", "anonymised"}),
        ),
    ),
    deny_message=(
        "ISO 27001 A.8.33: Non-production test data requires "
        "test_data_provenance of synthetic / masked / anonymised."
    ),
    citation=_cite("Annex A.8.33"),
)


def build_iso_27001_policy(
    *,
    policy_id: str = "iso-27001-enforceable-pack",
    version: str = "1.0.0",
) -> ComplianceRulePolicy:
    """Return the ISO/IEC 27001:2022 enforceable rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _A_5_15,
            _A_8_2,
            _A_8_3,
            _A_8_5,
            _A_8_8,
            _A_8_10,
            _A_8_11,
            _A_8_12,
            _A_8_15,
            _A_8_20,
            _A_8_24,
            _A_8_33,
        ],
        framework="ISO-27001",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_iso_27001_policy"]
