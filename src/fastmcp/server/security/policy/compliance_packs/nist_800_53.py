"""NIST SP 800-53 Rev. 5 compliance pack (Moderate baseline).

Encodes the subset of NIST Special Publication 800-53 Revision 5
controls (Security and Privacy Controls for Information Systems and
Organizations, September 2020, with updates through 2023) that is
verifiable at an MCP tool-call boundary. The pack targets the
*Moderate* confidentiality/integrity/availability baseline defined in
SP 800-53B.

Each rule carries a :class:`Citation` pointing at the NIST Computer
Security Resource Center authoritative PDF.

Controls encoded (and their parent family):

- **AC — Access Control**
  - AC-2 Account Management
  - AC-3 Access Enforcement
  - AC-5 Separation of Duties
  - AC-6 Least Privilege
  - AC-17 Remote Access

- **AU — Audit and Accountability**
  - AU-2 Event Logging
  - AU-3 Content of Audit Records
  - AU-12 Audit Record Generation

- **IA — Identification and Authentication**
  - IA-2 Identification and Authentication (Organizational Users)
  - IA-5 Authenticator Management

- **SC — System and Communications Protection**
  - SC-7 Boundary Protection
  - SC-8 Transmission Confidentiality and Integrity
  - SC-12 Cryptographic Key Establishment and Management
  - SC-13 Cryptographic Protection
  - SC-28 Protection of Information at Rest

- **SI — System and Information Integrity**
  - SI-4 System Monitoring
  - SI-7 Software, Firmware, and Information Integrity

What IS NOT encoded:

- PM (Program Management), PL (Planning), CA (Assessment),
  RA (Risk Assessment), IR (Incident Response process), AT
  (Awareness and Training) controls are program-level obligations
  verifiable through documentation, not per-call evidence.
- PE (Physical and Environmental Protection) is out-of-band.

Sources:

- NIST SP 800-53 Rev. 5:
  https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final
- NIST SP 800-53B Control Baselines:
  https://csrc.nist.gov/pubs/sp/800/53/b/upd1/final
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_NIST_800_53 = "https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final"
_VERSION = "SP 800-53 Rev. 5 (September 2020, updated 2023)"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="NIST-800-53",
        article=article,
        url=_NIST_800_53,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── AC — Access Control ────────────────────────────────────────────


_AC_2 = ComplianceRuleSpec(
    name="ac_2_account_management",
    description=(
        "AC-2 Account Management — the organization identifies and "
        "selects account types; assigns account managers; establishes "
        "conditions for group and role membership; and monitors the "
        "use of accounts. Calls must name the account_id and its type."
    ),
    tags=frozenset({"nist_moderate", "information_system_access"}),
    checks=(
        MetadataCheck(metadata_key="account_id"),
        MetadataCheck(
            metadata_key="account_type",
            allowed_values=frozenset(
                {
                    "individual",
                    "shared",
                    "group",
                    "system",
                    "application",
                    "guest",
                    "emergency",
                    "developer",
                    "temporary",
                }
            ),
        ),
    ),
    deny_message=(
        "NIST AC-2: Access requires an account_id and a permitted "
        "account_type."
    ),
    citation=_cite("AC-2"),
)


_AC_3 = ComplianceRuleSpec(
    name="ac_3_access_enforcement",
    description=(
        "AC-3 Access Enforcement — the system enforces approved "
        "authorizations for logical access to information and system "
        "resources in accordance with applicable access control "
        "policies."
    ),
    tags=frozenset({"nist_moderate", "information_system_access"}),
    checks=(
        MetadataCheck(metadata_key="authorization_decision_id"),
    ),
    deny_message=(
        "NIST AC-3: Access requires an authorization_decision_id "
        "from the PDP."
    ),
    citation=_cite("AC-3"),
)


_AC_5 = ComplianceRuleSpec(
    name="ac_5_separation_of_duties",
    description=(
        "AC-5 Separation of Duties — the organization separates duties "
        "of individuals as necessary to prevent malevolent activity "
        "without collusion. Dual-control actions must carry both "
        "performer and approver distinct identifiers."
    ),
    tags=frozenset({"dual_control", "sensitive_mutation"}),
    checks=(
        MetadataCheck(metadata_key="performer_id"),
        MetadataCheck(metadata_key="approver_id"),
    ),
    deny_message=(
        "NIST AC-5: Dual-control actions require distinct performer_id "
        "and approver_id metadata."
    ),
    citation=_cite("AC-5"),
)


_AC_6 = ComplianceRuleSpec(
    name="ac_6_least_privilege",
    description=(
        "AC-6 Least Privilege — the organization employs the principle "
        "of least privilege, allowing only authorized accesses for "
        "users (or processes acting on behalf of users) that are "
        "necessary to accomplish assigned tasks."
    ),
    tags=frozenset({"nist_moderate", "privileged_function"}),
    checks=(
        MetadataCheck(metadata_key="granted_scope"),
    ),
    deny_message=(
        "NIST AC-6: Privileged functions require a granted_scope."
    ),
    citation=_cite("AC-6"),
)


_AC_17 = ComplianceRuleSpec(
    name="ac_17_remote_access",
    description=(
        "AC-17 Remote Access — the organization authorizes remote "
        "access to the system prior to allowing such connections. "
        "Remote connections must declare the remote_access_method."
    ),
    tags=frozenset({"remote_access"}),
    checks=(
        MetadataCheck(
            metadata_key="remote_access_method",
            allowed_values=frozenset(
                {
                    "vpn_ipsec",
                    "vpn_tls",
                    "zero_trust_ztna",
                    "bastion_host",
                    "jump_server",
                }
            ),
        ),
    ),
    deny_message=(
        "NIST AC-17: Remote access requires a remote_access_method "
        "(vpn / ztna / bastion)."
    ),
    citation=_cite("AC-17"),
)


# ── AU — Audit and Accountability ──────────────────────────────────


_AU_2 = ComplianceRuleSpec(
    name="au_2_event_logging",
    description=(
        "AU-2 Event Logging — the organization identifies the types of "
        "events that the system is capable of logging in support of "
        "the audit function, and coordinates event-logging activities "
        "to select events for logging."
    ),
    tags=frozenset({"nist_moderate"}),
    checks=(
        MetadataCheck(metadata_key="audit_event_type"),
    ),
    deny_message=(
        "NIST AU-2: Calls require an audit_event_type for the log."
    ),
    citation=_cite("AU-2"),
)


_AU_3 = ComplianceRuleSpec(
    name="au_3_audit_content",
    description=(
        "AU-3 Content of Audit Records — the system generates audit "
        "records containing information that establishes what type of "
        "event occurred, when it occurred, where it occurred, source, "
        "outcome, and identity of any individuals."
    ),
    tags=frozenset({"nist_moderate"}),
    checks=(
        MetadataCheck(metadata_key="source_network_address"),
        MetadataCheck(metadata_key="outcome"),
    ),
    deny_message=(
        "NIST AU-3: Audit records require source_network_address and "
        "outcome metadata."
    ),
    citation=_cite("AU-3"),
)


_AU_12 = ComplianceRuleSpec(
    name="au_12_audit_record_generation",
    description=(
        "AU-12 Audit Record Generation — the system provides audit "
        "record generation capability for the event types the system "
        "is capable of auditing, and allows authorized individuals to "
        "select event types to be logged by specific components."
    ),
    tags=frozenset({"nist_moderate"}),
    checks=(
        MetadataCheck(metadata_key="audit_correlation_id"),
    ),
    deny_message=(
        "NIST AU-12: Calls require an audit_correlation_id."
    ),
    citation=_cite("AU-12"),
)


# ── IA — Identification and Authentication ─────────────────────────


_IA_2 = ComplianceRuleSpec(
    name="ia_2_user_identification_auth",
    description=(
        "IA-2 Identification and Authentication (Organizational Users) "
        "— the system uniquely identifies and authenticates "
        "organizational users and associates that unique "
        "identification with processes acting on behalf of those users."
    ),
    tags=frozenset({"nist_moderate"}),
    checks=(
        MetadataCheck(metadata_key="unique_user_identifier"),
        MetadataCheck(metadata_key="authentication_assurance_level"),
    ),
    deny_message=(
        "NIST IA-2: Calls require a unique_user_identifier and "
        "authentication_assurance_level (AAL1/AAL2/AAL3)."
    ),
    citation=_cite("IA-2"),
)


_IA_5 = ComplianceRuleSpec(
    name="ia_5_authenticator_management",
    description=(
        "IA-5 Authenticator Management — the organization manages "
        "system authenticators by verifying identity of the individual, "
        "group, role, service, or device receiving the authenticator."
    ),
    tags=frozenset({"authenticator_issuance", "credential_issuance"}),
    checks=(
        MetadataCheck(metadata_key="issuance_ticket_id"),
    ),
    deny_message=(
        "NIST IA-5: Authenticator issuance requires an "
        "issuance_ticket_id."
    ),
    citation=_cite("IA-5"),
)


# ── SC — System and Communications Protection ─────────────────────


_SC_7 = ComplianceRuleSpec(
    name="sc_7_boundary_protection",
    description=(
        "SC-7 Boundary Protection — the system monitors and controls "
        "communications at the external boundary of the system and at "
        "key internal boundaries within the system."
    ),
    tags=frozenset({"external_communication"}),
    checks=(
        MetadataCheck(metadata_key="boundary_gateway_id"),
    ),
    deny_message=(
        "NIST SC-7: External communications require a "
        "boundary_gateway_id."
    ),
    citation=_cite("SC-7"),
)


_SC_8 = ComplianceRuleSpec(
    name="sc_8_transmission_protection",
    description=(
        "SC-8 Transmission Confidentiality and Integrity — the system "
        "protects the confidentiality and integrity of transmitted "
        "information."
    ),
    tags=frozenset({"nist_moderate", "data_in_transit"}),
    checks=(
        MetadataCheck(
            metadata_key="transmission_protection",
            allowed_values=frozenset({"tls_1_2", "tls_1_3", "mtls", "ipsec"}),
        ),
    ),
    deny_message=(
        "NIST SC-8: Data in transit requires TLS 1.2 or higher / mTLS "
        "/ IPsec."
    ),
    citation=_cite("SC-8"),
)


_SC_12 = ComplianceRuleSpec(
    name="sc_12_key_establishment",
    description=(
        "SC-12 Cryptographic Key Establishment and Management — the "
        "organization establishes and manages cryptographic keys when "
        "cryptography is employed within the system."
    ),
    tags=frozenset({"key_operation"}),
    checks=(
        MetadataCheck(metadata_key="key_management_system_id"),
    ),
    deny_message=(
        "NIST SC-12: Cryptographic key operations require a "
        "key_management_system_id."
    ),
    citation=_cite("SC-12"),
)


_SC_13 = ComplianceRuleSpec(
    name="sc_13_cryptographic_protection",
    description=(
        "SC-13 Cryptographic Protection — the system implements "
        "FIPS-validated or NSA-approved cryptography when used to "
        "protect information."
    ),
    tags=frozenset({"crypto_operation", "federal_data"}),
    checks=(
        MetadataCheck(
            metadata_key="crypto_validation",
            allowed_values=frozenset(
                {"fips_140_2", "fips_140_3", "cnsa_suite_2_0"}
            ),
        ),
    ),
    deny_message=(
        "NIST SC-13: Federal crypto requires a validation attestation "
        "(fips_140_2 / fips_140_3 / cnsa_suite_2_0)."
    ),
    citation=_cite("SC-13"),
)


_SC_28 = ComplianceRuleSpec(
    name="sc_28_information_at_rest",
    description=(
        "SC-28 Protection of Information at Rest — the system protects "
        "the confidentiality and/or integrity of information at rest."
    ),
    tags=frozenset({"nist_moderate", "data_at_rest"}),
    checks=(
        MetadataCheck(
            metadata_key="at_rest_protection",
            allowed_values=frozenset(
                {
                    "fips_140_encryption",
                    "hsm_backed_encryption",
                    "cloud_kms_encryption",
                }
            ),
        ),
    ),
    deny_message=(
        "NIST SC-28: Data at rest requires an at_rest_protection "
        "attestation."
    ),
    citation=_cite("SC-28"),
)


# ── SI — System and Information Integrity ─────────────────────────


_SI_4 = ComplianceRuleSpec(
    name="si_4_system_monitoring",
    description=(
        "SI-4 System Monitoring — the system monitors the system to "
        "detect attacks and indicators of potential attacks, and "
        "unauthorized local, network, and remote connections."
    ),
    tags=frozenset({"nist_moderate"}),
    checks=(
        MetadataCheck(metadata_key="monitoring_sensor_id"),
    ),
    deny_message=(
        "NIST SI-4: Monitored calls require a monitoring_sensor_id."
    ),
    citation=_cite("SI-4"),
)


_SI_7 = ComplianceRuleSpec(
    name="si_7_software_integrity",
    description=(
        "SI-7 Software, Firmware, and Information Integrity — the "
        "organization employs integrity verification tools to detect "
        "unauthorized changes to software, firmware, and information."
    ),
    tags=frozenset({"software_deploy", "firmware_update"}),
    checks=(
        MetadataCheck(metadata_key="integrity_attestation_id"),
    ),
    deny_message=(
        "NIST SI-7: Software or firmware changes require an "
        "integrity_attestation_id (SBOM / signed attestation)."
    ),
    citation=_cite("SI-7"),
)


def build_nist_800_53_policy(
    *,
    policy_id: str = "nist-800-53-moderate-pack",
    version: str = "1.0.0",
) -> ComplianceRulePolicy:
    """Return the NIST SP 800-53 Rev. 5 Moderate baseline pack."""
    return ComplianceRulePolicy(
        rules=[
            _AC_2,
            _AC_3,
            _AC_5,
            _AC_6,
            _AC_17,
            _AU_2,
            _AU_3,
            _AU_12,
            _IA_2,
            _IA_5,
            _SC_7,
            _SC_8,
            _SC_12,
            _SC_13,
            _SC_28,
            _SI_4,
            _SI_7,
        ],
        framework="NIST-800-53",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_nist_800_53_policy"]
