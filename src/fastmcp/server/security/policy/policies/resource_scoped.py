"""Resource-scoped access control policy.

Delegates policy evaluation to per-resource sub-policies, allowing fine-grained
control over individual tools, resources, or endpoints.

Example::

    policy = ResourceScopedPolicy(
        resource_rules={
            "tool:database_query": strict_policy,
            "tool:calculator": lenient_policy,
            "resource:config": admin_only_policy,
        },
        default_policy=DenyAllPolicy(),
    )
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import cast

from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyProvider,
    PolicyResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ResourceScopedPolicy:
    """Per-resource policy delegation.

    Attributes:
        resource_rules: Dict mapping resource identifiers to PolicyProviders.
            Keys are matched against ``context.resource_id``.
        default_policy: Fallback policy when no rule matches. If None, DEFER.
        prefix_match: If True, match resource_id prefixes (e.g., "tool:" matches
            "tool:calculator"). If False, exact match only.
        policy_id: Unique identifier for this policy instance.
        version: Version string.
    """

    resource_rules: dict[str, PolicyProvider] = field(default_factory=dict)
    default_policy: PolicyProvider | None = None
    prefix_match: bool = False
    policy_id: str = "resource-scoped-policy"
    version: str = "1.0.0"

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        """Delegate to the matching resource policy."""
        resource_id = context.resource_id

        # Try exact match first
        if resource_id in self.resource_rules:
            policy = self.resource_rules[resource_id]
            result = policy.evaluate(context)
            if isinstance(result, Awaitable):
                result = await result
            return cast(PolicyResult, result)

        # Try prefix match
        if self.prefix_match:
            for prefix, policy in self.resource_rules.items():
                if resource_id.startswith(prefix):
                    result = policy.evaluate(context)
                    if isinstance(result, Awaitable):
                        result = await result
                    return cast(PolicyResult, result)

        # Fallback to default
        if self.default_policy is not None:
            result = self.default_policy.evaluate(context)
            if isinstance(result, Awaitable):
                result = await result
            return cast(PolicyResult, result)

        return PolicyResult(
            decision=PolicyDecision.DEFER,
            reason=f"No resource rule for '{resource_id}'",
            policy_id=self.policy_id,
        )

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version
