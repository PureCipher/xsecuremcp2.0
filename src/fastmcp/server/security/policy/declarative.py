"""Declarative policy definitions from YAML/JSON.

Load and build composite policies from structured config files or dicts,
without writing Python code.

Supported formats: YAML (``.yaml``/``.yml``), JSON (``.json``), or raw
Python dicts.

Example YAML::

    policy_id: production-policy
    version: "2.0"
    composition: all_of
    policies:
      - type: allowlist
        allowed: ["weather-*", "translate"]
      - type: denylist
        denied: ["admin-*", "debug-*"]
      - type: rbac
        role_mappings:
          admin: ["*"]
          viewer: ["call_tool", "read_resource"]
      - type: rate_limit
        max_requests: 100
        window_seconds: 3600
      - type: time_based
        allowed_days: [0, 1, 2, 3, 4]
        start_hour: 9
        end_hour: 17

Example usage::

    from fastmcp.server.security.policy.declarative import load_policy

    # From a YAML file
    policy = load_policy("policies/production.yaml")

    # From a dict
    policy = load_policy({
        "composition": "all_of",
        "policies": [
            {"type": "allowlist", "allowed": ["safe-*"]},
        ],
    })

    # Use with PolicyEngine
    engine = PolicyEngine(providers=[policy])
"""

from __future__ import annotations

import json
import logging
from datetime import time
from pathlib import Path
from typing import Any

from fastmcp.server.security.policy.composition import AllOf, AnyOf, FirstMatch, Not
from fastmcp.server.security.policy.plugin_registry import (
    PolicyTypeDescriptor,
    get_registry,
)

# Import built_in to trigger registration of compliance types (gdpr, hipaa, etc.)
import fastmcp.server.security.policy.built_in as _built_in  # noqa: F401
from fastmcp.server.security.policy.policies.abac import AttributeBasedPolicy
from fastmcp.server.security.policy.policies.allowlist import (
    AllowlistPolicy,
    DenylistPolicy,
)
from fastmcp.server.security.policy.policies.rate_limit import RateLimitPolicy
from fastmcp.server.security.policy.policies.rbac import RoleBasedPolicy
from fastmcp.server.security.policy.policies.resource_scoped import (
    ResourceScopedPolicy,
)
from fastmcp.server.security.policy.policies.temporal import TimeBasedPolicy
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
    DenyAllPolicy,
    PolicyDecision,
    PolicyProvider,
)

logger = logging.getLogger(__name__)

_registry = get_registry()


# ── Factory functions ─────────────────────────────────────────────


def _build_allowlist(config: dict[str, Any]) -> AllowlistPolicy:
    return AllowlistPolicy(
        allowed=set(config.get("allowed", [])),
        policy_id=config.get("policy_id", "allowlist-policy"),
        version=config.get("version", "1.0.0"),
    )


def _build_denylist(config: dict[str, Any]) -> DenylistPolicy:
    return DenylistPolicy(
        denied=set(config.get("denied", [])),
        policy_id=config.get("policy_id", "denylist-policy"),
        version=config.get("version", "1.0.0"),
    )


def _build_rbac(config: dict[str, Any]) -> RoleBasedPolicy:
    raw = config.get("role_mappings", {})
    mappings = {role: set(actions) for role, actions in raw.items()}
    return RoleBasedPolicy(
        role_mappings=mappings,
        policy_id=config.get("policy_id", "rbac-policy"),
        version=config.get("version", "1.0.0"),
        default_decision=_parse_decision(
            config.get("default_decision", "deny"),
        ),
    )


def _build_rate_limit(config: dict[str, Any]) -> RateLimitPolicy:
    return RateLimitPolicy(
        max_requests=config.get("max_requests", 100),
        window_seconds=config.get("window_seconds", 3600),
        policy_id=config.get("policy_id", "rate-limit-policy"),
        version=config.get("version", "1.0.0"),
    )


def _build_time_based(config: dict[str, Any]) -> TimeBasedPolicy:
    days = config.get("allowed_days")
    return TimeBasedPolicy(
        allowed_days=(frozenset(days) if days is not None else frozenset(range(7))),
        allowed_start_time=time(config.get("start_hour", 0), 0),
        allowed_end_time=time(config.get("end_hour", 23), 59, 59),
        utc_offset_hours=config.get("utc_offset_hours", 0),
        policy_id=config.get("policy_id", "time-based-policy"),
        version=config.get("version", "1.0.0"),
    )


