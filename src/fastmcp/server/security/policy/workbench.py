"""Policy workbench helpers for UI-driven management flows.

This module keeps higher-level management concepts out of the core engine:

- reusable policy bundles
- environment profiles for migrations
- analytics summaries for the policy console
- human-friendly change summaries between policy snapshots
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastmcp.server.security.policy.serialization import describe_policy_config


@dataclass(frozen=True)
class PolicyEnvironmentProfile:
    """Environment guidance for policy promotion and migration."""

    environment_id: str
    title: str
    description: str
    goals: tuple[str, ...]
    required_controls: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "title": self.title,
            "description": self.description,
            "goals": list(self.goals),
            "required_controls": list(self.required_controls),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PolicyBundle:
    """Reusable policy pack for common SecureMCP operating modes."""

    bundle_id: str
    title: str
    summary: str
    description: str
    risk_posture: str
    recommended_environments: tuple[str, ...]
    tags: tuple[str, ...]
    providers: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "title": self.title,
            "summary": self.summary,
            "description": self.description,
            "risk_posture": self.risk_posture,
            "recommended_environments": list(self.recommended_environments),
            "tags": list(self.tags),
            "provider_count": len(self.providers),
            "provider_summaries": [
                describe_policy_config(provider) for provider in self.providers
            ],
            "providers": [dict(provider) for provider in self.providers],
        }


_ENVIRONMENTS: tuple[PolicyEnvironmentProfile, ...] = (
    PolicyEnvironmentProfile(
        environment_id="development",
        title="Development",
        description="Fast iteration with enough guardrails to catch unsafe rules early.",
        goals=(
            "Keep the chain easy to edit.",
            "Surface risky allow-all rules before they escape dev.",
        ),
        required_controls=(
            "At least one reviewer-aware access rule",
            "A denylist for obvious admin-only surfaces",
        ),
        warnings=(
            "Allow-all rules are acceptable only for short-lived local testing.",
            "Time-based controls can get in the way of local iteration.",
        ),
    ),
    PolicyEnvironmentProfile(
        environment_id="staging",
        title="Staging",
        description="Pre-production validation with production-like access patterns.",
        goals=(
            "Mirror production policy shape closely.",
            "Simulate realistic reviewer and publisher workflows before promotion.",
        ),
        required_controls=(
            "Role-aware access rules",
            "A denylist for sensitive resources",
            "Rate limiting on shared endpoints",
        ),
        warnings=(
            "Large chain replacements should be simulated before approval.",
            "Unassigned or stale proposals should be cleared before promotion.",
        ),
    ),
    PolicyEnvironmentProfile(
        environment_id="production",
        title="Production",
        description="Tight governance for live SecureMCP surfaces and shared tooling.",
        goals=(
            "Enforce least privilege.",
            "Require explicit reviewer ownership and predictable rollout risk.",
        ),
        required_controls=(
            "Role-aware access rules",
            "A denylist for sensitive resources",
            "Rate limiting",
            "Simulation before approval",
        ),
        warnings=(
            "Allow-all rules are a production risk.",
            "Missing rate limiting increases blast radius during abuse or drift.",
            "Replacing the whole chain should be treated as a high-attention change.",
        ),
    ),
)


_BUNDLES: tuple[PolicyBundle, ...] = (
    # ── Compliance Bundles ────────────────────────────────────
    PolicyBundle(
        bundle_id="gdpr-data-protection",
        title="GDPR Data Protection",
        summary="EU General Data Protection Regulation compliance for personal data handling.",
        description=(
            "Enforces GDPR principles for any MCP tool or resource that handles "
            "personal data. Requires a valid legal basis (consent, contract, "
            "legitimate interests, etc.) before allowing access to PII-tagged "
            "resources. Combines GDPR policy with RBAC for data controller/processor "
            "role separation, denylists for raw data exports, rate limiting, and "
            "audit-friendly resource scoping."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "gdpr", "privacy", "eu", "data-protection"),
        providers=(
            {
                "type": "compliance_rule",
                "policy_id": "gdpr-bundle-core",
                "version": "1.0.0",
                "framework": "GDPR",
                "rules": [
                    {
                        "name": "legal_basis_required",
                        "description": (
                            "Personal data access requires a valid legal basis "
                            "under GDPR Article 6"
                        ),
                        "tags": [
                            "gdpr_regulated",
                            "personal_data",
                            "pii",
                            "sensitive_data",
                        ],
                        "checks": [
                            {
                                "metadata_key": "legal_basis",
                                "allowed_values": [
                                    "consent",
                                    "contract",
                                    "legal_obligation",
                                    "legitimate_interests",
                                    "public_interest",
                                    "vital_interests",
                                ],
                            },
                        ],
                        "deny_message": (
                            "GDPR: Personal data access requires a valid "
                            "legal basis (consent, contract, etc.)"
                        ),
                        "allow_message": (
                            "GDPR: Access permitted under stated legal basis"
                        ),
                    },
                ],
            },
            {
                "type": "rbac",
                "policy_id": "gdpr-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "data_subject": ["read_resource"],
                    "data_controller": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                    ],
                    "data_processor": ["call_tool", "read_resource"],
                    "dpo": ["call_tool", "read_resource", "manage_policy", "review_listing"],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "gdpr-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "data:export-raw-*",
                    "data:bulk-download-*",
                ],
            },
            {
                "type": "rate_limit",
                "policy_id": "gdpr-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 100,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="hipaa-health-data",
        title="HIPAA Health Data Protection",
        summary="US HIPAA compliance for protected health information in MCP workflows.",
        description=(
            "Enforces HIPAA principles for any MCP tool or resource handling "
            "protected health information (PHI). Requires authorized roles "
            "(healthcare provider, business associate, etc.) and a stated purpose "
            "before granting access. Includes strict RBAC, PHI-tagged resource "
            "denylists, business-hours restrictions for administrative actions, "
            "and conservative rate limits."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "hipaa", "healthcare", "phi", "us"),
        providers=(
            {
                "type": "compliance_rule",
                "policy_id": "hipaa-bundle-core",
                "version": "1.0.0",
                "framework": "HIPAA",
                "rules": [
                    {
                        "name": "authorized_role_required",
                        "description": (
                            "PHI access requires an authorized covered-entity "
                            "or business-associate role"
                        ),
                        "tags": [
                            "health_data",
                            "hipaa_regulated",
                            "medical_record",
                            "phi",
                        ],
                        "checks": [
                            {
                                "metadata_key": "actor_role",
                                "allowed_values": [
                                    "business_associate",
                                    "health_plan",
                                    "healthcare_clearinghouse",
                                    "healthcare_provider",
                                ],
                            },
                            {
                                "metadata_key": "purpose",
                            },
                        ],
                        "deny_message": (
                            "HIPAA: PHI access requires an authorized role "
                            "and a stated purpose (minimum necessary principle)"
                        ),
                        "allow_message": (
                            "HIPAA: PHI access permitted for authorized role "
                            "with stated purpose"
                        ),
                    },
                ],
            },
            {
                "type": "rbac",
                "policy_id": "hipaa-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "healthcare_provider": [
                        "call_tool",
                        "read_resource",
                    ],
                    "business_associate": ["call_tool", "read_resource"],
                    "compliance_officer": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                        "review_listing",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "hipaa-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "data:phi-export-*",
                    "data:bulk-patient-*",
                ],
            },
            {
                "type": "time_based",
                "policy_id": "hipaa-bundle-business-hours",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 6,
                "end_hour": 22,
                "utc_offset_hours": -5,
            },
            {
                "type": "rate_limit",
                "policy_id": "hipaa-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 60,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="soc2-trust-services",
        title="SOC 2 Trust Services",
        summary="Controls aligned with SOC 2 trust service criteria for SaaS and cloud MCP services.",
        description=(
            "Implements access controls aligned with SOC 2 trust service criteria: "
            "security, availability, and confidentiality. Uses strict RBAC with "
            "separation of duties, denylists for sensitive administrative surfaces, "
            "business-hours restrictions for change management, and conservative "
            "rate limiting to protect availability."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "soc2", "trust-services", "saas", "cloud"),
        providers=(
            {
                "type": "allowlist",
                "policy_id": "soc2-bundle-allowlist",
                "version": "1.0.0",
                "allowed": [
                    "tool:*",
                    "registry:submit",
                    "registry:review",
                    "registry:policy",
                ],
            },
            {
                "type": "rbac",
                "policy_id": "soc2-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "viewer": ["read_resource"],
                    "operator": ["call_tool", "read_resource"],
                    "publisher": ["call_tool", "read_resource", "submit_listing"],
                    "reviewer": [
                        "call_tool",
                        "read_resource",
                        "submit_listing",
                        "review_listing",
                    ],
                    "security_admin": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                        "review_listing",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "soc2-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "config:*",
                    "debug:*",
                ],
            },
            {
                "type": "time_based",
                "policy_id": "soc2-bundle-change-window",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 8,
                "end_hour": 18,
                "utc_offset_hours": 0,
            },
            {
                "type": "rate_limit",
                "policy_id": "soc2-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 150,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="zero-trust-lockdown",
        title="Zero Trust Lockdown",
        summary="Deny-by-default posture requiring explicit approval for every resource and action.",
        description=(
            "Implements a zero-trust architecture: all access is denied by default "
            "and must be explicitly granted per resource. Uses resource-scoped "
            "policies for fine-grained control, strict RBAC with no wildcard "
            "permissions, aggressive rate limits, and metadata-based verification "
            "via ABAC conditions."
        ),
        risk_posture="locked_down",
        recommended_environments=("production",),
        tags=("compliance", "zero-trust", "locked-down", "high-security"),
        providers=(
            {
                "type": "resource_scoped",
                "policy_id": "zero-trust-resource-scoping",
                "version": "1.0.0",
                "resource_rules": {
                    "tool:": {"type": "allow_all"},
                    "registry:submit": {"type": "allow_all"},
                },
                "default": {"type": "deny_all"},
                "prefix_match": True,
            },
            {
                "type": "rbac",
                "policy_id": "zero-trust-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "operator": ["call_tool", "read_resource"],
                    "publisher": ["call_tool", "read_resource", "submit_listing"],
                    "reviewer": [
                        "call_tool",
                        "read_resource",
                        "submit_listing",
                        "review_listing",
                    ],
                    "security_admin": ["manage_policy"],
                },
                "default_decision": "deny",
            },
            {
                "type": "abac",
                "policy_id": "zero-trust-verification",
                "version": "1.0.0",
                "metadata_conditions": {"verified": "true"},
                "require_all": True,
            },
            {
                "type": "denylist",
                "policy_id": "zero-trust-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "config:*",
                    "debug:*",
                    "data:export-*",
                    "data:bulk-*",
                ],
            },
            {
                "type": "rate_limit",
                "policy_id": "zero-trust-rate-limit",
                "version": "1.0.0",
                "max_requests": 50,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="pci-dss-cardholder-data",
        title="PCI DSS Cardholder Data Protection",
        summary="Payment Card Industry Data Security Standard controls for cardholder data.",
        description=(
            "Enforces PCI DSS requirements for any MCP tool or resource handling "
            "cardholder data (CHD) or sensitive authentication data (SAD). Requires "
            "a valid data handling justification and authorized processor role before "
            "granting access. Combines PCI DSS compliance rules with strict RBAC, "
            "denylists for raw card data exports, business-hours restrictions for "
            "data operations, and conservative rate limits."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "pci-dss", "payment", "cardholder", "financial"),
        providers=(
            {
                "type": "compliance_rule",
                "policy_id": "pci-dss-bundle-core",
                "version": "1.0.0",
                "framework": "PCI DSS",
                "rules": [
                    {
                        "name": "cardholder_data_protection",
                        "description": (
                            "Cardholder data access requires authorized processor "
                            "role and valid business justification (PCI DSS Req 7)"
                        ),
                        "tags": [
                            "cardholder_data",
                            "pci_regulated",
                            "payment_data",
                            "sad",
                        ],
                        "checks": [
                            {
                                "metadata_key": "processor_role",
                                "allowed_values": [
                                    "payment_processor",
                                    "acquiring_bank",
                                    "issuing_bank",
                                    "service_provider",
                                    "merchant_admin",
                                ],
                            },
                            {
                                "metadata_key": "business_justification",
                                "allowed_values": [
                                    "transaction_processing",
                                    "fraud_investigation",
                                    "dispute_resolution",
                                    "compliance_audit",
                                    "system_maintenance",
                                ],
                            },
                        ],
                        "deny_message": (
                            "PCI DSS: Cardholder data access requires an "
                            "authorized processor role and valid business "
                            "justification (Requirement 7: Restrict access)"
                        ),
                        "allow_message": (
                            "PCI DSS: Cardholder data access permitted for "
                            "authorized role with valid justification"
                        ),
                    },
                ],
            },
            {
                "type": "rbac",
                "policy_id": "pci-dss-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "payment_processor": ["call_tool", "read_resource"],
                    "merchant_admin": ["call_tool", "read_resource"],
                    "security_assessor": [
                        "call_tool",
                        "read_resource",
                        "review_listing",
                    ],
                    "compliance_officer": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                        "review_listing",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "pci-dss-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "data:card-export-*",
                    "data:pan-bulk-*",
                    "data:cvv-*",
                    "debug:*",
                ],
            },
            {
                "type": "time_based",
                "policy_id": "pci-dss-bundle-business-hours",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 6,
                "end_hour": 22,
                "utc_offset_hours": 0,
            },
            {
                "type": "rate_limit",
                "policy_id": "pci-dss-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 60,
                "window_seconds": 1800,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="ccpa-consumer-privacy",
        title="CCPA/CPRA Consumer Privacy",
        summary="California Consumer Privacy Act controls for personal information handling.",
        description=(
            "Enforces CCPA/CPRA requirements for MCP tools and resources handling "
            "California consumer personal information. Requires a valid processing "
            "purpose and authorized business role before granting access. Supports "
            "opt-out verification for data sales/sharing. Includes RBAC for privacy "
            "team roles, denylists for unauthorized data monetization, and rate limits."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "ccpa", "cpra", "privacy", "california", "us"),
        providers=(
            {
                "type": "compliance_rule",
                "policy_id": "ccpa-bundle-core",
                "version": "1.0.0",
                "framework": "CCPA/CPRA",
                "rules": [
                    {
                        "name": "processing_purpose_required",
                        "description": (
                            "Consumer PI access requires a valid processing purpose "
                            "aligned with CCPA permitted purposes"
                        ),
                        "tags": [
                            "ccpa_regulated",
                            "consumer_pi",
                            "personal_information",
                            "sensitive_pi",
                        ],
                        "checks": [
                            {
                                "metadata_key": "processing_purpose",
                                "allowed_values": [
                                    "service_delivery",
                                    "security_integrity",
                                    "debugging",
                                    "short_term_transient",
                                    "quality_maintenance",
                                    "research",
                                    "consumer_requested",
                                ],
                            },
                            {
                                "metadata_key": "business_role",
                                "allowed_values": [
                                    "business_operator",
                                    "service_provider",
                                    "contractor",
                                    "privacy_officer",
                                ],
                            },
                        ],
                        "deny_message": (
                            "CCPA/CPRA: Consumer personal information access "
                            "requires a valid processing purpose and authorized "
                            "business role"
                        ),
                        "allow_message": (
                            "CCPA/CPRA: Consumer PI access permitted for "
                            "authorized role with valid purpose"
                        ),
                    },
                    {
                        "name": "opt_out_check",
                        "description": (
                            "Data sharing/selling requires verification that "
                            "the consumer has not opted out"
                        ),
                        "tags": ["data_sharing", "data_selling", "cross_context"],
                        "checks": [
                            {
                                "metadata_key": "consumer_opt_out_verified",
                                "allowed_values": ["false"],
                            },
                        ],
                        "deny_message": (
                            "CCPA/CPRA: Data sharing/selling blocked — consumer "
                            "opt-out status must be verified as not opted out"
                        ),
                        "allow_message": (
                            "CCPA/CPRA: Data sharing permitted — consumer has "
                            "not opted out"
                        ),
                    },
                ],
            },
            {
                "type": "rbac",
                "policy_id": "ccpa-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "business_operator": ["call_tool", "read_resource"],
                    "service_provider": ["call_tool", "read_resource"],
                    "privacy_officer": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                        "review_listing",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "ccpa-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "data:sell-*",
                    "data:share-unverified-*",
                    "data:bulk-consumer-*",
                ],
            },
            {
                "type": "rate_limit",
                "policy_id": "ccpa-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 100,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="ferpa-student-records",
        title="FERPA Student Records Protection",
        summary="Family Educational Rights and Privacy Act controls for student education records.",
        description=(
            "Enforces FERPA requirements for MCP tools and resources handling "
            "student education records. Requires authorized educational roles and "
            "a legitimate educational interest before granting access. Supports "
            "directory information exceptions. Includes RBAC for school officials, "
            "denylists for unauthorized bulk exports, and rate limits."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("compliance", "ferpa", "education", "student-records", "us"),
        providers=(
            {
                "type": "compliance_rule",
                "policy_id": "ferpa-bundle-core",
                "version": "1.0.0",
                "framework": "FERPA",
                "rules": [
                    {
                        "name": "educational_interest_required",
                        "description": (
                            "Student record access requires an authorized school "
                            "official role and a legitimate educational interest"
                        ),
                        "tags": [
                            "ferpa_regulated",
                            "student_record",
                            "education_record",
                            "student_pii",
                        ],
                        "checks": [
                            {
                                "metadata_key": "official_role",
                                "allowed_values": [
                                    "teacher",
                                    "school_administrator",
                                    "counselor",
                                    "registrar",
                                    "financial_aid_officer",
                                    "institutional_researcher",
                                ],
                            },
                            {
                                "metadata_key": "educational_interest",
                            },
                        ],
                        "deny_message": (
                            "FERPA: Student record access requires an authorized "
                            "school official role and a legitimate educational interest"
                        ),
                        "allow_message": (
                            "FERPA: Student record access permitted for "
                            "authorized official with legitimate interest"
                        ),
                    },
                    {
                        "name": "directory_information_exception",
                        "description": (
                            "Directory information (name, enrollment status) may "
                            "be shared without consent unless student has opted out"
                        ),
                        "tags": ["directory_information"],
                        "checks": [
                            {
                                "metadata_key": "student_opted_out",
                                "allowed_values": ["false"],
                            },
                        ],
                        "deny_message": (
                            "FERPA: Student has opted out of directory information "
                            "disclosure"
                        ),
                        "allow_message": (
                            "FERPA: Directory information disclosure permitted — "
                            "student has not opted out"
                        ),
                    },
                ],
                "require_all_rules": False,
            },
            {
                "type": "rbac",
                "policy_id": "ferpa-bundle-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "teacher": ["call_tool", "read_resource"],
                    "school_administrator": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                    ],
                    "counselor": ["call_tool", "read_resource"],
                    "registrar": [
                        "call_tool",
                        "read_resource",
                        "submit_listing",
                    ],
                    "compliance_officer": [
                        "call_tool",
                        "read_resource",
                        "manage_policy",
                        "review_listing",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "ferpa-bundle-denylist",
                "version": "1.0.0",
                "denied": [
                    "admin-panel",
                    "data:student-export-*",
                    "data:bulk-transcript-*",
                    "data:discipline-record-*",
                ],
            },
            {
                "type": "rate_limit",
                "policy_id": "ferpa-bundle-rate-limit",
                "version": "1.0.0",
                "max_requests": 80,
                "window_seconds": 3600,
            },
        ),
    ),
    # ── Registry Operations Bundles ───────────────────────────
    PolicyBundle(
        bundle_id="registry-balanced",
        title="Balanced Registry Guardrails",
        summary="A balanced baseline for public tool browsing and moderated operations.",
        description=(
            "Allows published tools and registry workflows, gates actions by role, "
            "blocks obvious admin-only surfaces, and adds rate limiting."
        ),
        risk_posture="balanced",
        recommended_environments=("development", "staging"),
        tags=("registry", "starter", "balanced"),
        providers=(
            {
                "type": "allowlist",
                "policy_id": "registry-balanced-allowlist",
                "version": "1.0.0",
                "allowed": [
                    "tool:*",
                    "registry:submit",
                    "registry:review",
                    "registry:policy",
                ],
            },
            {
                "type": "rbac",
                "policy_id": "registry-balanced-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "viewer": ["call_tool", "read_resource"],
                    "publisher": ["call_tool", "read_resource", "submit_listing"],
                    "reviewer": [
                        "call_tool",
                        "read_resource",
                        "submit_listing",
                        "review_listing",
                        "manage_policy",
                    ],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "registry-balanced-denylist",
                "version": "1.0.0",
                "denied": ["admin-panel"],
            },
            {
                "type": "rate_limit",
                "policy_id": "registry-balanced-rate-limit",
                "version": "1.0.0",
                "max_requests": 250,
                "window_seconds": 3600,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="registry-strict-change-control",
        title="Strict Change Control",
        summary="Production-minded controls for reviewer-owned policy and listing changes.",
        description=(
            "Builds on the balanced bundle and adds business-hours control for "
            "sensitive review and policy actions."
        ),
        risk_posture="strict",
        recommended_environments=("staging", "production"),
        tags=("registry", "strict", "production"),
        providers=(
            {
                "type": "allowlist",
                "policy_id": "registry-strict-allowlist",
                "version": "1.0.0",
                "allowed": [
                    "tool:*",
                    "registry:submit",
                    "registry:review",
                    "registry:policy",
                ],
            },
            {
                "type": "rbac",
                "policy_id": "registry-strict-rbac",
                "version": "1.0.0",
                "role_mappings": {
                    "publisher": ["submit_listing"],
                    "reviewer": ["review_listing", "manage_policy"],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
            {
                "type": "denylist",
                "policy_id": "registry-strict-denylist",
                "version": "1.0.0",
                "denied": ["admin-panel"],
            },
            {
                "type": "rate_limit",
                "policy_id": "registry-strict-rate-limit",
                "version": "1.0.0",
                "max_requests": 120,
                "window_seconds": 1800,
            },
            {
                "type": "time_based",
                "policy_id": "registry-strict-business-hours",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 8,
                "end_hour": 19,
                "utc_offset_hours": 0,
            },
        ),
    ),
    PolicyBundle(
        bundle_id="published-tools-only",
        title="Published Tools Only",
        summary="A lean pack for read-focused catalogs that should not mutate registry state.",
        description=(
            "Allows published tools, blocks admin surfaces, and omits publish/review "
            "flows for browse-only deployments."
        ),
        risk_posture="locked_down",
        recommended_environments=("development", "production"),
        tags=("catalog", "readonly", "viewer"),
        providers=(
            {
                "type": "allowlist",
                "policy_id": "catalog-only-allowlist",
                "version": "1.0.0",
                "allowed": ["tool:*"],
            },
            {
                "type": "denylist",
                "policy_id": "catalog-only-denylist",
                "version": "1.0.0",
                "denied": [
                    "registry:submit",
                    "registry:review",
                    "registry:policy",
                    "admin-panel",
                ],
            },
            {
                "type": "rate_limit",
                "policy_id": "catalog-only-rate-limit",
                "version": "1.0.0",
                "max_requests": 300,
                "window_seconds": 3600,
            },
        ),
    ),
)


def list_policy_bundles() -> list[dict[str, Any]]:
    """Return reusable policy bundles for the management UI."""

    return [bundle.to_dict() for bundle in _BUNDLES]


def get_policy_bundle(bundle_id: str) -> dict[str, Any] | None:
    """Return one bundle by identifier."""

    for bundle in _BUNDLES:
        if bundle.bundle_id == bundle_id:
            return bundle.to_dict()
    return None


def list_policy_environments() -> list[dict[str, Any]]:
    """Return known environment profiles for migration guidance."""

    return [environment.to_dict() for environment in _ENVIRONMENTS]


def get_policy_environment(environment_id: str) -> dict[str, Any] | None:
    """Return one environment profile by identifier."""

    for environment in _ENVIRONMENTS:
        if environment.environment_id == environment_id:
            return environment.to_dict()
    return None


def summarize_policy_chain_delta(
    source_configs: list[dict[str, Any]],
    target_configs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a UI-friendly summary of how two chains differ."""

    changed: list[dict[str, Any]] = []
    shared = min(len(source_configs), len(target_configs))
    for index in range(shared):
        source = source_configs[index]
        target = target_configs[index]
        if source != target:
            changed.append(
                {
                    "index": index,
                    "from": describe_policy_config(source),
                    "to": describe_policy_config(target),
                    "from_type": str(
                        source.get("type") or source.get("composition") or ""
                    ),
                    "to_type": str(
                        target.get("type") or target.get("composition") or ""
                    ),
                }
            )

    added = [
        {
            "index": index,
            "summary": describe_policy_config(config),
            "type": str(config.get("type") or config.get("composition") or ""),
        }
        for index, config in enumerate(target_configs[shared:], start=shared)
    ]
    removed = [
        {
            "index": index,
            "summary": describe_policy_config(config),
            "type": str(config.get("type") or config.get("composition") or ""),
        }
        for index, config in enumerate(source_configs[shared:], start=shared)
    ]

    return {
        "source_provider_count": len(source_configs),
        "target_provider_count": len(target_configs),
        "changed_count": len(changed),
        "added_count": len(added),
        "removed_count": len(removed),
        "changed": changed,
        "added": added,
        "removed": removed,
    }


