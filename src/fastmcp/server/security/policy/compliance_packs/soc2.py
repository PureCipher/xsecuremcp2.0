"""SOC 2 Trust Services Criteria compliance pack.

Encodes the subset of the AICPA SOC 2 Trust Services Criteria (2017,
including the 2022 points of focus revision) that can be verified at
an MCP tool-call boundary. SOC 2 is an audit framework, not a
regulation — so "compliance" means a service-provider's controls
match the criteria the auditor is testing. Attaching this pack to a
listing says "calls through this listing consistently carry the
metadata the Trust Services auditor expects to see".

SOC 2 organizes criteria into categories; the kernel pack focuses on
the two most mechanically testable ones:

- **CC6 — Logical and Physical Access Controls**, specifically the
  technical access paths (CC6.1, CC6.2, CC6.3, CC6.6, CC6.7, CC6.8).
- **CC7 — System Operations**, specifically monitoring and anomaly
  detection (CC7.2, CC7.3).
- **Confidentiality (C1.1, C1.2)** — handling and disposal.
- **Availability (A1.2)** — backup / recovery annotations.
- **Processing Integrity (PI1.1)** — completeness / accuracy of inputs.

What IS NOT encoded:

- CC1 (Control Environment) and CC2 (Communication and Information)
  describe organizational culture and policy documentation; not
  checkable per-call.
- CC3 (Risk Assessment) is periodic, not per-call.
- CC9 (Risk Mitigation) is post-incident remediation.
- Physical access (CC6.4, CC6.5) is out-of-band.

Sources:

- AICPA Trust Services Criteria (2017 with 2022 revisions), published
  as SOC 2 guidance:
  https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria
- AICPA SOC 2 landing page:
  https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2
"""

from __future__ import annotations

from fastmcp.server.security.policy.policies.compliance_rule import (
    ComplianceRulePolicy,
    ComplianceRuleSpec,
    MetadataCheck,
)
from fastmcp.server.security.policy.provider import Citation

_AICPA_TSC = (
    "https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria"
)
_VERSION = "TSC 2017 (with 2022 revisions)"
_RETRIEVED = "2026-05-01"


def _cite(article: str) -> Citation:
    return Citation(
        source="SOC2",
        article=article,
        url=_AICPA_TSC,
        version=_VERSION,
        retrieved_at=_RETRIEVED,
    )


# ── CC6 — Logical and Physical Access Controls ─────────────────────


_CC6_1_AUTH = ComplianceRuleSpec(
    name="cc6_1_logical_access_auth",
    description=(
        "CC6.1 — logical access to systems and data is restricted to "
        "authorized users with a business need. Every call must carry "
        "an authenticated_principal id."
    ),
    tags=frozenset({"soc2_scoped", "production_data", "sensitive_tool"}),
    checks=(
        MetadataCheck(metadata_key="authenticated_principal"),
    ),
    deny_message=(
        "SOC 2 CC6.1: Access to SOC-scoped data requires an "
        "authenticated_principal."
    ),
    citation=_cite("CC6.1"),
)


_CC6_2_ROLE = ComplianceRuleSpec(
    name="cc6_2_user_registration",
    description=(
        "CC6.2 — prior to issuing system credentials and granting "
        "access, the entity registers and authorizes new users. "
        "Callers must carry a role claim backed by the authoritative "
        "identity provider."
    ),
    tags=frozenset({"soc2_scoped", "production_data"}),
    checks=(
        MetadataCheck(metadata_key="role"),
        MetadataCheck(metadata_key="identity_provider"),
    ),
    deny_message=(
        "SOC 2 CC6.2: Access requires a role claim and identity_provider "
        "identifying the issuing IdP."
    ),
    citation=_cite("CC6.2"),
)


