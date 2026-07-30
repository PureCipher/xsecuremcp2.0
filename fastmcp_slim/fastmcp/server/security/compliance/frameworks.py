"""Compliance frameworks and requirement definitions.

Defines compliance frameworks (e.g. SOC2, ISO27001, custom) with
typed requirements that can be checked against system state.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class ComplianceStatus(enum.Enum):
    """Status of a compliance requirement check."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class RequirementCategory(enum.Enum):
    """Category of compliance requirement."""

    ACCESS_CONTROL = "access_control"
    AUDIT_LOGGING = "audit_logging"
    DATA_PROTECTION = "data_protection"
    INCIDENT_RESPONSE = "incident_response"
    RISK_MANAGEMENT = "risk_management"
    CERTIFICATION = "certification"
    CONSENT_MANAGEMENT = "consent_management"
    SANDBOXING = "sandboxing"
    FEDERATION = "federation"
    PROVENANCE = "provenance"


@dataclass
class ComplianceRequirement:
    """A single compliance requirement within a framework.

    Each requirement maps to a check function that evaluates system
    state and returns a ComplianceStatus.
    """

    requirement_id: str = ""
    name: str = ""
    description: str = ""
    category: RequirementCategory = RequirementCategory.RISK_MANAGEMENT
    mandatory: bool = True
    check_key: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.requirement_id:
            self.requirement_id = f"req-{uuid.uuid4().hex[:8]}"
        if not self.check_key:
            self.check_key = self.requirement_id

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "mandatory": self.mandatory,
            "check_key": self.check_key,
        }


@dataclass
class ComplianceFramework:
    """A compliance framework containing a set of requirements.

    Frameworks define the requirements to check and provide
    aggregate compliance scoring.
    """

    framework_id: str = ""
    name: str = ""
    version: str = "1.0"
    description: str = ""
    requirements: list[ComplianceRequirement] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.framework_id:
            self.framework_id = f"fw-{uuid.uuid4().hex[:8]}"

    def add_requirement(self, requirement: ComplianceRequirement) -> None:
        """Add a requirement to the framework."""
        self.requirements.append(requirement)

    def remove_requirement(self, requirement_id: str) -> bool:
        """Remove a requirement by ID."""
        before = len(self.requirements)
        self.requirements = [
            r for r in self.requirements if r.requirement_id != requirement_id
        ]
        return len(self.requirements) < before

    def get_requirement(self, requirement_id: str) -> ComplianceRequirement | None:
        """Get a requirement by ID."""
        for r in self.requirements:
            if r.requirement_id == requirement_id:
                return r
        return None

    def get_requirements_by_category(
        self, category: RequirementCategory
    ) -> list[ComplianceRequirement]:
        """Get all requirements in a category."""
        return [r for r in self.requirements if r.category == category]

    def get_mandatory_requirements(self) -> list[ComplianceRequirement]:
        """Get all mandatory requirements."""
        return [r for r in self.requirements if r.mandatory]

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def mandatory_count(self) -> int:
        return len(self.get_mandatory_requirements())

    def to_dict(self) -> dict:
        return {
            "framework_id": self.framework_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "requirement_count": self.requirement_count,
            "mandatory_count": self.mandatory_count,
            "requirements": [r.to_dict() for r in self.requirements],
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def securemcp_default() -> ComplianceFramework:
        """Create the default SecureMCP compliance framework.

        Covers all major security areas: trust, policy, consent,
        sandbox, federation, provenance, and certification.
        """
        fw = ComplianceFramework(
            name="SecureMCP Security Framework",
            version="1.0",
            description="Default compliance framework for SecureMCP deployments",
        )

        # Trust & Registry
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="trust-registry-active",
                name="Trust Registry Active",
                description="Trust registry must be operational with registered tools",
                category=RequirementCategory.RISK_MANAGEMENT,
                check_key="trust_registry_active",
            )
        )
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="trust-scores-healthy",
                name="Trust Scores Healthy",
                description="Average trust score across tools must be >= 0.5",
                category=RequirementCategory.RISK_MANAGEMENT,
                check_key="trust_scores_healthy",
            )
        )

        # Policy
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="policy-engine-active",
                name="Policy Engine Active",
                description="Policy engine must be operational",
                category=RequirementCategory.ACCESS_CONTROL,
                check_key="policy_engine_active",
            )
        )
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="no-critical-violations",
                name="No Critical Policy Violations",
                description="No unresolved critical policy violations",
                category=RequirementCategory.ACCESS_CONTROL,
                check_key="no_critical_violations",
            )
        )

        # Audit
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="audit-logging-enabled",
                name="Audit Logging Enabled",
                description="Audit logging must be active for all operations",
                category=RequirementCategory.AUDIT_LOGGING,
                check_key="audit_logging_enabled",
            )
        )

        # Consent
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="consent-tracking-active",
                name="Consent Tracking Active",
                description="Consent graph must be operational",
                category=RequirementCategory.CONSENT_MANAGEMENT,
                check_key="consent_tracking_active",
            )
        )

        # Sandbox
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="sandbox-enforcement-active",
                name="Sandbox Enforcement Active",
                description="Sandbox enforcement must be enabled",
                category=RequirementCategory.SANDBOXING,
                check_key="sandbox_enforcement_active",
            )
        )
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="no-sandbox-violations",
                name="No Unresolved Sandbox Violations",
                description="All sandbox violations must be resolved",
                category=RequirementCategory.SANDBOXING,
                check_key="no_sandbox_violations",
            )
        )

        # Certification
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="tools-certified",
                name="Tools Certified",
                description="All published tools must have valid certifications",
                category=RequirementCategory.CERTIFICATION,
                check_key="tools_certified",
            )
        )

        # Federation
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="no-revoked-tools",
                name="No Revoked Tools Active",
                description="No revoked tools should be in active use",
                category=RequirementCategory.FEDERATION,
                check_key="no_revoked_tools",
            )
        )

        # Provenance
        fw.add_requirement(
            ComplianceRequirement(
                requirement_id="provenance-tracking-active",
                name="Provenance Tracking Active",
                description="Provenance ledger must be operational",
                category=RequirementCategory.PROVENANCE,
                check_key="provenance_tracking_active",
            )
        )

        return fw
