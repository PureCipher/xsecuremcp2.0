"""Tests for the dynamic policy-type plugin registry.

Covers: PolicyTypeDescriptor, PolicyTypeRegistry, entry-point discovery,
schema generation, plugin listing, jurisdiction/category filtering, and
the global singleton convenience functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fastmcp.server.security.policy.plugin_registry import (
    PolicyTypeDescriptor,
    PolicyTypeRegistry,
    get_registry,
)
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
    PolicyProvider,
)

# ── Helpers ──────────────────────────────────────────────────────


def _make_descriptor(
    type_key: str = "test_policy",
    display_name: str = "Test Policy",
    description: str = "A test policy",
    jurisdiction: str | None = None,
    category: str = "general",
    aliases: tuple[str, ...] = (),
    version: str = "1.0.0",
) -> PolicyTypeDescriptor:
    """Create a descriptor that builds an AllowAllPolicy."""
    return PolicyTypeDescriptor(
        type_key=type_key,
        factory=lambda cfg: AllowAllPolicy(),
        display_name=display_name,
        description=description,
        jurisdiction=jurisdiction,
        category=category,
        field_specs={"some_field": {"type": "string"}},
        starter_config={"type": type_key},
        version=version,
        aliases=aliases,
    )


# ── PolicyTypeRegistry Tests ─────────────────────────────────────


class TestRegistryRegistration:
    """Tests for register / unregister lifecycle."""

    def test_register_and_get(self) -> None:
        reg = PolicyTypeRegistry()
        desc = _make_descriptor()
        reg.register(desc)
        assert reg.get("test_policy") is desc

    def test_register_duplicate_raises(self) -> None:
        reg = PolicyTypeRegistry()
        reg.register(_make_descriptor())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_descriptor())

    def test_unregister(self) -> None:
        reg = PolicyTypeRegistry()
        reg.register(_make_descriptor())
        reg.unregister("test_policy")
        assert reg.get("test_policy") is None

    def test_unregister_missing_raises(self) -> None:
        reg = PolicyTypeRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.unregister("nonexistent")

    def test_alias_resolution(self) -> None:
        reg = PolicyTypeRegistry()
        desc = _make_descriptor(aliases=("tp", "test_p"))
        reg.register(desc)
        assert reg.get("tp") is desc
        assert reg.get("test_p") is desc

    def test_unregister_cleans_aliases(self) -> None:
        reg = PolicyTypeRegistry()
        desc = _make_descriptor(aliases=("tp",))
        reg.register(desc)
        reg.unregister("test_policy")
        assert reg.get("tp") is None


class TestRegistryLookup:
    """Tests for list_types and type_keys."""

    def test_list_types_empty(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True  # skip discovery
        assert reg.list_types() == []

    def test_list_types_returns_sorted(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="zzz"))
        reg.register(_make_descriptor(type_key="aaa"))
        types = reg.list_types()
        assert [t.type_key for t in types] == ["aaa", "zzz"]

    def test_filter_by_jurisdiction(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="eu_policy", jurisdiction="EU"))
        reg.register(_make_descriptor(type_key="us_policy", jurisdiction="US"))
        reg.register(_make_descriptor(type_key="universal"))

        eu_types = reg.list_types(jurisdiction="EU")
        keys = [t.type_key for t in eu_types]
        assert "eu_policy" in keys
        assert "universal" in keys  # None jurisdiction = universal
        assert "us_policy" not in keys

    def test_filter_by_category(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="a", category="compliance"))
        reg.register(_make_descriptor(type_key="b", category="access_control"))

        compliance = reg.list_types(category="compliance")
        assert [t.type_key for t in compliance] == ["a"]

    def test_type_keys_includes_aliases(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="main", aliases=("alt",)))
        assert "alt" in reg.type_keys
        assert "main" in reg.type_keys


class TestRegistryBuild:
    """Tests for building policy providers from config."""

    def test_build_success(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="test"))
        provider = reg.build({"type": "test"})
        assert isinstance(provider, PolicyProvider)

    def test_build_unknown_type_raises(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        with pytest.raises(ValueError, match="Unknown policy type"):
            reg.build({"type": "nonexistent"})

    def test_build_via_alias(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="main", aliases=("shortcut",)))
        provider = reg.build({"type": "shortcut"})
        assert isinstance(provider, PolicyProvider)


class TestRegistrySchema:
    """Tests for dump_schema and dump_plugin_list."""

    def test_dump_schema_shape(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(
            _make_descriptor(type_key="test", jurisdiction="EU", category="compliance")
        )
        schema = reg.dump_schema()
        assert "policy_types" in schema
        assert "test" in schema["policy_types"]
        entry = schema["policy_types"]["test"]
        assert entry["jurisdiction"] == "EU"
        assert entry["category"] == "compliance"
        assert "field_specs" in entry
        assert "starter_config" in entry

    def test_dump_schema_filtered(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="eu", jurisdiction="EU"))
        reg.register(_make_descriptor(type_key="us", jurisdiction="US"))

        schema = reg.dump_schema(jurisdiction="US")
        assert "us" in schema["policy_types"]
        assert "eu" not in schema["policy_types"]

    def test_dump_plugin_list(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="test"))
        plugins = reg.dump_plugin_list()
        assert len(plugins) == 1
        p = plugins[0]
        assert p["type_key"] == "test"
        assert p["display_name"] == "Test Policy"
        assert "starter_config" in p

    def test_dump_plugin_list_filtered(self) -> None:
        reg = PolicyTypeRegistry()
        reg._plugins_discovered = True
        reg.register(_make_descriptor(type_key="eu", jurisdiction="EU"))
        reg.register(_make_descriptor(type_key="us", jurisdiction="US"))

        us_plugins = reg.dump_plugin_list(jurisdiction="US")
        assert all(p["type_key"] != "eu" for p in us_plugins)


class TestEntryPointDiscovery:
    """Tests for discover_plugins via importlib entry points."""

    def test_discover_loads_valid_descriptor(self) -> None:
        reg = PolicyTypeRegistry()
        desc = _make_descriptor(type_key="discovered")
        mock_ep = MagicMock()
        mock_ep.name = "discovered"
        mock_ep.load.return_value = desc

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            count = reg.discover_plugins()
        assert count == 1
        assert reg.get("discovered") is desc

    def test_discover_skips_non_descriptor(self) -> None:
        reg = PolicyTypeRegistry()
        mock_ep = MagicMock()
        mock_ep.name = "bad_plugin"
        mock_ep.load.return_value = "not a descriptor"

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            count = reg.discover_plugins()
        assert count == 0

    def test_discover_skips_failing_entrypoint(self) -> None:
        reg = PolicyTypeRegistry()
        mock_ep = MagicMock()
        mock_ep.name = "broken"
        mock_ep.load.side_effect = ImportError("missing dep")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            count = reg.discover_plugins()
        assert count == 0

    def test_lazy_discovery_on_first_get(self) -> None:
        reg = PolicyTypeRegistry()
        assert not reg._plugins_discovered
        with patch("importlib.metadata.entry_points", return_value=[]):
            reg.get("anything")
        assert reg._plugins_discovered


# ── Global singleton convenience functions ────────────────────────


class TestGlobalSingleton:
    """Tests for module-level get_registry / register / unregister."""

    def test_get_registry_returns_same_instance(self) -> None:
        assert get_registry() is get_registry()

    def test_builtin_types_are_registered(self) -> None:
        """After importing declarative, built-in types should be present."""
        # Force declarative + built_in imports to trigger registration
        import fastmcp.server.security.policy.built_in  # noqa: F401
        import fastmcp.server.security.policy.declarative  # noqa: F401

        registry = get_registry()
        # Spot-check a few built-in types
        assert registry.get("allowlist") is not None
        assert registry.get("rbac") is not None
        assert registry.get("rate_limit") is not None

    def test_compliance_types_registered(self) -> None:
        """built_in.py should register compliance types with jurisdictions."""
        import fastmcp.server.security.policy.built_in  # noqa: F401

        registry = get_registry()
        gdpr = registry.get("gdpr")
        assert gdpr is not None
        assert gdpr.jurisdiction == "EU"
        assert gdpr.category == "compliance"

        hipaa = registry.get("hipaa")
        assert hipaa is not None
        assert hipaa.jurisdiction == "US"
        assert hipaa.category == "compliance"