def build_policy_risks(
    *,
    provider_configs: list[dict[str, Any]],
    pending_count: int = 0,
    stale_count: int = 0,
    deny_rate: float = 0.0,
    recent_alert_count: int = 0,
    changed_count: int = 0,
) -> list[dict[str, str]]:
    """Return a small set of human-facing risk flags for the policy UI."""

    types = {
        str(config.get("type") or config.get("composition") or "")
        for config in provider_configs
    }
    risks: list[dict[str, str]] = []

    if "allow_all" in types:
        risks.append(
            {
                "level": "high",
                "title": "Allow-all rule is active",
                "detail": "An allow-all provider weakens least-privilege controls in shared environments.",
            }
        )
    if "rbac" not in types and "role_based" not in types:
        risks.append(
            {
                "level": "medium",
                "title": "No role-aware rule in the chain",
                "detail": "Reviewer, publisher, and admin actions are easier to drift without RBAC coverage.",
            }
        )
    if "rate_limit" not in types:
        risks.append(
            {
                "level": "medium",
                "title": "No rate limiting configured",
                "detail": "Shared registry actions have no per-actor throttle in the current chain.",
            }
        )
    if stale_count > 0:
        risks.append(
            {
                "level": "medium",
                "title": "Stale proposals are waiting",
                "detail": f"{stale_count} proposal(s) are pinned to an older live version.",
            }
        )
    if pending_count >= 4:
        risks.append(
            {
                "level": "low",
                "title": "Review queue is backing up",
                "detail": f"{pending_count} proposals are waiting for review or deployment.",
            }
        )
    if deny_rate >= 0.4 or recent_alert_count >= 2:
        risks.append(
            {
                "level": "high",
                "title": "Policy is actively blocking a lot of traffic",
                "detail": "High deny rates or repeated alerts can indicate drift, abuse, or an overly strict rollout.",
            }
        )
    elif deny_rate >= 0.2:
        risks.append(
            {
                "level": "medium",
                "title": "Deny rate is elevated",
                "detail": "Recent policy decisions are blocking more traffic than normal.",
            }
        )
    if changed_count >= 3:
        risks.append(
            {
                "level": "medium",
                "title": "Recent rollout changed several rules at once",
                "detail": "Larger updates deserve simulation and reviewer ownership before promotion.",
            }
        )

    return risks


