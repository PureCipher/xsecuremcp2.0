"""Declarative compliance rule engine.

Expresses compliance logic (GDPR, HIPAA, SOC 2, etc.) as pure JSON
config — no Python classes required in bundles.

Each rule follows a tag-gated, metadata-checked pattern:

1. **Match**: Does the resource carry any of the specified ``tags``?
   If not, the rule does not apply and the decision is ``defer``.
2. **Check**: Are the required ``metadata`` fields present and valid?
   Each check specifies a metadata key and an optional set of
   ``allowed_values``.
3. **Decide**: If all checks pass → ``allow``. If any check fails →
   ``deny`` (with a human-readable reason from the rule).

This covers the full spectrum of compliance gating:

- GDPR: "if resource is tagged ``pii``, require ``legal_basis`` from
  ``{consent, contract, legitimate_interests, ...}``"
- HIPAA: "if resource is tagged ``phi``, require ``actor_role`` from
  ``{healthcare_provider, ...}`` AND require ``purpose``"

Example JSON config::

    {
        "type": "compliance_rule",
        "policy_id": "gdpr-core",
        "version": "1.0.0",
        "framework": "GDPR",
        "rules": [
            {
                "name": "legal_basis_required",
                "description": "Personal data access requires a valid legal basis",
                "tags": ["pii", "personal_data", "gdpr_regulated"],
                "checks": [
                    {
                        "metadata_key": "legal_basis",
                        "allowed_values": ["consent", "contract", "legal_obligation"]
                    }
                ],
                "deny_message": "Personal data access denied: missing or invalid legal basis"
            }
        ]
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetadataCheck:
    """A single metadata field requirement.

    Attributes:
        metadata_key: The key to look up in ``context.metadata``.
        allowed_values: If provided, the metadata value must be one of
            these. If empty/None, any truthy value satisfies the check.
        required: Whether the key must be present. Defaults to True.
    """

    metadata_key: str
    allowed_values: frozenset[str] | None = None
    required: bool = True


@dataclass(frozen=True)
class ComplianceRuleSpec:
    """One logical rule within a compliance policy.

    Attributes:
        name: Short identifier for audit trails.
        description: Human-readable explanation.
        tags: Resource tags that activate this rule. If the resource
            carries *any* of these tags, the rule applies.
        checks: Metadata requirements that must all pass.
        deny_message: Message returned when a check fails.
        allow_message: Message returned when all checks pass.
    """

    name: str
    description: str
    tags: frozenset[str]
    checks: tuple[MetadataCheck, ...]
    deny_message: str = "Access denied by compliance rule"
    allow_message: str = "Access permitted by compliance rule"


@dataclass
class ComplianceRulePolicy:
    """Declarative compliance rule engine.

    Evaluates a list of rules against the context. Each rule is
    tag-gated: it only fires when the resource carries a matching tag.
    When a rule fires, all its metadata checks must pass.

    If no rules fire (no tag matches), the policy defers to the next
    provider in the chain.

    Attributes:
        rules: Ordered list of compliance rule specs.
        framework: Human label for the compliance framework (e.g. "GDPR").
        require_all_rules: If True, every matching rule must pass (AND).
            If False, any matching rule passing is sufficient (OR).
        policy_id: Stable identifier for audit trails.
        version: Version string.
    """

    rules: list[ComplianceRuleSpec] = field(default_factory=list)
    framework: str = ""
    require_all_rules: bool = True
    policy_id: str = "compliance-rule-policy"
    version: str = "1.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        """Evaluate compliance rules against the context."""

        if not self.rules:
            return PolicyResult(
                decision=PolicyDecision.DEFER,
                reason=f"{self.framework or 'Compliance'}: No rules configured",
                policy_id=self.policy_id,
            )

        matched_rules: list[ComplianceRuleSpec] = []
        for rule in self.rules:
            if context.tags & rule.tags:
                matched_rules.append(rule)

        if not matched_rules:
            framework_label = self.framework or "Compliance"
            return PolicyResult(
                decision=PolicyDecision.DEFER,
                reason=f"{framework_label}: No matching tags; rules not applicable",
                policy_id=self.policy_id,
            )

        passed: list[str] = []
        failed: list[tuple[str, str]] = []

        for rule in matched_rules:
            rule_passed = True
            fail_reasons: list[str] = []

            for check in rule.checks:
                value = context.metadata.get(check.metadata_key)

                if check.required and not value:
                    rule_passed = False
                    fail_reasons.append(
                        f"missing required metadata '{check.metadata_key}'"
                    )
                    continue

                if (
                    value
                    and check.allowed_values is not None
                    and value not in check.allowed_values
                ):
                    rule_passed = False
                    fail_reasons.append(
                        f"'{check.metadata_key}' value '{value}' "
                        f"not in allowed set"
                    )

            if rule_passed:
                passed.append(rule.name)
            else:
                failed.append((rule.name, "; ".join(fail_reasons)))

        framework_label = self.framework or "Compliance"

        if self.require_all_rules:
            if not failed:
                constraints = [f"compliance:{name}" for name in passed]
                allow_msg = matched_rules[0].allow_message if len(matched_rules) == 1 else (
                    f"{framework_label}: All {len(passed)} rules passed"
                )
                return PolicyResult(
                    decision=PolicyDecision.ALLOW,
                    reason=allow_msg,
                    policy_id=self.policy_id,
                    constraints=constraints,
                )
            first_fail_name, first_fail_reason = failed[0]
            matching_rule = next(
                (r for r in matched_rules if r.name == first_fail_name), None
            )
            deny_msg = (
                matching_rule.deny_message
                if matching_rule
                else f"{framework_label}: {first_fail_reason}"
            )
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=deny_msg,
                policy_id=self.policy_id,
                constraints=[f"failed:{first_fail_name}"],
            )
        else:
            if passed:
                constraints = [f"compliance:{name}" for name in passed]
                return PolicyResult(
                    decision=PolicyDecision.ALLOW,
                    reason=f"{framework_label}: {len(passed)}/{len(matched_rules)} rules passed",
                    policy_id=self.policy_id,
                    constraints=constraints,
                )
            all_reasons = "; ".join(f"{n}: {r}" for n, r in failed)
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"{framework_label}: No rules passed ({all_reasons})",
                policy_id=self.policy_id,
            )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version