_CC6_3_LEAST_PRIV = ComplianceRuleSpec(
    name="cc6_3_least_privilege",
    description=(
        "CC6.3 — the entity authorizes, modifies, or removes access to "
        "data based on roles, responsibilities, or the system design. "
        "Callers must state the scope being exercised so the auditor "
        "can compare against the entitlement."
    ),
    # Only ``privileged_access`` activates this rule. Tagging
    # ``soc2_scoped`` alone must not imply a privilege elevation that
    # requires entitlement_scope (CC6.1/CC6.2/CC7.2 cover baseline
    # SOC2-scoped production calls).
    tags=frozenset({"privileged_access"}),
    checks=(
        MetadataCheck(metadata_key="entitlement_scope"),
    ),
    deny_message=(
        "SOC 2 CC6.3: Privileged access requires an entitlement_scope "
        "limiting what the call is authorized to do."
    ),
    citation=_cite("CC6.3"),
)


_CC6_6_ENCRYPTION = ComplianceRuleSpec(
    name="cc6_6_restrict_external_access",
    description=(
        "CC6.6 — the entity implements logical access security measures "
        "to protect against threats from sources outside its system "
        "boundaries. Boundary-crossing traffic must be encrypted."
    ),
    tags=frozenset({"external_egress", "boundary_crossing"}),
    checks=(
        MetadataCheck(
            metadata_key="transport_security",
            allowed_values=frozenset(
                {"tls_1_2", "tls_1_3", "mtls", "ipsec"}
            ),
        ),
    ),
    deny_message=(
        "SOC 2 CC6.6: External boundary traffic requires "
        "transport_security (tls_1_2 or stronger)."
    ),
    citation=_cite("CC6.6"),
)


_CC6_7_INTEGRITY = ComplianceRuleSpec(
    name="cc6_7_data_transmission_integrity",
    description=(
        "CC6.7 — the entity restricts the transmission, movement, and "
        "removal of information to authorized users and processes, and "
        "protects it during transmission, movement, or removal."
    ),
    tags=frozenset({"soc2_data_movement"}),
    checks=(
        MetadataCheck(metadata_key="data_movement_authorization"),
    ),
    deny_message=(
        "SOC 2 CC6.7: Data movement requires an authorization "
        "identifier (data_movement_authorization)."
    ),
    citation=_cite("CC6.7"),
)


_CC6_8_MALICIOUS = ComplianceRuleSpec(
    name="cc6_8_malicious_software",
    description=(
        "CC6.8 — the entity implements controls to prevent or detect and "
        "act upon the introduction of unauthorized or malicious "
        "software. Binary-deploying tools must attest signature checks."
    ),
    tags=frozenset({"binary_deploy", "code_deploy"}),
    checks=(
        MetadataCheck(
            metadata_key="signature_verified",
            allowed_values=frozenset({"true", "1", "yes"}),
        ),
    ),
    deny_message=(
        "SOC 2 CC6.8: Deploys require signature_verified=true."
    ),
    citation=_cite("CC6.8"),
)


# ── CC7 — System Operations ────────────────────────────────────────


_CC7_2_MONITOR = ComplianceRuleSpec(
    name="cc7_2_monitoring_trace",
    description=(
        "CC7.2 — the entity monitors system components and the operation "
        "of controls to detect anomalies. Callers must attach a trace "
        "id so the monitoring system can correlate."
    ),
    tags=frozenset({"soc2_scoped", "production_data"}),
    checks=(
        MetadataCheck(metadata_key="trace_id"),
    ),
    deny_message=(
        "SOC 2 CC7.2: Monitored calls require a trace_id."
    ),
    citation=_cite("CC7.2"),
)


_CC7_3_INCIDENT = ComplianceRuleSpec(
    name="cc7_3_incident_response_tag",
    description=(
        "CC7.3 — the entity evaluates security events. Calls flagged "
        "as part of an active incident must carry the incident_id so "
        "the accounting can later be reconstructed."
    ),
    tags=frozenset({"incident_response"}),
    checks=(
        MetadataCheck(metadata_key="incident_id"),
    ),
    deny_message=(
        "SOC 2 CC7.3: Incident-response calls require an incident_id."
    ),
    citation=_cite("CC7.3"),
)


# ── Confidentiality ────────────────────────────────────────────────