def _build_abac(config: dict[str, Any]) -> AttributeBasedPolicy:
    """Build ABAC from declarative metadata checks.

    Supports a ``metadata_conditions`` dict mapping metadata keys to
    expected values::

        type: abac
        require_all: true
        metadata_conditions:
          department: engineering
          clearance_level: 3

    Each condition becomes a rule checking
    ``context.metadata.get(key) == value``.
    """
    conditions = config.get("metadata_conditions", {})
    rules: dict[str, Any] = {}
    for key, expected in conditions.items():

        def _make_check(k: str, v: Any):
            def check(ctx: Any) -> bool:
                return ctx.metadata.get(k) == v

            return check

        rules[f"check_{key}"] = _make_check(key, expected)

    policy = AttributeBasedPolicy(
        rules=rules,
        require_all=config.get("require_all", True),
        policy_id=config.get("policy_id", "abac-policy"),
        version=config.get("version", "1.0.0"),
    )
    object.__setattr__(policy, "_metadata_conditions", dict(conditions))
    return policy


def _build_resource_scoped(config: dict[str, Any]) -> ResourceScopedPolicy:
    """Build resource-scoped from nested policy definitions.

    Example::

        type: resource_scoped
        prefix_match: true
        resource_rules:
          "tool:admin":
            type: rbac
            role_mappings:
              admin: ["*"]
          "tool:public":
            type: allow_all
        default:
          type: deny_all
    """
    resource_rules: dict[str, PolicyProvider] = {}
    for resource_id, sub_config in config.get("resource_rules", {}).items():
        resource_rules[resource_id] = _build_single_policy(sub_config)

    default_config = config.get("default")
    default_policy = _build_single_policy(default_config) if default_config else None

    return ResourceScopedPolicy(
        resource_rules=resource_rules,
        default_policy=default_policy,
        prefix_match=config.get("prefix_match", False),
        policy_id=config.get("policy_id", "resource-scoped-policy"),
        version=config.get("version", "1.0.0"),
    )


def _build_allow_all(config: dict[str, Any]) -> AllowAllPolicy:
    return AllowAllPolicy()


def _build_deny_all(config: dict[str, Any]) -> DenyAllPolicy:
    return DenyAllPolicy()


# ── Register built-in types in the plugin registry ────────────────


