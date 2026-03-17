"""Built-in policy providers for common compliance frameworks.

These are starter implementations that can be extended or replaced
with organization-specific policies. GDPR and HIPAA providers are
automatically registered in the plugin registry at import time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.security.policy.plugin_registry import (
    PolicyTypeDescriptor,
    get_registry,
)
from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

logger = logging.getLogger(__name__)


@dataclass
class TagBasedPolicy:
    """Policy that makes decisions based on component tags.

    Allows defining allow/deny rules for specific tags. Tags not
    covered by any rule are handled by the default_decision.

    Args:
        policy_id: Unique identifier for this policy.
        version: Version string.
        allowed_tags: Tags that should be ALLOWED.
        denied_tags: Tags that should be DENIED.
        default_decision: Decision for unmatched tags.

    Example::

        policy = TagBasedPolicy(
            policy_id="tag-policy",
            allowed_tags={"public", "internal"},
            denied_tags={"deprecated", "unsafe"},
        )
    """

    policy_id: str = "tag-based-policy"
    version: str = "1.0.0"
    allowed_tags: frozenset[str] = field(default_factory=frozenset)
    denied_tags: frozenset[str] = field(default_factory=frozenset)
    default_decision: PolicyDecision = PolicyDecision.ALLOW

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        # Check denied tags first (deny takes precedence)
        denied_matches = context.tags & self.denied_tags
        if denied_matches:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Component has denied tag(s): {', '.join(sorted(denied_matches))}",
                policy_id=self.policy_id,
            )

        # Check if allowed tags are configured and component has them
        if self.allowed_tags:
            allowed_matches = context.tags & self.allowed_tags
            if allowed_matches:
                return PolicyResult(
                    decision=PolicyDecision.ALLOW,
                    reason=f"Component has allowed tag(s): {', '.join(sorted(allowed_matches))}",
                    policy_id=self.policy_id,
                )
            # Has allowed tags configured but component doesn't match any
            if context.tags:
                return PolicyResult(
                    decision=self.default_decision,
                    reason="Component tags do not match any allowed tags",
                    policy_id=self.policy_id,
                )

        return PolicyResult(
            decision=self.default_decision,
            reason="No tag rules matched",
            policy_id=self.policy_id,
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version


@dataclass
class ActionBasedPolicy:
    """Policy that controls access based on action types.

    Args:
        policy_id: Unique identifier for this policy.
        version: Version string.
        allowed_actions: Actions that are ALLOWED (if set, others are denied).
        denied_actions: Actions that are DENIED (others are allowed).
    """

    policy_id: str = "action-based-policy"
    version: str = "1.0.0"
    allowed_actions: frozenset[str] = field(default_factory=frozenset)
    denied_actions: frozenset[str] = field(default_factory=frozenset)

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        if self.denied_actions and context.action in self.denied_actions:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Action '{context.action}' is denied by policy",
                policy_id=self.policy_id,
            )

        if self.allowed_actions and context.action not in self.allowed_actions:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Action '{context.action}' is not in the allowed actions list",
                policy_id=self.policy_id,
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"Action '{context.action}' is permitted",
            policy_id=self.policy_id,
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version


@dataclass
class GDPRPolicy:
    """GDPR compliance policy stub.

    Enforces basic GDPR principles: denies access to components tagged
    with personal data categories unless the actor has appropriate
    consent or legal basis declared in metadata.

    This is a starting point; extend with your organization's specific
    GDPR requirements.
    """

    policy_id: str = "gdpr-v1"
    version: str = "1.0.0"
    personal_data_tags: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"pii", "personal_data", "sensitive_data", "gdpr_regulated"}
        )
    )
    valid_legal_bases: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "consent",
                "contract",
                "legal_obligation",
                "vital_interests",
                "public_interest",
                "legitimate_interests",
            }
        )
    )

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        # Check if component handles personal data
        pd_tags = context.tags & self.personal_data_tags
        if not pd_tags:
            return PolicyResult(
                decision=PolicyDecision.DEFER,
                reason="No personal data tags; GDPR not applicable",
                policy_id=self.policy_id,
            )

        # Require legal basis in metadata
        legal_basis = context.metadata.get("legal_basis")
        if not legal_basis:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Personal data access requires legal basis (tags: {', '.join(sorted(pd_tags))})",
                policy_id=self.policy_id,
                constraints=["legal_basis_required"],
            )

        if legal_basis not in self.valid_legal_bases:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Invalid legal basis '{legal_basis}' for personal data access",
                policy_id=self.policy_id,
                constraints=["valid_legal_basis_required"],
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"GDPR: Access permitted under '{legal_basis}'",
            policy_id=self.policy_id,
            constraints=[f"legal_basis:{legal_basis}"],
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version


@dataclass
class HIPAAPolicy:
    """HIPAA compliance policy stub.

    Enforces basic HIPAA principles: denies access to components tagged
    with protected health information (PHI) unless the actor has
    appropriate authorization.

    This is a starting point; extend with your organization's specific
    HIPAA requirements.
    """

    policy_id: str = "hipaa-v1"
    version: str = "1.0.0"
    phi_tags: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"phi", "health_data", "medical_record", "hipaa_regulated"}
        )
    )
    authorized_roles: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "healthcare_provider",
                "health_plan",
                "healthcare_clearinghouse",
                "business_associate",
            }
        )
    )

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        # Check if component handles PHI
        phi_match = context.tags & self.phi_tags
        if not phi_match:
            return PolicyResult(
                decision=PolicyDecision.DEFER,
                reason="No PHI tags; HIPAA not applicable",
                policy_id=self.policy_id,
            )

        # Require authorized role
        actor_role = context.metadata.get("actor_role")
        if not actor_role:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"PHI access requires authorized role (tags: {', '.join(sorted(phi_match))})",
                policy_id=self.policy_id,
                constraints=["authorized_role_required"],
            )

        if actor_role not in self.authorized_roles:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Role '{actor_role}' is not authorized for PHI access",
                policy_id=self.policy_id,
                constraints=["valid_role_required"],
            )

        # Check minimum necessary principle
        purpose = context.metadata.get("purpose")
        if not purpose:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason="PHI access requires stated purpose (minimum necessary principle)",
                policy_id=self.policy_id,
                constraints=["purpose_required"],
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"HIPAA: Access permitted for role '{actor_role}' with purpose '{purpose}'",
            policy_id=self.policy_id,
            constraints=[f"role:{actor_role}", f"purpose:{purpose}"],
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version


# ── Factory functions for plugin registry ─────────────────────────


def _build_tag_based(config: dict[str, Any]) -> TagBasedPolicy:
    return TagBasedPolicy(
        policy_id=config.get("policy_id", "tag-based-policy"),
        version=config.get("version", "1.0.0"),
        allowed_tags=frozenset(config.get("allowed_tags", [])),
        denied_tags=frozenset(config.get("denied_tags", [])),
        default_decision=PolicyDecision(
            config.get("default_decision", "allow").lower()
        ),
    )


def _build_action_based(config: dict[str, Any]) -> ActionBasedPolicy:
    return ActionBasedPolicy(
        policy_id=config.get("policy_id", "action-based-policy"),
        version=config.get("version", "1.0.0"),
        allowed_actions=frozenset(config.get("allowed_actions", [])),
        denied_actions=frozenset(config.get("denied_actions", [])),
    )


def _build_gdpr(config: dict[str, Any]) -> GDPRPolicy:
    return GDPRPolicy(
        policy_id=config.get("policy_id", "gdpr-v1"),
        version=config.get("version", "1.0.0"),
        personal_data_tags=frozenset(
            config.get(
                "personal_data_tags",
                ["pii", "personal_data", "sensitive_data", "gdpr_regulated"],
            )
        ),
        valid_legal_bases=frozenset(
            config.get(
                "valid_legal_bases",
                [
                    "consent",
                    "contract",
                    "legal_obligation",
                    "vital_interests",
                    "public_interest",
                    "legitimate_interests",
                ],
            )
        ),
    )


def _build_hipaa(config: dict[str, Any]) -> HIPAAPolicy:
    return HIPAAPolicy(
        policy_id=config.get("policy_id", "hipaa-v1"),
        version=config.get("version", "1.0.0"),
        phi_tags=frozenset(
            config.get(
                "phi_tags",
                ["phi", "health_data", "medical_record", "hipaa_regulated"],
            )
        ),
        authorized_roles=frozenset(
            config.get(
                "authorized_roles",
                [
                    "healthcare_provider",
                    "health_plan",
                    "healthcare_clearinghouse",
                    "business_associate",
                ],
            )
        ),
    )


# ── Register compliance types in the plugin registry ──────────────


def _register_compliance_types() -> None:
    """Register GDPR, HIPAA, tag-based, and action-based types."""
    _registry = get_registry()
    compliance_types = [
        PolicyTypeDescriptor(
            type_key="tag_based",
            factory=_build_tag_based,
            display_name="Tag-Based Policy",
            description="Decisions based on component tags (allow/deny tag sets)",
            category="access_control",
            field_specs={
                "allowed_tags": {
                    "label": "Allowed tags",
                    "type": "string_list",
                    "description": "Tags that should be ALLOWED access.",
                    "required": False,
                    "example": ["public", "internal"],
                },
                "denied_tags": {
                    "label": "Denied tags",
                    "type": "string_list",
                    "description": "Tags that should be DENIED access.",
                    "required": False,
                    "example": ["deprecated", "unsafe"],
                },
                "default_decision": {
                    "label": "Default decision",
                    "type": "enum",
                    "description": "Decision for tags not matching any rule.",
                    "required": False,
                    "default": "allow",
                    "enum": ["allow", "deny", "defer"],
                },
            },
            starter_config={
                "type": "tag_based",
                "policy_id": "tag-based-policy",
                "version": "1.0.0",
                "allowed_tags": ["public", "internal"],
                "denied_tags": ["deprecated", "unsafe"],
                "default_decision": "allow",
            },
        ),
        PolicyTypeDescriptor(
            type_key="action_based",
            factory=_build_action_based,
            display_name="Action-Based Policy",
            description="Controls access based on action types (allowed vs denied)",
            category="access_control",
            field_specs={
                "allowed_actions": {
                    "label": "Allowed actions",
                    "type": "string_list",
                    "description": "Actions that are permitted (if set, others are denied).",
                    "required": False,
                    "example": ["call_tool", "read_resource"],
                },
                "denied_actions": {
                    "label": "Denied actions",
                    "type": "string_list",
                    "description": "Actions that are denied (others are allowed).",
                    "required": False,
                    "example": ["delete_resource", "admin_override"],
                },
            },
            starter_config={
                "type": "action_based",
                "policy_id": "action-based-policy",
                "version": "1.0.0",
                "allowed_actions": ["call_tool", "read_resource"],
            },
        ),
        PolicyTypeDescriptor(
            type_key="gdpr",
            factory=_build_gdpr,
            display_name="GDPR Data Protection",
            description=(
                "Enforces GDPR principles: requires legal basis for personal "
                "data access. Tags: pii, personal_data, sensitive_data, gdpr_regulated."
            ),
            jurisdiction="EU",
            category="compliance",
            version="1.0.0",
            field_specs={
                "personal_data_tags": {
                    "label": "Personal data tags",
                    "type": "string_list",
                    "description": "Component tags that indicate personal data handling.",
                    "required": False,
                    "default": [
                        "pii",
                        "personal_data",
                        "sensitive_data",
                        "gdpr_regulated",
                    ],
                },
                "valid_legal_bases": {
                    "label": "Valid legal bases",
                    "type": "string_list",
                    "description": "Accepted legal bases per GDPR Art. 6.",
                    "required": False,
                    "default": [
                        "consent",
                        "contract",
                        "legal_obligation",
                        "vital_interests",
                        "public_interest",
                        "legitimate_interests",
                    ],
                },
            },
            starter_config={
                "type": "gdpr",
                "policy_id": "gdpr-v1",
                "version": "1.0.0",
                "personal_data_tags": [
                    "pii",
                    "personal_data",
                    "sensitive_data",
                    "gdpr_regulated",
                ],
                "valid_legal_bases": [
                    "consent",
                    "contract",
                    "legal_obligation",
                    "vital_interests",
                    "public_interest",
                    "legitimate_interests",
                ],
            },
        ),
        PolicyTypeDescriptor(
            type_key="hipaa",
            factory=_build_hipaa,
            display_name="HIPAA PHI Protection",
            description=(
                "Enforces HIPAA principles: requires authorized role and stated "
                "purpose for PHI access (minimum necessary principle)."
            ),
            jurisdiction="US",
            category="compliance",
            version="1.0.0",
            field_specs={
                "phi_tags": {
                    "label": "PHI tags",
                    "type": "string_list",
                    "description": "Component tags that indicate protected health information.",
                    "required": False,
                    "default": [
                        "phi",
                        "health_data",
                        "medical_record",
                        "hipaa_regulated",
                    ],
                },
                "authorized_roles": {
                    "label": "Authorized roles",
                    "type": "string_list",
                    "description": "Roles permitted to access PHI.",
                    "required": False,
                    "default": [
                        "healthcare_provider",
                        "health_plan",
                        "healthcare_clearinghouse",
                        "business_associate",
                    ],
                },
            },
            starter_config={
                "type": "hipaa",
                "policy_id": "hipaa-v1",
                "version": "1.0.0",
                "phi_tags": [
                    "phi",
                    "health_data",
                    "medical_record",
                    "hipaa_regulated",
                ],
                "authorized_roles": [
                    "healthcare_provider",
                    "health_plan",
                    "healthcare_clearinghouse",
                    "business_associate",
                ],
            },
        ),
    ]
    for desc in compliance_types:
        if _registry.get(desc.type_key) is None:
            _registry.register(desc)


# Run registration at module import time.
_register_compliance_types()
