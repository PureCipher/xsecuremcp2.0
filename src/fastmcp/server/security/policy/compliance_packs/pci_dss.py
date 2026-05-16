"""PCI DSS v4.0 compliance pack.

Encodes the subset of the Payment Card Industry Data Security Standard
v4.0 (March 2022, in effect since Q2 2024) that is verifiable at an
MCP tool-call boundary. PCI DSS protects cardholder data (CHD) and
sensitive authentication data (SAD); the kernel's role is to enforce
that every tool call against CHD-classified resources carries the
metadata the requirements demand.

PCI DSS organizes controls into twelve Requirements. This pack
covers the technical ones that can be checked per-call:

- Req 3 — Protect stored account data.
- Req 4 — Protect cardholder data with strong cryptography during
  transmission over open, public networks.
- Req 7 — Restrict access to system components and cardholder data
  by business need-to-know.
- Req 8 — Identify users and authenticate access.
- Req 10 — Log and monitor all access to system components and
  cardholder data.

What IS NOT encoded:

- Req 1 (network security controls) and Req 2 (apply secure
  configurations) operate at infrastructure scope.
- Req 5 (malware protection), Req 6 (develop and maintain secure
  systems) are process obligations.
- Req 9 (restrict physical access), Req 11 (regular security
  testing), Req 12 (information security policy) are out-of-band.

Sources:

- PCI SSC Document Library (PCI DSS v4.0 PDF download requires
  agreement):
  https://www.pcisecuritystandards.org/document_library/
- Quick-reference Guide (non-authoritative but freely accessible):
  https://www.pcisecuritystandards.org/document_library/pci-dss-quick-reference-guide/
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_PCI_LIBRARY = "https://www.pcisecuritystandards.org/document_library/"
_VERSION = "v4.0"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="PCI-DSS",
        article=article,
        url=_PCI_LIBRARY,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── Req 3 — Protect stored account data ───────────────────────────


_REQ_3_2_SAD = ComplianceRuleSpec(
    name="req3_2_sad_not_stored",
    description=(
        "PCI DSS 3.2 — SAD (full track data, card verification code, "
        "PIN/PIN block) must not be stored after authorization. Tools "
        "persisting SAD must attest cryptographic protection and "
        "post-auth deletion."
    ),
    tags=frozenset({"sad_storage", "sensitive_auth_data"}),
    checks=(
        MetadataCheck(
            metadata_key="sad_post_auth_retention",
            allowed_values=frozenset({"deleted", "cryptographically_rendered_unrecoverable"}),
        ),
    ),
    deny_message=(
        "PCI DSS 3.2: SAD persistence requires declared post-auth "
        "deletion or cryptographic unrecoverability."
    ),
    citation=_cite("Requirement 3.2"),
)


_REQ_3_4_PAN_STORED = ComplianceRuleSpec(
    name="req3_4_pan_render_unreadable",
    description=(
        "PCI DSS 3.4 — PAN (primary account number) must be rendered "
        "unreadable anywhere it is stored, using one of: hashing, "
        "truncation, index tokens, or strong cryptography."
    ),
    tags=frozenset({"pan_storage", "cardholder_data_storage"}),
    checks=(
        MetadataCheck(
            metadata_key="pan_protection",
            allowed_values=frozenset(
                {
                    "strong_cryptography",
                    "tokenization",
                    "truncation",
                    "one_way_hash",
                }
            ),
        ),
    ),
    deny_message=(
        "PCI DSS 3.4: Stored PAN requires a pan_protection method "
        "(strong_cryptography / tokenization / truncation / one_way_hash)."
    ),
    citation=_cite("Requirement 3.4"),
)


_REQ_3_5_KEY_MGMT = ComplianceRuleSpec(
    name="req3_5_key_management",
    description=(
        "PCI DSS 3.5 — documented key-management procedures must be "
        "implemented for cryptographic keys used to protect stored "
        "account data. Callers encrypting CHD must reference the KEK "
        "(key-encrypting key) identifier."
    ),
    tags=frozenset({"cardholder_data_storage", "chd_encryption"}),
    checks=(
        MetadataCheck(metadata_key="kek_id"),
    ),
    deny_message=(
        "PCI DSS 3.5: CHD encryption requires a kek_id "
        "(key-encrypting-key identifier)."
    ),
    citation=_cite("Requirement 3.5"),
)


# ── Req 4 — Protect cardholder data with strong cryptography ──────


_REQ_4_2_ENCRYPT_TRANSMISSION = ComplianceRuleSpec(
    name="req4_2_transmission_encryption",
    description=(
        "PCI DSS 4.2.1 — strong cryptography and security protocols "
        "must be used to safeguard sensitive cardholder data during "
        "transmission over open, public networks."
    ),
    tags=frozenset({"chd_in_transit", "pan_in_transit"}),
    checks=(
        MetadataCheck(
            metadata_key="transit_protocol",
            # v4.0 requires "only trusted keys and certificates"; we
            # enforce a protocol floor. TLS 1.0/1.1 are explicitly
            # forbidden by the spec and therefore not allowed here.
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls"}),
        ),
    ),
    deny_message=(
        "PCI DSS 4.2.1: CHD transmission requires TLS 1.2 or higher."
    ),
    citation=_cite("Requirement 4.2.1"),
)


# ── Req 7 — Restrict access by business need-to-know ──────────────


_REQ_7_2_NEED_TO_KNOW = ComplianceRuleSpec(
    name="req7_2_need_to_know",
    description=(
        "PCI DSS 7.2 — an access control model is defined and includes "
        "granting access as needed and denying access by default. "
        "Calls must state the need_to_know justification."
    ),
    tags=frozenset({"cardholder_data", "chd_access", "pci_scoped"}),
    checks=(
        MetadataCheck(metadata_key="need_to_know_justification"),
        MetadataCheck(
            metadata_key="job_function",
            allowed_values=frozenset(
                {
                    "card_processing",
                    "fraud_investigation",
                    "payment_reconciliation",
                    "customer_support",
                    "compliance_audit",
                }
            ),
        ),
    ),
    deny_message=(
        "PCI DSS 7.2: CHD access requires a need_to_know_justification "
        "and a permitted job_function."
    ),
    citation=_cite("Requirement 7.2"),
)


# ── Req 8 — Identify and authenticate access ──────────────────────


_REQ_8_2_UNIQUE_ID = ComplianceRuleSpec(
    name="req8_2_unique_user_id",
    description=(
        "PCI DSS 8.2.1 — all users are identified via a unique ID "
        "before allowing access to system components or cardholder data."
    ),
    tags=frozenset({"cardholder_data", "pci_scoped"}),
    checks=(
        MetadataCheck(metadata_key="user_id"),
    ),
    deny_message=(
        "PCI DSS 8.2.1: Access requires a unique user_id."
    ),
    citation=_cite("Requirement 8.2.1"),
)


_REQ_8_4_MFA = ComplianceRuleSpec(
    name="req8_4_multi_factor_authentication",
    description=(
        "PCI DSS 8.4.2 — MFA is implemented for all non-console access "
        "to the CDE for personnel with administrative access."
    ),
    tags=frozenset({"cde_admin_access", "privileged_chd_access"}),
    checks=(
        MetadataCheck(
            metadata_key="mfa_state",
            allowed_values=frozenset({"passed", "satisfied", "verified"}),
        ),
    ),
    deny_message=(
        "PCI DSS 8.4.2: Admin access to the CDE requires MFA "
        "(mfa_state=passed)."
    ),
    citation=_cite("Requirement 8.4.2"),
)


# ── Req 10 — Log and monitor all access ───────────────────────────


_REQ_10_2_AUDIT = ComplianceRuleSpec(
    name="req10_2_audit_log_event",
    description=(
        "PCI DSS 10.2 — audit logs are implemented to record the "
        "detailed information required. Each access to CHD must emit "
        "an audit event id."
    ),
    tags=frozenset({"cardholder_data", "pci_scoped"}),
    checks=(
        MetadataCheck(metadata_key="audit_event_id"),
    ),
    deny_message=(
        "PCI DSS 10.2: CHD access requires an audit_event_id for log "
        "correlation."
    ),
    citation=_cite("Requirement 10.2"),
)


_REQ_10_7_INCIDENT_DETECT = ComplianceRuleSpec(
    name="req10_7_failure_alert",
    description=(
        "PCI DSS 10.7 — failures of critical security control systems "
        "are detected, alerted, and addressed promptly. Calls issued "
        "during an active control-failure window must carry the "
        "failure_ticket id."
    ),
    tags=frozenset({"pci_control_failure_window"}),
    checks=(
        MetadataCheck(metadata_key="failure_ticket"),
    ),
    deny_message=(
        "PCI DSS 10.7: Operations during a control-failure window "
        "require a failure_ticket reference."
    ),
    citation=_cite("Requirement 10.7"),
)


def build_pci_dss_policy(
    *,
    policy_id: str = "pci-dss-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the PCI DSS v4.0 enforceable rule pack."""
    return ComplianceRulePolicy(
        rules=[
            _REQ_3_2_SAD,
            _REQ_3_4_PAN_STORED,
            _REQ_3_5_KEY_MGMT,
            _REQ_4_2_ENCRYPT_TRANSMISSION,
            _REQ_7_2_NEED_TO_KNOW,
            _REQ_8_2_UNIQUE_ID,
            _REQ_8_4_MFA,
            _REQ_10_2_AUDIT,
            _REQ_10_7_INCIDENT_DETECT,
        ],
        framework="PCI-DSS",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_pci_dss_policy"]
