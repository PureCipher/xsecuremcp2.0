"""Dynamic policy-type registry for SecureMCP.

Provides a central registry where policy types can be registered,
discovered, and instantiated at runtime. Replaces the hardcoded
``_POLICY_FACTORIES`` dict in ``declarative.py`` with a mutable
registry that supports third-party plugins.

Example::

    from fastmcp.server.security.policy.plugin_registry import (
        PolicyTypeDescriptor,
        register_policy_type,
        get_registry,
    )

    descriptor = PolicyTypeDescriptor(
        type_key="my_custom_policy",
        factory=my_factory_fn,
        display_name="My Custom Policy",
        description="Does custom things",
        category="access_control",
    )
    register_policy_type(descriptor)

    # Third-party packages can auto-register via entry points:
    #   [project.entry-points."securemcp.policy_types"]
    #   my_policy = "my_package.policies:my_descriptor"
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastmcp.server.security.policy.provider import PolicyProvider

logger = logging.getLogger(__name__)

# Entry-point group name for third-party policy type discovery.
POLICY_TYPES_ENTRY_POINT_GROUP = "securemcp.policy_types"


@dataclass(frozen=True)
class PolicyTypeDescriptor:
    """Describes a registrable policy type.

    Attributes:
        type_key: Unique key used in config ``{"type": "<key>"}``.
        factory: Callable that builds a ``PolicyProvider`` from a config dict.
        display_name: Human-readable name shown in the UI.
        description: Short description of what the policy enforces.
        jurisdiction: ISO region code (``"EU"``, ``"US"``) or ``None`` for universal.
        category: Grouping label (``"compliance"``, ``"access_control"``, etc.).
        field_specs: JSON-schema-like dict describing configurable fields.
        starter_config: Default config dict used as a UI template.
        version: Version string for the plugin itself.
        aliases: Alternative type keys that resolve to this descriptor.
    """

    type_key: str
    factory: Callable[[dict[str, Any]], PolicyProvider]
    display_name: str
    description: str
    jurisdiction: str | None = None
    category: str = "general"
    field_specs: dict[str, Any] = field(default_factory=dict)
    starter_config: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    aliases: tuple[str, ...] = ()


class PolicyTypeRegistry:
    """Mutable registry of policy types.

    Supports registration, lookup, filtering, and schema generation.
    The global singleton is available via :func:`get_registry`.
    """

    def __init__(self) -> None:
        self._types: dict[str, PolicyTypeDescriptor] = {}
        self._alias_map: dict[str, str] = {}
        self._plugins_discovered: bool = False

    # ── Registration ───────────────────────────────────────────

    def register(self, descriptor: PolicyTypeDescriptor) -> None:
        """Register a policy type.

        Raises:
            ValueError: If the ``type_key`` is already registered.
        """
        if descriptor.type_key in self._types:
            raise ValueError(
                f"Policy type {descriptor.type_key!r} is already registered"
            )
        self._types[descriptor.type_key] = descriptor
        for alias in descriptor.aliases:
            self._alias_map[alias] = descriptor.type_key
        logger.debug("Registered policy type: %s", descriptor.type_key)

    def unregister(self, type_key: str) -> None:
        """Remove a previously registered policy type.

        Raises:
            KeyError: If the type is not registered.
        """
        descriptor = self._types.pop(type_key, None)
        if descriptor is None:
            raise KeyError(f"Policy type {type_key!r} is not registered")
        for alias in descriptor.aliases:
            self._alias_map.pop(alias, None)
        logger.debug("Unregistered policy type: %s", type_key)

    # ── Lookup ─────────────────────────────────────────────────

    def get(self, type_key: str) -> PolicyTypeDescriptor | None:
        """Get a descriptor by type key or alias."""
        self._ensure_discovered()
        resolved = self._alias_map.get(type_key, type_key)
        return self._types.get(resolved)

    def list_types(
        self,
        *,
        jurisdiction: str | None = None,
        category: str | None = None,
    ) -> list[PolicyTypeDescriptor]:
        """List registered types, optionally filtered.

        Args:
            jurisdiction: Filter to types matching this jurisdiction
                (``None`` matches universal types too).
            category: Filter to types in this category.
        """
        self._ensure_discovered()
        result = list(self._types.values())
        if jurisdiction is not None:
            result = [
                d
                for d in result
                if d.jurisdiction is None or d.jurisdiction == jurisdiction
            ]
        if category is not None:
            result = [d for d in result if d.category == category]
        return sorted(result, key=lambda d: d.type_key)

    @property
    def type_keys(self) -> list[str]:
        """All registered type keys (sorted)."""
        self._ensure_discovered()
        all_keys = set(self._types.keys()) | set(self._alias_map.keys())
        return sorted(all_keys)

    # ── Build ──────────────────────────────────────────────────

    def build(self, config: dict[str, Any]) -> PolicyProvider:
        """Build a PolicyProvider from a declarative config.

        Looks up the ``type`` key in the registry and calls the factory.

        Raises:
            ValueError: If the type is unknown.
        """
        self._ensure_discovered()
        policy_type = config.get("type", "")
        descriptor = self.get(policy_type)
        if descriptor is None:
            raise ValueError(
                f"Unknown policy type: {policy_type!r}. "
                f"Available types: {self.type_keys}"
            )
        return descriptor.factory(config)

    # ── Schema ─────────────────────────────────────────────────

    def dump_schema(
        self,
        *,
        jurisdiction: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON-serializable schema from registered types.

        The output mirrors the existing ``dump_policy_schema()`` shape
        so the frontend can consume it without changes.
        """
        self._ensure_discovered()
        descriptors = self.list_types(
            jurisdiction=jurisdiction, category=category
        )
        policy_types: dict[str, Any] = {}
        for desc in descriptors:
            entry: dict[str, Any] = {
                "description": desc.description,
                "field_specs": dict(desc.field_specs),
                "starter_config": dict(desc.starter_config),
            }
            if desc.aliases:
                entry["aliases"] = list(desc.aliases)
            if desc.jurisdiction:
                entry["jurisdiction"] = desc.jurisdiction
            if desc.category:
                entry["category"] = desc.category
            if desc.version:
                entry["plugin_version"] = desc.version
            policy_types[desc.type_key] = entry

        return {"policy_types": policy_types}

    def dump_plugin_list(
        self,
        *,
        jurisdiction: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a lightweight list of registered plugin descriptors."""
        self._ensure_discovered()
        descriptors = self.list_types(
            jurisdiction=jurisdiction, category=category
        )
        return [
            {
                "type_key": d.type_key,
                "display_name": d.display_name,
                "description": d.description,
                "jurisdiction": d.jurisdiction,
                "category": d.category,
                "version": d.version,
                "starter_config": dict(d.starter_config),
            }
            for d in descriptors
        ]

    # ── Entry-point discovery ──────────────────────────────────

    def discover_plugins(
        self, group: str = POLICY_TYPES_ENTRY_POINT_GROUP
    ) -> int:
        """Scan installed packages for policy-type entry points.

        Each entry point must resolve to a :class:`PolicyTypeDescriptor`.

        Returns:
            Number of plugins discovered and registered.
        """
        try:
            from importlib.metadata import entry_points
        except ImportError:
            logger.debug("importlib.metadata not available; skipping discovery")
            return 0

        count = 0
        for ep in entry_points(group=group):
            try:
                descriptor = ep.load()
                if not isinstance(descriptor, PolicyTypeDescriptor):
                    logger.warning(
                        "Entry point %s did not return a PolicyTypeDescriptor, "
                        "got %s; skipping",
                        ep.name,
                        type(descriptor).__name__,
                    )
                    continue
                if descriptor.type_key not in self._types:
                    self.register(descriptor)
                    count += 1
            except Exception:
                logger.warning(
                    "Failed to load policy plugin entry point: %s",
                    ep.name,
                    exc_info=True,
                )
        self._plugins_discovered = True
        logger.debug("Discovered %d policy plugin(s) from entry points", count)
        return count

    def _ensure_discovered(self) -> None:
        """Lazily run entry-point discovery on first access."""
        if not self._plugins_discovered:
            self.discover_plugins()


# ── Module-level singleton ─────────────────────────────────────────


_global_registry = PolicyTypeRegistry()


def get_registry() -> PolicyTypeRegistry:
    """Return the global :class:`PolicyTypeRegistry` singleton."""
    return _global_registry


def register_policy_type(descriptor: PolicyTypeDescriptor) -> None:
    """Register a policy type on the global registry.

    Convenience wrapper around ``get_registry().register(descriptor)``.
    """
    _global_registry.register(descriptor)


def unregister_policy_type(type_key: str) -> None:
    """Remove a policy type from the global registry.

    Convenience wrapper around ``get_registry().unregister(type_key)``.
    """
    _global_registry.unregister(type_key)