def _register_builtins() -> None:
    """Register all built-in policy types with the global registry."""
    builtins = [
        PolicyTypeDescriptor(
            type_key="allowlist",
            factory=_build_allowlist,
            display_name="Allowlist",
            description="Allow only listed resources (glob patterns supported)",
            category="access_control",
            field_specs={
                "allowed": {
                    "label": "Allowed resources",
                    "type": "string_list",
                    "description": "Resource IDs or glob patterns that should remain callable.",
                    "required": True,
                    "example": ["tool:*", "registry:submit"],
                },
            },
            starter_config={
                "type": "allowlist",
                "policy_id": "allowlist-policy",
                "version": "1.0.0",
                "allowed": ["tool:*"],
            },
        ),
        PolicyTypeDescriptor(
            type_key="denylist",
            factory=_build_denylist,
            display_name="Denylist",
            description="Block listed resources (glob patterns supported)",
            category="access_control",
            field_specs={
                "denied": {
                    "label": "Blocked resources",
                    "type": "string_list",
                    "description": "Resource IDs or glob patterns that should always be denied.",
                    "required": True,
                    "example": ["admin-panel", "tool:dangerous-*"],
                },
            },
            starter_config={
                "type": "denylist",
                "policy_id": "denylist-policy",
                "version": "1.0.0",
                "denied": ["admin-panel"],
            },
        ),
        PolicyTypeDescriptor(
            type_key="rbac",
            factory=_build_rbac,
            display_name="Role-Based Access Control",
            description="Role-based access control",
            category="access_control",
            aliases=("role_based",),
            field_specs={
                "role_mappings": {
                    "label": "Role mappings",
                    "type": "string_map_string_list",
                    "description": "Map a role to the actions it may perform.",
                    "required": True,
                    "example": {
                        "reviewer": ["review_listing", "manage_policy"],
                        "admin": ["*"],
                    },
                },
                "default_decision": {
                    "label": "Default decision",
                    "type": "enum",
                    "description": "What to do when no role mapping matches.",
                    "required": False,
                    "default": "deny",
                    "enum": ["allow", "deny", "defer"],
                },
            },
            starter_config={
                "type": "rbac",
                "policy_id": "rbac-policy",
                "version": "1.0.0",
                "role_mappings": {
                    "publisher": ["submit_listing"],
                    "reviewer": ["review_listing", "manage_policy"],
                    "admin": ["*"],
                },
                "default_decision": "deny",
            },
        ),
        PolicyTypeDescriptor(
            type_key="rate_limit",
            factory=_build_rate_limit,
            display_name="Rate Limit",
            description="Sliding-window rate limiting per actor",
            category="rate_limiting",
            field_specs={
                "max_requests": {
                    "label": "Max requests",
                    "type": "int",
                    "description": "Maximum requests allowed per actor in each window.",
                    "required": False,
                    "default": 100,
                    "minimum": 1,
                },
                "window_seconds": {
                    "label": "Window (seconds)",
                    "type": "int",
                    "description": "Length of the rate-limit window in seconds.",
                    "required": False,
                    "default": 3600,
                    "minimum": 1,
                },
            },
            starter_config={
                "type": "rate_limit",
                "policy_id": "rate-limit-policy",
                "version": "1.0.0",
                "max_requests": 200,
                "window_seconds": 3600,
            },
        ),
        PolicyTypeDescriptor(
            type_key="time_based",
            factory=_build_time_based,
            display_name="Time-Based Access",
            description="Time-of-day and day-of-week restrictions",
            category="access_control",
            aliases=("temporal",),
            field_specs={
                "allowed_days": {
                    "label": "Allowed days",
                    "type": "int_list",
                    "description": "Days of the week where the policy can allow access. Use 0=Mon .. 6=Sun.",
                    "required": False,
                    "default": [0, 1, 2, 3, 4],
                },
                "start_hour": {
                    "label": "Start hour",
                    "type": "int",
                    "description": "Hour of day when access opens.",
                    "required": False,
                    "default": 9,
                    "minimum": 0,
                    "maximum": 23,
                },
                "end_hour": {
                    "label": "End hour",
                    "type": "int",
                    "description": "Hour of day when access closes.",
                    "required": False,
                    "default": 17,
                    "minimum": 0,
                    "maximum": 23,
                },
                "utc_offset_hours": {
                    "label": "UTC offset",
                    "type": "int",
                    "description": "Hour offset from UTC for interpreting the time window.",
                    "required": False,
                    "default": 0,
                    "minimum": -12,
                    "maximum": 14,
                },
            },
            starter_config={
                "type": "time_based",
                "policy_id": "business-hours-policy",
                "version": "1.0.0",
                "allowed_days": [0, 1, 2, 3, 4],
                "start_hour": 9,
                "end_hour": 17,
                "utc_offset_hours": 0,
            },
        ),
        PolicyTypeDescriptor(
            type_key="abac",
            factory=_build_abac,
            display_name="Attribute-Based Access Control",
            description="Attribute-based policy using metadata checks",
            category="access_control",
            aliases=("attribute_based",),
            field_specs={
                "metadata_conditions": {
                    "label": "Metadata conditions",
                    "type": "json_map",
                    "description": "Exact key/value checks applied to context.metadata.",
                    "required": True,
                    "example": {"tenant": "acme", "clearance": "reviewer"},
                },
                "require_all": {
                    "label": "Require all conditions",
                    "type": "bool",
                    "description": "When enabled, every metadata condition must match.",
                    "required": False,
                    "default": True,
                },
            },
            starter_config={
                "type": "abac",
                "policy_id": "abac-policy",
                "version": "1.0.0",
                "metadata_conditions": {"tenant": "acme"},
                "require_all": True,
            },
        ),
        PolicyTypeDescriptor(
            type_key="resource_scoped",
            factory=_build_resource_scoped,
            display_name="Resource-Scoped",
            description="Delegate to sub-policies per resource ID",
            category="access_control",
            field_specs={
                "resource_rules": {
                    "label": "Resource rules",
                    "type": "policy_config_map",
                    "description": "Map a resource to a nested policy config. Use the JSON preview for nested rules.",
                    "required": True,
                },
                "default": {
                    "label": "Default policy",
                    "type": "policy_config",
                    "description": "Fallback nested policy when a resource has no direct match.",
                    "required": False,
                },
                "prefix_match": {
                    "label": "Prefix match resources",
                    "type": "bool",
                    "description": "Match resource IDs by prefix instead of exact equality.",
                    "required": False,
                    "default": False,
                },
            },
            starter_config={
                "type": "resource_scoped",
                "policy_id": "resource-scoped-policy",
                "version": "1.0.0",
                "resource_rules": {
                    "registry:policy": {"type": "deny_all"},
                },
                "default": {"type": "allow_all"},
                "prefix_match": False,
            },
        ),
        PolicyTypeDescriptor(
            type_key="allow_all",
            factory=_build_allow_all,
            display_name="Allow All",
            description="Always allow",
            category="access_control",
            field_specs={},
            starter_config={"type": "allow_all"},
        ),
        PolicyTypeDescriptor(
            type_key="deny_all",
            factory=_build_deny_all,
            display_name="Deny All",
            description="Always deny",
            category="access_control",
            field_specs={},
            starter_config={"type": "deny_all"},
        ),
    ]
    for desc in builtins:
        if _registry.get(desc.type_key) is None:
            _registry.register(desc)