_C1_1_HANDLE = ComplianceRuleSpec(
    name="c1_1_confidential_handling",
    description=(
        "C1.1 — the entity identifies and maintains confidential "
        "information to meet the entity's objectives related to "
        "confidentiality. Confidential data accesses must state the "
        "confidentiality_tier."
    ),
    tags=frozenset(
        {"confidential", "restricted", "secret", "internal_only"}
    ),
    checks=(
        MetadataCheck(
            metadata_key="confidentiality_tier",
            allowed_values=frozenset(
                {"public", "internal", "confidential", "restricted"}
            ),
        ),
    ),
    deny_message=(
        "SOC 2 C1.1: Confidential data access requires a declared "
        "confidentiality_tier."
    ),
    citation=_cite("C1.1"),
)


_C1_2_DISPOSE = ComplianceRuleSpec(
    name="c1_2_confidential_disposal",
    description=(
        "C1.2 — the entity disposes of confidential information to meet "
        "the entity's objectives related to confidentiality."
    ),
    tags=frozenset({"confidential_disposal", "data_destruction"}),
    checks=(
        MetadataCheck(
            metadata_key="disposal_method",
            allowed_values=frozenset(
                {"cryptographic_erasure", "physical_destruction", "secure_wipe"}
            ),
        ),
    ),
    deny_message=(
        "SOC 2 C1.2: Disposal requires a disposal_method "
        "(cryptographic_erasure / physical_destruction / secure_wipe)."
    ),
    citation=_cite("C1.2"),
)


# ── Availability ───────────────────────────────────────────────────


_A1_2_BACKUP = ComplianceRuleSpec(
    name="a1_2_backup_recovery",
    description=(
        "A1.2 — the entity authorizes, designs, develops or acquires, "
        "implements, operates, approves, maintains, and monitors "
        "environmental protections, software, data backup processes, "
        "and recovery infrastructure."
    ),
    tags=frozenset({"backup_write", "restore_write"}),
    checks=(
        MetadataCheck(metadata_key="backup_policy_id"),
    ),
    deny_message=(
        "SOC 2 A1.2: Backup / recovery operations require a "
        "backup_policy_id identifying the authorized procedure."
    ),
    citation=_cite("A1.2"),
)


# ── Processing Integrity ───────────────────────────────────────────


_PI1_1_INPUT = ComplianceRuleSpec(
    name="pi1_1_input_completeness",
    description=(
        "PI1.1 — the entity obtains or generates, uses, and communicates "
        "relevant, quality information regarding the objectives related "
        "to processing, including definitions of data processed and "
        "product and service specifications."
    ),
    tags=frozenset({"financial_processing", "integrity_critical"}),
    checks=(
        MetadataCheck(metadata_key="input_validation_id"),
    ),
    deny_message=(
        "SOC 2 PI1.1: Integrity-critical processing requires an "
        "input_validation_id."
    ),
    citation=_cite("PI1.1"),
)


def build_soc2_policy(
    *,
    policy_id: str = "soc2-enforceable-pack",
    version: str = "1.1.0",
) -> ComplianceRulePolicy:
    """Return the SOC 2 enforceable-at-tool-boundary rule pack.

    Trust Services Criteria (TSC 2017) are an audit framework; this
    pack encodes only the technical criteria that produce deterministic
    per-call evidence. Attach this pack alongside the capability
    bundle for listings that handle SOC 2-scoped production data.
    """
    return ComplianceRulePolicy(
        rules=[
            _CC6_1_AUTH,
            _CC6_2_ROLE,
            _CC6_3_LEAST_PRIV,
            _CC6_6_ENCRYPTION,
            _CC6_7_INTEGRITY,
            _CC6_8_MALICIOUS,
            _CC7_2_MONITOR,
            _CC7_3_INCIDENT,
            _C1_1_HANDLE,
            _C1_2_DISPOSE,
            _A1_2_BACKUP,
            _PI1_1_INPUT,
        ],
        framework="SOC2",
        policy_id=policy_id,
        version=version,
    )


__all__ = ["build_soc2_policy"]
