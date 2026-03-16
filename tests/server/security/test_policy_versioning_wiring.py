"""Tests for PolicyVersionManager wiring into PolicyEngine, Orchestrator, and API.

Verifies that:
- PolicyEngine auto-snapshots versions on hot_swap when a version manager is attached
- PolicyConfig creates version managers when enable_versioning=True
- SecurityOrchestrator wires version manager through the bootstrap pipeline
- SecurityAPI exposes versioning endpoints (list, rollback, diff)
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.config import PolicyConfig, SecurityConfig
from fastmcp.server.security.http.api import SecurityAPI
from fastmcp.server.security.orchestrator import SecurityOrchestrator
from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyProvider,
    PolicyResult,
)
from fastmcp.server.security.policy.versioning.manager import PolicyVersionManager
from fastmcp.server.security.storage.memory import MemoryBackend as InMemoryBackend


class DenyAllPolicy(PolicyProvider):
    """Test policy that denies everything."""

    def get_policy_id(self) -> str:
        return "deny-all"

    def get_policy_version(self) -> str:
        return "1.0.0"

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        return PolicyResult(
            decision=PolicyDecision.DENY,
            reason="Denied by DenyAllPolicy",
            policy_id="deny-all",
        )


class CustomPolicy(PolicyProvider):
    """Test policy with custom id and version."""

    def __init__(self, policy_id: str = "custom", version: str = "2.0.0"):
        self._id = policy_id
        self._version = version

    def get_policy_id(self) -> str:
        return self._id

    def get_policy_version(self) -> str:
        return self._version

    def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Allowed by CustomPolicy",
            policy_id=self._id,
        )


# ── Engine + VersionManager ──────────────────────────────────────


class TestEngineVersionManagerWiring:
    """Test that PolicyEngine integrates with PolicyVersionManager."""

    def test_engine_accepts_version_manager(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(version_manager=vm)
        assert engine.version_manager is vm

    def test_engine_without_version_manager(self):
        engine = PolicyEngine()
        assert engine.version_manager is None

    @pytest.mark.anyio
    async def test_hot_swap_creates_version_snapshot(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        new_policy = CustomPolicy(policy_id="new-policy", version="2.0.0")
        await engine.hot_swap(0, new_policy, reason="Upgrade to v2")

        assert vm.version_count == 2
        version = vm.current_version
        assert version is not None
        assert "new-policy" in version.description
        assert version.author == "policy-engine"
        assert version.policy_data["metadata"]["old_policy_id"] == "allow-all"
        assert version.policy_data["metadata"]["new_policy_id"] == "new-policy"
        assert version.policy_data["providers"][0]["type"] == "python_class"

    @pytest.mark.anyio
    async def test_hot_swap_without_version_manager_still_works(self):
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        new_policy = CustomPolicy()
        record = await engine.hot_swap(0, new_policy, reason="Test")
        assert record.new_policy_id == "custom"
        # No version manager → no crash

    @pytest.mark.anyio
    async def test_multiple_hot_swaps_create_multiple_versions(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        await engine.hot_swap(0, CustomPolicy("v1", "1.0"), reason="First")
        await engine.hot_swap(0, CustomPolicy("v2", "2.0"), reason="Second")
        await engine.hot_swap(0, CustomPolicy("v3", "3.0"), reason="Third")

        assert vm.version_count == 4
        versions = vm.list_versions()
        assert versions[1].policy_data["metadata"]["new_policy_id"] == "v1"
        assert versions[2].policy_data["metadata"]["new_policy_id"] == "v2"
        assert versions[3].policy_data["metadata"]["new_policy_id"] == "v3"

    @pytest.mark.anyio
    async def test_hot_swap_version_includes_reason(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        await engine.hot_swap(0, CustomPolicy(), reason="Security patch")
        version = vm.current_version
        assert version is not None
        assert "Security patch" in version.description

    @pytest.mark.anyio
    async def test_add_and_remove_create_versions(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        await engine.add_provider(CustomPolicy("added", "1.1"), reason="Expand chain")
        assert vm.version_count == 2
        assert vm.current_version is not None
        assert vm.current_version.policy_data["metadata"]["operation"] == "add"

        await engine.remove_provider(1, reason="Undo expand")
        assert vm.version_count == 3
        assert vm.current_version is not None
        assert vm.current_version.policy_data["metadata"]["operation"] == "remove"

    @pytest.mark.anyio
    async def test_rollback_restores_live_engine(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        await engine.hot_swap(0, DenyAllPolicy(), reason="Lock down")
        first_version = vm.list_versions()[0]

        await engine.restore_version(first_version.policy_data, reason="Rollback")

        restored = engine.providers[0]
        assert isinstance(restored, AllowAllPolicy)

    @pytest.mark.anyio
    async def test_hot_swap_version_manager_error_does_not_block_swap(self):
        """If version manager fails, the swap still completes."""

        class BrokenBackend:
            def load_policy_versions(self, *a, **kw):
                return None

            def save_policy_version(self, *a, **kw):
                raise RuntimeError("Storage failure")

        vm = PolicyVersionManager(
            policy_set_id="test",
            backend=BrokenBackend(),  # type: ignore[arg-type]
        )
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        # Should not raise despite broken backend
        record = await engine.hot_swap(0, CustomPolicy(), reason="Test")
        assert record.new_policy_id == "custom"
        # The provider was actually swapped
        assert type(engine.providers[0]).__name__ == "CustomPolicy"


# ── PolicyConfig ─────────────────────────────────────────────────


class TestPolicyConfigVersioning:
    """Test PolicyConfig version manager creation."""

    def test_versioning_disabled_returns_none(self):
        config = PolicyConfig(enable_versioning=False)
        assert config.get_version_manager() is None

    def test_versioning_enabled_creates_manager(self):
        config = PolicyConfig(enable_versioning=True)
        vm = config.get_version_manager(policy_set_id="my-server")
        assert vm is not None
        assert isinstance(vm, PolicyVersionManager)
        assert vm.policy_set_id == "my-server"

    def test_versioning_uses_provided_backend(self):
        backend = InMemoryBackend()
        config = PolicyConfig(enable_versioning=True, backend=backend)
        vm = config.get_version_manager()
        assert vm is not None
        assert vm._backend is backend

    def test_versioning_creates_inmemory_backend_if_none(self):
        config = PolicyConfig(enable_versioning=True, backend=None)
        vm = config.get_version_manager()
        assert vm is not None
        # Should have an InMemoryBackend
        assert type(vm._backend).__name__ == "MemoryBackend"

    def test_get_engine_passes_version_manager(self):
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        config = PolicyConfig()
        engine = config.get_engine(version_manager=vm)
        assert engine.version_manager is vm

    def test_get_engine_injects_into_existing_engine(self):
        """If engine is pre-built, version_manager is injected."""
        existing_engine = PolicyEngine()
        assert existing_engine.version_manager is None

        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        config = PolicyConfig(engine=existing_engine)
        returned = config.get_engine(version_manager=vm)
        assert returned is existing_engine
        assert returned.version_manager is vm


# ── Orchestrator ─────────────────────────────────────────────────


class TestOrchestratorVersioning:
    """Test SecurityOrchestrator wires version manager correctly."""

    def test_versioning_disabled_no_manager(self):
        config = SecurityConfig(
            policy=PolicyConfig(providers=[AllowAllPolicy()]),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_version_manager is None
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.version_manager is None

    def test_versioning_enabled_creates_manager(self):
        config = SecurityConfig(
            policy=PolicyConfig(
                providers=[AllowAllPolicy()],
                enable_versioning=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config, server_name="test-server")
        assert ctx.policy_version_manager is not None
        assert ctx.policy_version_manager.policy_set_id == "test-server"
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.version_manager is ctx.policy_version_manager

    def test_backend_propagation(self):
        """Shared backend propagates from SecurityConfig to PolicyConfig."""
        backend = InMemoryBackend()
        config = SecurityConfig(
            policy=PolicyConfig(
                providers=[AllowAllPolicy()],
                enable_versioning=True,
            ),
            backend=backend,
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_version_manager is not None
        assert ctx.policy_version_manager._backend is backend

    @pytest.mark.anyio
    async def test_hot_swap_through_orchestrated_engine(self):
        """End-to-end: bootstrap → hot_swap → version created."""
        config = SecurityConfig(
            policy=PolicyConfig(
                providers=[AllowAllPolicy()],
                enable_versioning=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        assert ctx.policy_engine is not None
        assert ctx.policy_version_manager is not None

        await ctx.policy_engine.hot_swap(0, CustomPolicy(), reason="Orchestrator test")
        assert ctx.policy_version_manager.version_count == 2


# ── SecurityAPI ──────────────────────────────────────────────────


class TestSecurityAPIVersioning:
    """Test SecurityAPI versioning endpoints."""

    def _make_api_with_versioning(self) -> SecurityAPI:
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )
        return SecurityAPI(
            policy_engine=engine,
            policy_version_manager=vm,
        )

    def test_from_context_includes_version_manager(self):
        config = SecurityConfig(
            policy=PolicyConfig(
                providers=[AllowAllPolicy()],
                enable_versioning=True,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        api = SecurityAPI.from_context(ctx)
        assert api.policy_version_manager is not None

    def test_get_versions_initial_snapshot(self):
        api = self._make_api_with_versioning()
        result = api.get_policy_versions()
        assert result["version_count"] == 1
        assert len(result["versions"]) == 1
        assert result["current_version"] == 1

    def test_get_versions_after_create(self):
        api = self._make_api_with_versioning()
        assert api.policy_version_manager is not None
        api.policy_version_manager.create_version(
            policy_data={"rules": ["allow-all"]},
            author="test",
            description="Initial version",
        )
        result = api.get_policy_versions()
        assert result["version_count"] == 2
        assert result["current_version"] == 2
        assert len(result["versions"]) == 2

    @pytest.mark.anyio
    async def test_rollback_success(self):
        api = self._make_api_with_versioning()
        assert api.policy_engine is not None
        await api.policy_engine.hot_swap(0, DenyAllPolicy(), reason="V2")
        result = await api.rollback_policy_version(1, reason="Revert")
        assert result["status"] == "rolled_back"
        assert result["version"]["version_number"] == 1
        assert isinstance(api.policy_engine.providers[0], AllowAllPolicy)

    @pytest.mark.anyio
    async def test_rollback_invalid_version(self):
        api = self._make_api_with_versioning()
        result = await api.rollback_policy_version(99)
        assert "error" in result

    def test_diff_versions(self):
        api = self._make_api_with_versioning()
        assert api.policy_version_manager is not None
        api.policy_version_manager.create_version(
            policy_data={"a": 1, "b": 2}, author="test", description="V1"
        )
        api.policy_version_manager.create_version(
            policy_data={"a": 1, "c": 3}, author="test", description="V2"
        )
        result = api.diff_policy_versions(2, 3)
        assert result["v1"] == 2
        assert result["v2"] == 3
        diff = result["diff"]
        assert "b" in diff["removed"]
        assert "c" in diff["added"]

    def test_diff_invalid_version(self):
        api = self._make_api_with_versioning()
        result = api.diff_policy_versions(1, 2)
        assert "error" in result

    @pytest.mark.anyio
    async def test_add_update_delete_provider_through_api(self):
        api = self._make_api_with_versioning()

        created = await api.add_policy_provider(
            {"type": "denylist", "denied": ["admin-*"]},
            reason="Add denylist",
            author="reviewer",
        )
        assert created["status"] == "created"
        assert created["policy"]["provider_count"] == 2

        updated = await api.update_policy_provider(
            1,
            {"type": "allowlist", "allowed": ["tool:*"]},
            reason="Swap denylist",
            author="reviewer",
        )
        assert updated["status"] == "updated"
        assert updated["policy"]["providers"][1]["config"]["type"] == "allowlist"

        deleted = await api.delete_policy_provider(
            1,
            reason="Remove extra rule",
            author="reviewer",
        )
        assert deleted["status"] == "deleted"
        assert deleted["policy"]["provider_count"] == 1

    @pytest.mark.anyio
    async def test_not_configured_returns_503(self):
        api = SecurityAPI()
        assert api.get_policy_versions().get("status") == 503
        assert (await api.rollback_policy_version(1)).get("status") == 503
        assert api.diff_policy_versions(1, 2).get("status") == 503

    def test_health_includes_versioning(self):
        api = self._make_api_with_versioning()
        health = api.get_health()
        assert "policy_versioning" in health["components"]


# ── End-to-End ───────────────────────────────────────────────────


class TestEndToEndVersioning:
    """Full pipeline: config → orchestrator → engine → version manager → API."""

    @pytest.mark.anyio
    async def test_full_pipeline(self):
        backend = InMemoryBackend()
        config = SecurityConfig(
            policy=PolicyConfig(
                providers=[AllowAllPolicy()],
                enable_versioning=True,
                backend=backend,
            ),
        )
        ctx = SecurityOrchestrator.bootstrap(config)
        api = SecurityAPI.from_context(ctx)

        # Verify wiring
        assert ctx.policy_version_manager is not None
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.version_manager is ctx.policy_version_manager
        assert api.policy_version_manager is ctx.policy_version_manager

        # Initially empty
        versions = api.get_policy_versions()
        assert versions["version_count"] == 1

        # Do a hot swap
        await ctx.policy_engine.hot_swap(
            0, CustomPolicy("upgraded", "3.0"), reason="Upgrade"
        )

        # Version was created
        versions = api.get_policy_versions()
        assert versions["version_count"] == 2
        assert versions["current_version"] == 2

        # The version data captures the swap
        v = versions["versions"][1]
        assert v["policy_data"]["metadata"]["old_policy_id"] == "allow-all"
        assert v["policy_data"]["metadata"]["new_policy_id"] == "upgraded"

        # Do another swap
        await ctx.policy_engine.hot_swap(
            0, CustomPolicy("final", "4.0"), reason="Final"
        )

        # Diff the two versions
        diff_result = api.diff_policy_versions(2, 3)
        assert "diff" in diff_result
        changed = diff_result["diff"]["changed"]["metadata"]
        assert changed["from"]["new_policy_id"] == "upgraded"
        assert changed["to"]["new_policy_id"] == "final"

        # Rollback to version 1
        rollback = await api.rollback_policy_version(1, reason="Reverting")
        assert rollback["status"] == "rolled_back"

        # Current version is now 1
        versions = api.get_policy_versions()
        assert versions["current_version"] == 1
        assert isinstance(ctx.policy_engine.providers[0], AllowAllPolicy)

    @pytest.mark.anyio
    async def test_versioning_persists_to_backend(self):
        """Verify versions are persisted to the storage backend."""
        backend = InMemoryBackend()
        vm = PolicyVersionManager(policy_set_id="persist-test", backend=backend)
        engine = PolicyEngine(
            providers=[AllowAllPolicy()],
            version_manager=vm,
        )

        await engine.hot_swap(0, CustomPolicy(), reason="Persist test")

        # Check that data was saved to backend
        data = backend.load_policy_versions("persist-test")
        assert data is not None
        assert len(data["versions"]) == 2
        assert data["current_version_index"] == 1