# Run registration at module import time.
_register_builtins()


# ── Backward-compatible lookup ────────────────────────────────────
# Kept for any code that references _POLICY_FACTORIES directly.
_POLICY_FACTORIES: dict[str, Any] = {
    key: (_registry.get(key).factory if _registry.get(key) else None)
    for key in _registry.type_keys
    if _registry.get(key) is not None
}


# ── Composition builders ──────────────────────────────────────────


_COMPOSITION_MAP = {
    "all_of": "all_of",
    "allof": "all_of",
    "all": "all_of",
    "any_of": "any_of",
    "anyof": "any_of",
    "any": "any_of",
    "first_match": "first_match",
    "firstmatch": "first_match",
    "not": "not",
}


# ── Helpers ───────────────────────────────────────────────────────


def _parse_decision(value: str) -> PolicyDecision:
    """Parse a string into a PolicyDecision enum."""
    return PolicyDecision(value.lower())


def _build_single_policy(config: dict[str, Any]) -> PolicyProvider:
    """Build a single PolicyProvider from a config dict.

    Handles both simple policies and nested compositions via
    ``composition`` key. Delegates to the plugin registry for
    type lookup.
    """
    # If it has a "composition" or "policies" key, it's a composite
    if "composition" in config or "policies" in config:
        return _build_composite(config)

    return _registry.build(config)


def _build_composite(config: dict[str, Any]) -> PolicyProvider:
    """Build a composite policy from a config with ``policies`` list."""
    raw_composition = config.get("composition", "all_of")
    composition = _COMPOSITION_MAP.get(raw_composition.lower())
    if composition is None:
        raise ValueError(
            f"Unknown composition: {raw_composition!r}. "
            f"Available: {sorted(_COMPOSITION_MAP.keys())}"
        )

    policy_id = config.get("policy_id", f"declarative-{composition}")
    version = config.get("version", "1.0.0")
    children_config = config.get("policies", [])

    children: list[PolicyProvider] = [
        _build_single_policy(child) for child in children_config
    ]

    if composition == "not":
        if len(children) != 1:
            raise ValueError("'not' composition requires exactly one child policy")
        return Not(children[0], policy_id=policy_id, version=version)

    if composition == "all_of":
        return AllOf(*children, policy_id=policy_id, version=version)

    if composition == "any_of":
        return AnyOf(
            *children,
            policy_id=policy_id,
            version=version,
            require_minimum=config.get("require_minimum", 1),
        )

    # first_match
    default = _parse_decision(config.get("default_decision", "deny"))
    return FirstMatch(
        *children,
        policy_id=policy_id,
        version=version,
        default_decision=default,
    )


# ── Public API ────────────────────────────────────────────────────