def build_environment_recommendations(
    *,
    environment_id: str,
    provider_configs: list[dict[str, Any]],
) -> list[str]:
    """Suggest follow-up steps for a target environment."""

    types = {
        str(config.get("type") or config.get("composition") or "")
        for config in provider_configs
    }
    recommendations: list[str] = []

    if environment_id == "production":
        if "rbac" not in types and "role_based" not in types:
            recommendations.append(
                "Add an RBAC rule before promoting this chain to production."
            )
        if "rate_limit" not in types:
            recommendations.append(
                "Introduce a rate-limit rule before production rollout."
            )
        if "allow_all" in types:
            recommendations.append(
                "Replace allow-all access with explicit allowlists or resource-scoped rules."
            )
    elif environment_id == "staging":
        if "denylist" not in types:
            recommendations.append(
                "Add a denylist for sensitive resources before staging validation."
            )
        if "time_based" not in types and "temporal" not in types:
            recommendations.append(
                "Consider time-based controls if reviewers only manage changes in staffed hours."
            )
    elif environment_id == "development":
        if "allow_all" in types:
            recommendations.append(
                "Keep allow-all rules short-lived and pair them with a migration plan to staging."
            )

    if not recommendations:
        recommendations.append(
            "This chain already lines up well with the selected environment profile."
        )
    return recommendations
