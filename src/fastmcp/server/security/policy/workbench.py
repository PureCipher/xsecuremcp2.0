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
                    "from_type": str(source.get("type") or source.get("composition") or ""),
                    "to_type": str(target.get("type") or target.get("composition") or ""),
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
            recommendations.append("Add an RBAC rule before promoting this chain to production.")
        if "rate_limit" not in types:
            recommendations.append("Introduce a rate-limit rule before production rollout.")
        if "allow_all" in types:
            recommendations.append("Replace allow-all access with explicit allowlists or resource-scoped rules.")
    elif environment_id == "staging":
        if "denylist" not in types:
            recommendations.append("Add a denylist for sensitive resources before staging validation.")
        if "time_based" not in types and "temporal" not in types:
            recommendations.append("Consider time-based controls if reviewers only manage changes in staffed hours.")
    elif environment_id == "development":
        if "allow_all" in types:
            recommendations.append("Keep allow-all rules short-lived and pair them with a migration plan to staging.")

    if not recommendations:
        recommendations.append("This chain already lines up well with the selected environment profile.")
    return recommendations