def load_policy(source: str | Path | dict[str, Any]) -> PolicyProvider:
    """Load a policy from a YAML/JSON file or a dict.

    Args:
        source: Path to a YAML/JSON file, or a dict with the policy
            definition.

    Returns:
        A fully-built PolicyProvider ready for use with PolicyEngine.

    Raises:
        ValueError: If the config is malformed or references unknown types.
        FileNotFoundError: If the file path doesn't exist.
        ImportError: If YAML loading is requested but PyYAML is not installed.

    Example::

        policy = load_policy("policies/production.yaml")
        engine = PolicyEngine(providers=[policy])
    """
    if isinstance(source, dict):
        return _build_single_policy(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    text = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as err:
            raise ImportError(
                "PyYAML is required for loading YAML policy files. "
                "Install it with: pip install pyyaml"
            ) from err
        config = yaml.safe_load(text)
    elif path.suffix == ".json":
        config = json.loads(text)
    else:
        raise ValueError(
            f"Unsupported file format: {path.suffix!r}. Use .yaml, .yml, or .json"
        )

    if not isinstance(config, dict):
        raise ValueError(
            f"Policy file must contain a mapping, got {type(config).__name__}"
        )

    return _build_single_policy(config)


def dump_policy_schema(
    *,
    jurisdiction: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable schema describing the declarative format.

    Useful for documentation, IDE completion hints, or validation.
    Dynamically includes all registered policy types from the plugin
    registry.

    Args:
        jurisdiction: Optional filter to types matching this jurisdiction.
        category: Optional filter to types in this category.
    """
    # Get dynamically registered types from the plugin registry.
    registry_schema = _registry.dump_schema(
        jurisdiction=jurisdiction, category=category
    )

    return {
        "description": "Declarative policy definition schema for SecureMCP",
        "common_field_specs": {
            "policy_id": {
                "label": "Policy ID",
                "type": "string",
                "description": "Stable identifier for audit trails and version history.",
                "required": False,
                "placeholder": "my-policy",
            },
            "version": {
                "label": "Version",
                "type": "string",
                "description": "Provider-level version string captured in snapshots.",
                "required": False,
                "default": "1.0.0",
                "placeholder": "1.0.0",
            },
        },
        "policy_types": registry_schema["policy_types"],
        "compositions": {
            "all_of": {
                "description": "All child policies must ALLOW",
                "aliases": ["allof", "all"],
                "field_specs": {
                    "policies": {
                        "label": "Child policies",
                        "type": "policy_config_list",
                        "description": "Ordered child policy configs. Use the JSON preview to edit nested children.",
                        "required": True,
                    }
                },
                "starter_config": {
                    "composition": "all_of",
                    "policy_id": "all-of-policy",
                    "version": "1.0.0",
                    "policies": [
                        {"type": "allow_all"},
                        {"type": "denylist", "denied": ["admin-panel"]},
                    ],
                },
            },
            "any_of": {
                "description": "At least N child policies must ALLOW",
                "aliases": ["anyof", "any"],
                "extra_fields": {"require_minimum": "int (default: 1)"},
                "field_specs": {
                    "policies": {
                        "label": "Child policies",
                        "type": "policy_config_list",
                        "description": "Ordered child policy configs. Use the JSON preview to edit nested children.",
                        "required": True,
                    },
                    "require_minimum": {
                        "label": "Minimum allows",
                        "type": "int",
                        "description": "Minimum child policies that must allow.",
                        "required": False,
                        "default": 1,
                        "minimum": 1,
                    },
                },
                "starter_config": {
                    "composition": "any_of",
                    "policy_id": "any-of-policy",
                    "version": "1.0.0",
                    "require_minimum": 1,
                    "policies": [
                        {"type": "allow_all"},
                        {"type": "denylist", "denied": ["admin-panel"]},
                    ],
                },
            },
            "first_match": {
                "description": "First non-DEFER result wins",
                "aliases": ["firstmatch"],
                "extra_fields": {"default_decision": "str (default: 'deny')"},
                "field_specs": {
                    "policies": {
                        "label": "Child policies",
                        "type": "policy_config_list",
                        "description": "Ordered child policy configs. Use the JSON preview to edit nested children.",
                        "required": True,
                    },
                    "default_decision": {
                        "label": "Default decision",
                        "type": "enum",
                        "description": "Fallback decision if all children defer.",
                        "required": False,
                        "default": "deny",
                        "enum": ["allow", "deny", "defer"],
                    },
                },
                "starter_config": {
                    "composition": "first_match",
                    "policy_id": "first-match-policy",
                    "version": "1.0.0",
                    "default_decision": "deny",
                    "policies": [
                        {"type": "denylist", "denied": ["admin-panel"]},
                        {"type": "allow_all"},
                    ],
                },
            },
            "not": {
                "description": "Invert child decision (exactly 1 child)",
                "aliases": [],
                "field_specs": {
                    "policies": {
                        "label": "Child policy",
                        "type": "policy_config_list",
                        "description": "Exactly one child policy. Use the JSON preview to edit nested children.",
                        "required": True,
                    }
                },
                "starter_config": {
                    "composition": "not",
                    "policy_id": "not-policy",
                    "version": "1.0.0",
                    "policies": [{"type": "deny_all"}],
                },
            },
        },
        "common_fields": {
            "type": "str — policy type name (required for leaf policies)",
            "policy_id": "str — custom identifier",
            "version": "str — version string",
            "composition": "str — composition type (for composite policies)",
            "policies": "list[policy_config] — child policies (for composite)",
        },
    }
