"""Tests for SDK & Integration Layer (Phase 19).

Covers the SecureMCPClient facade, security checks, provenance recording,
trust queries, tool profiles, compliance integration, decorators, and history.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from fastmcp.server.security.alerts.bus import SecurityEventBus
from fastmcp.server.security.alerts.handlers import BufferedHandler
from fastmcp.server.security.certification.manifest import (
    PermissionScope,
    SecurityManifest,
)
from fastmcp.server.security.compliance.frameworks import ComplianceFramework
from fastmcp.server.security.compliance.reports import (
    ComplianceReporter,
)
from fastmcp.server.security.federation.crl import CertificateRevocationList
from fastmcp.server.security.federation.federation import TrustFederation
from fastmcp.server.security.gateway.tool_marketplace import (
    ToolMarketplace,
)
from fastmcp.server.security.policy.engine import PolicyEngine
from fastmcp.server.security.policy.provider import (
    AllowAllPolicy,
    DenyAllPolicy,
)
from fastmcp.server.security.registry.registry import TrustRegistry
from fastmcp.server.security.sandbox.enforcer import SandboxedRunner
from fastmcp.server.security.sdk.client import (
    SecureMCPClient,
    SecurityCheckResult,
    ToolSecurityProfile,
)
from fastmcp.server.security.sdk.decorators import (
    SecurityDecorator,
    SecurityDecoratorConfig,
    SecurityDenied,
)

# ── Helpers ─────────────────────────────────────────────────────


def _make_manifest(tool_name: str = "test-tool", **kwargs: Any) -> SecurityManifest:
    defaults: dict[str, Any] = {
        "tool_name": tool_name,
        "version": "1.0.0",
        "author": "acme",
    }
    defaults.update(kwargs)
    return SecurityManifest(**cast(Any, defaults))


def _make_client(**kwargs) -> SecureMCPClient:
    return SecureMCPClient(**kwargs)


# ── SecurityCheckResult tests ────────────────────────────────────


class TestSecurityCheckResult:
    def test_default(self):
        r = SecurityCheckResult()
        assert r.check_id.startswith("chk-")
        assert r.allowed is True

    def test_to_dict(self):
        r = SecurityCheckResult(tool_name="test", allowed=False, reasons=["revoked"])
        d = r.to_dict()
        assert d["tool_name"] == "test"
        assert d["allowed"] is False
        assert "revoked" in d["reasons"]


# ── ToolSecurityProfile tests ────────────────────────────────────


class TestToolSecurityProfile:
    def test_default(self):
        p = ToolSecurityProfile()
        assert p.trust_score == 0.0
        assert not p.is_certified

    def test_to_dict(self):
        p = ToolSecurityProfile(tool_name="test", trust_score=0.9, is_certified=True)
        d = p.to_dict()
        assert d["tool_name"] == "test"
        assert d["trust_score"] == 0.9


# ── SecureMCPClient basic tests ──────────────────────────────────


class TestSecureMCPClientBasic:
    def test_empty_client(self):
        client = _make_client()
        assert client.check_count == 0
        assert client.registry is None
        assert client.marketplace is None
        assert client.federation is None

    def test_statistics(self):
        registry = TrustRegistry()
        client = _make_client(registry=registry)
        stats = client.get_statistics()
        assert stats["components_configured"] == 1
        assert "registry" in stats["components"]

    def test_statistics_all_components(self):
        client = _make_client(
            registry=TrustRegistry(),
            marketplace=ToolMarketplace(),
            federation=TrustFederation(),
            sandbox_runner=SandboxedRunner(),
            event_bus=SecurityEventBus(),
            crl=CertificateRevocationList(),
        )
        stats = client.get_statistics()
        assert stats["components_configured"] == 6


# ── Security check tests ────────────────────────────────────────


class TestSecurityChecks:
    def test_check_unknown_tool(self):
        client = _make_client()
        result = client.check_tool("unknown-tool")
        assert result.allowed is True
        assert result.trust_score == 0.0

    def test_check_revoked_tool_crl(self):
        crl = CertificateRevocationList()
        crl.revoke("bad-tool")
        client = _make_client(crl=crl)
        result = client.check_tool("bad-tool")
        assert not result.allowed
        assert result.is_revoked

    def test_check_revoked_tool_federation(self):
        fed = TrustFederation()
        fed.local_crl.revoke("bad-tool")
        client = _make_client(federation=fed)
        result = client.check_tool("bad-tool")
        assert not result.allowed
        assert result.is_revoked

    def test_check_trust_score_threshold(self):
        registry = TrustRegistry()
        registry.register("low-trust", attestation=None)
        # Default score is 0.5
        client = _make_client(registry=registry)
        result = client.check_tool("low-trust", min_trust_score=0.9)
        assert not result.allowed
        assert len(result.reasons) > 0

    def test_check_trust_score_passes(self):
        registry = TrustRegistry()
        registry.register("good-tool", attestation=None)
        client = _make_client(registry=registry)
        result = client.check_tool("good-tool", min_trust_score=0.1)
        assert result.allowed
        assert result.trust_score > 0

    def test_check_with_sandbox(self):
        runner = SandboxedRunner()
        client = _make_client(sandbox_runner=runner)
        manifest = _make_manifest()
        result = client.check_tool("test-tool", manifest=manifest)
        assert result.allowed
        assert result.sandbox_context is not None

    def test_check_sandbox_blocked_by_crl(self):
        crl = CertificateRevocationList()
        crl.revoke("test-tool")
        runner = SandboxedRunner(crl=crl)
        client = _make_client(sandbox_runner=runner, crl=crl)
        manifest = _make_manifest()
        result = client.check_tool("test-tool", manifest=manifest)
        assert not result.allowed

    def test_check_history(self):
        client = _make_client()
        client.check_tool("tool-a")
        client.check_tool("tool-b")
        assert client.check_count == 2
        history = client.get_check_history()
        assert len(history) == 2

    def test_check_emits_event(self):
        bus = SecurityEventBus()
        handler = BufferedHandler(max_size=50)
        bus.subscribe(handler)
        client = _make_client(event_bus=bus)
        client.check_tool("test-tool")
        assert len(handler.events) == 1
        assert handler.events[0].layer == "sdk"


# ── Policy engine integration tests ──────────────────────────────


class TestPolicyEngineIntegration:
    """check_tool must actually consult the configured PolicyEngine.

    Regression test for the bug where policy_allowed was wired in but the
    engine was never invoked, so policy_allowed was always True.
    """

    def test_check_tool_consults_policy_engine_allow(self):
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        client = _make_client(policy_engine=engine)

        result = client.check_tool("good-tool", actor_id="alice")

        assert result.policy_allowed is True
        assert result.allowed is True
        # Engine evaluation count proves we actually called it.
        assert engine.evaluation_count == 1

    def test_check_tool_consults_policy_engine_deny(self):
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        client = _make_client(policy_engine=engine)

        result = client.check_tool("any-tool", actor_id="alice")

        assert result.policy_allowed is False
        assert result.allowed is False
        assert engine.evaluation_count == 1
        assert engine.deny_count == 1
        assert any("deny-all" in r for r in result.reasons)

    def test_check_tool_no_policy_engine_unchanged(self):
        client = _make_client()
        result = client.check_tool("any-tool")
        # When no engine is configured, the field stays at its dataclass
        # default — but no policy decision was implied.
        assert result.policy_allowed is True
        assert result.allowed is True

    def test_check_tool_policy_deny_combines_with_other_signals(self):
        """A policy DENY must remain a DENY even if everything else allows."""
        registry = TrustRegistry()
        registry.register("good-tool", attestation=None)
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        client = _make_client(registry=registry, policy_engine=engine)

        result = client.check_tool("good-tool", min_trust_score=0.0)

        assert result.policy_allowed is False
        assert result.allowed is False
        assert result.trust_score > 0  # registry signal still recorded

    def test_check_tool_forwards_actor_and_action(self):
        """The PolicyEvaluationContext must reflect the SDK call's actor."""
        observed: list[Any] = []

        class RecordingPolicy(AllowAllPolicy):
            async def evaluate(self, context):
                observed.append(context)
                return await super().evaluate(context)

        engine = PolicyEngine(providers=[RecordingPolicy()])
        client = _make_client(policy_engine=engine)

        client.check_tool(
            "tool-x",
            actor_id="alice",
            policy_action="invoke",
            policy_metadata={"src": "sdk-test"},
        )

        assert len(observed) == 1
        ctx = observed[0]
        assert ctx.actor_id == "alice"
        assert ctx.action == "invoke"
        assert ctx.resource_id == "tool-x"
        assert ctx.metadata == {"src": "sdk-test"}

    async def test_acheck_tool_awaits_engine_directly(self):
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        client = _make_client(policy_engine=engine)

        result = await client.acheck_tool("any-tool", actor_id="bob")

        assert result.policy_allowed is False
        assert result.allowed is False
        assert engine.evaluation_count == 1

    async def test_check_tool_inside_running_loop_raises(self):
        """Sync check_tool inside an event loop must fail loudly, not silently
        skip the policy. Callers should switch to acheck_tool."""
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        client = _make_client(policy_engine=engine)

        with pytest.raises(RuntimeError, match="acheck_tool"):
            client.check_tool("tool-y")

        # The engine was never evaluated because we refused to deadlock.
        assert engine.evaluation_count == 0

    def test_check_tool_inside_running_loop_no_engine_still_works(self):
        """Without a policy engine the loop check is bypassed entirely."""

        async def _run():
            client = _make_client()  # no policy_engine
            return client.check_tool("tool-z")

        result = asyncio.run(_run())
        assert result.allowed is True


# ── Trust query tests ────────────────────────────────────────────


class TestTrustQueries:
    def test_get_trust_score(self):
        registry = TrustRegistry()
        registry.register("my-tool", attestation=None)
        client = _make_client(registry=registry)
        assert client.get_trust_score("my-tool") > 0

    def test_get_trust_score_missing(self):
        client = _make_client()
        assert client.get_trust_score("unknown") == 0.0

    def test_is_tool_revoked(self):
        crl = CertificateRevocationList()
        crl.revoke("bad-tool")
        client = _make_client(crl=crl)
        assert client.is_tool_revoked("bad-tool")
        assert not client.is_tool_revoked("good-tool")

    def test_is_tool_revoked_federation(self):
        fed = TrustFederation()
        fed.local_crl.revoke("bad-tool")
        client = _make_client(federation=fed)
        assert client.is_tool_revoked("bad-tool")

    def test_is_tool_certified_registry(self):
        registry = TrustRegistry()
        registry.register("my-tool", attestation=None)
        client = _make_client(registry=registry)
        # Default registration isn't certified
        assert not client.is_tool_certified("my-tool")

    def test_is_tool_certified_no_components(self):
        client = _make_client()
        assert not client.is_tool_certified("anything")


# ── Tool profile tests ───────────────────────────────────────────


class TestToolProfile:
    def test_empty_profile(self):
        client = _make_client()
        profile = client.get_tool_profile("unknown")
        assert profile.tool_name == "unknown"
        assert profile.trust_score == 0.0

    def test_profile_with_registry(self):
        registry = TrustRegistry()
        registry.register("my-tool", attestation=None)
        client = _make_client(registry=registry)
        profile = client.get_tool_profile("my-tool")
        assert profile.trust_score > 0

    def test_profile_with_marketplace(self):
        mp = ToolMarketplace()
        mp.publish("pub-tool", display_name="Published Tool")
        client = _make_client(marketplace=mp)
        profile = client.get_tool_profile("pub-tool")
        assert profile.is_published

    def test_profile_revoked(self):
        crl = CertificateRevocationList()
        crl.revoke("bad-tool")
        client = _make_client(crl=crl)
        profile = client.get_tool_profile("bad-tool")
        assert profile.is_revoked


# ── Compliance integration tests ─────────────────────────────────


class TestComplianceIntegration:
    def test_run_compliance_report(self):
        fw = ComplianceFramework(name="Test")
        reporter = ComplianceReporter(framework=fw)
        client = _make_client(compliance_reporter=reporter)
        report = client.run_compliance_report()
        assert report is not None

    def test_run_compliance_no_reporter(self):
        client = _make_client()
        assert client.run_compliance_report() is None


# ── Provenance recording tests ───────────────────────────────────


class TestProvenanceRecording:
    def test_record_action_no_provenance(self):
        client = _make_client()
        assert client.record_action("tool", "execute") is None


# ── SecurityDecoratorConfig tests ────────────────────────────────


class TestSecurityDecoratorConfig:
    def test_default(self):
        cfg = SecurityDecoratorConfig()
        assert cfg.config_id.startswith("sdcfg-")
        assert cfg.min_trust_score == 0.0
        assert cfg.record_provenance is True

    def test_with_permissions(self):
        cfg = SecurityDecoratorConfig(
            required_permissions={
                PermissionScope.NETWORK_ACCESS,
                PermissionScope.FILE_SYSTEM_READ,
            }
        )
        assert len(cfg.required_permissions) == 2

    def test_to_dict(self):
        cfg = SecurityDecoratorConfig(
            tool_name="test",
            sandbox_enabled=True,
            max_execution_seconds=60.0,
        )
        d = cfg.to_dict()
        assert d["tool_name"] == "test"
        assert d["sandbox_enabled"] is True
        assert d["max_execution_seconds"] == 60.0


# ── SecurityDecorator tests ──────────────────────────────────────


class TestSecurityDecorator:
    def test_default(self):
        dec = SecurityDecorator()
        assert dec.decorator_id.startswith("sd-")
        assert dec.tool_count == 0

    def test_register(self):
        dec = SecurityDecorator()
        cfg = dec.register("my-tool", min_trust_score=0.5)
        assert cfg.tool_name == "my-tool"
        assert cfg.min_trust_score == 0.5
        assert dec.tool_count == 1

    def test_register_with_config(self):
        dec = SecurityDecorator()
        config = SecurityDecoratorConfig(require_certification=True)
        cfg = dec.register("tool-a", config=config)
        assert cfg.tool_name == "tool-a"
        assert cfg.require_certification

    def test_unregister(self):
        dec = SecurityDecorator()
        dec.register("tool-a")
        assert dec.unregister("tool-a")
        assert dec.tool_count == 0
        assert not dec.unregister("nonexistent")

    def test_get_config(self):
        dec = SecurityDecorator()
        dec.register("tool-a", sandbox_enabled=True)
        cfg = dec.get_config("tool-a")
        assert cfg is not None
        assert cfg.sandbox_enabled
        assert dec.get_config("unknown") is None

    def test_get_tools_requiring_certification(self):
        dec = SecurityDecorator()
        dec.register("tool-a", require_certification=True)
        dec.register("tool-b", require_certification=False)
        assert dec.get_tools_requiring_certification() == ["tool-a"]

    def test_get_tools_with_sandbox(self):
        dec = SecurityDecorator()
        dec.register("tool-a", sandbox_enabled=True)
        dec.register("tool-b", sandbox_enabled=False)
        assert dec.get_tools_with_sandbox() == ["tool-a"]

    def test_to_dict(self):
        dec = SecurityDecorator()
        dec.register("tool-a")
        d = dec.to_dict()
        assert d["tool_count"] == 1
        assert "tool-a" in d["tools"]


# ── SecurityDecorator enforcement tests ─────────────────────────


class TestSecurityDecoratorEnforcement:
    """The decorator must actually wrap and enforce — not just register.

    Regression test for the bug where SecurityDecorator only stored
    metadata and never gated, signed, or recorded anything at call time.
    """

    def test_call_without_client_raises(self):
        """Wrapping works without a client; calling the wrapped fn fails loudly."""
        security = SecurityDecorator()

        @security("greet")
        def greet(name: str) -> str:
            return f"hi {name}"

        # Wrapping itself does not raise — the registry path is intact.
        assert security.tool_count == 1
        assert security.get_config("greet") is not None

        # Calling without a client must fail with a clear error.
        with pytest.raises(RuntimeError, match="no client attached"):
            greet("world")

    def test_sync_wrapper_allows_when_check_passes(self):
        client = SecureMCPClient()  # all checks effectively allow
        security = SecurityDecorator(client=client)

        @security("echo", min_trust_score=0.0)
        def echo(text: str) -> str:
            return text.upper()

        assert echo("ping") == "PING"
        assert client.check_count == 1

    def test_sync_wrapper_blocks_revoked_tool(self):
        crl = CertificateRevocationList()
        crl.revoke("bad-tool")
        client = SecureMCPClient(crl=crl)
        security = SecurityDecorator(client=client)

        @security("bad-tool")
        def runs() -> str:  # pragma: no cover — must never execute
            return "should not run"

        with pytest.raises(SecurityDenied) as exc_info:
            runs()
        assert exc_info.value.result.is_revoked is True

    def test_sync_wrapper_blocks_below_trust_threshold(self):
        registry = TrustRegistry()
        registry.register("low-trust", attestation=None)  # default trust 0.5
        client = SecureMCPClient(registry=registry)
        security = SecurityDecorator(client=client)

        @security("low-trust", min_trust_score=0.99)
        def runs() -> str:  # pragma: no cover
            return "nope"

        with pytest.raises(SecurityDenied) as exc_info:
            runs()
        assert any("Trust score" in r for r in exc_info.value.result.reasons)

    def test_sync_wrapper_blocks_when_policy_denies(self):
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        client = SecureMCPClient(policy_engine=engine)
        security = SecurityDecorator(client=client)

        @security("any")
        def runs() -> str:  # pragma: no cover
            return "nope"

        with pytest.raises(SecurityDenied):
            runs()
        assert engine.deny_count == 1

    def test_require_certification_enforced(self):
        registry = TrustRegistry()
        registry.register("uncertified", attestation=None)
        client = SecureMCPClient(registry=registry)
        security = SecurityDecorator(client=client)

        @security("uncertified", require_certification=True)
        def runs() -> str:  # pragma: no cover
            return "nope"

        with pytest.raises(SecurityDenied) as exc_info:
            runs()
        assert any("requires certification" in r for r in exc_info.value.result.reasons)

    def test_required_permissions_denied_without_manifest(self):
        """If the manifest doesn't grant the required permission, deny."""
        client = SecureMCPClient()
        security = SecurityDecorator(client=client)

        @security(
            "needs-net",
            required_permissions={PermissionScope.NETWORK_ACCESS},
            sandbox_enabled=False,  # no manifest available
        )
        def runs() -> str:  # pragma: no cover
            return "nope"

        with pytest.raises(SecurityDenied) as exc_info:
            runs()
        assert any(
            "missing required permissions" in r for r in exc_info.value.result.reasons
        )

    def test_required_permissions_satisfied_by_manifest(self):
        runner = SandboxedRunner()
        client = SecureMCPClient(sandbox_runner=runner)

        manifest = SecurityManifest(
            tool_name="needs-net",
            version="1.0.0",
            author="acme",
            permissions={PermissionScope.NETWORK_ACCESS},
        )
        security = SecurityDecorator(
            client=client,
            manifest_provider=lambda name, cfg: manifest,
        )

        @security(
            "needs-net",
            required_permissions={PermissionScope.NETWORK_ACCESS},
            sandbox_enabled=True,
        )
        def runs() -> str:
            return "ok"

        assert runs() == "ok"

    def test_provenance_recorded_on_success(self):
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        provenance = ProvenanceLedger()
        client = SecureMCPClient(provenance=provenance)
        security = SecurityDecorator(client=client)

        @security("traced")
        def runs(value: int) -> int:
            return value * 2

        assert runs(21) == 42
        records = provenance.get_records(resource_id="traced")
        assert len(records) == 1
        assert records[0].metadata.get("outcome") == "success"

    def test_provenance_recorded_on_failure(self):
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        provenance = ProvenanceLedger()
        client = SecureMCPClient(provenance=provenance)
        security = SecurityDecorator(client=client)

        @security("flaky")
        def runs() -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            runs()
        records = provenance.get_records(resource_id="flaky")
        assert len(records) == 1
        assert records[0].metadata.get("outcome") == "error"
        assert records[0].metadata.get("error_type") == "ValueError"

    def test_provenance_disabled_skips_recording(self):
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger

        provenance = ProvenanceLedger()
        client = SecureMCPClient(provenance=provenance)
        security = SecurityDecorator(client=client)

        @security("silent", record_provenance=False)
        def runs() -> str:
            return "ok"

        runs()
        assert provenance.get_records(resource_id="silent") == []

    async def test_async_wrapper_enforces_via_acheck_tool(self):
        engine = PolicyEngine(providers=[DenyAllPolicy()])
        client = SecureMCPClient(policy_engine=engine)
        security = SecurityDecorator(client=client)

        @security("async-tool")
        async def runs() -> str:  # pragma: no cover
            return "nope"

        with pytest.raises(SecurityDenied):
            await runs()
        assert engine.evaluation_count == 1

    async def test_async_wrapper_runs_when_allowed(self):
        client = SecureMCPClient()
        security = SecurityDecorator(client=client)

        @security("async-ok")
        async def runs(value: int) -> int:
            return value + 1

        assert await runs(41) == 42

    async def test_async_wrapper_enforces_timeout(self):
        client = SecureMCPClient()
        security = SecurityDecorator(client=client)

        @security("slow", max_execution_seconds=0.05)
        async def runs() -> str:
            await asyncio.sleep(1)
            return "never"  # pragma: no cover

        with pytest.raises(asyncio.TimeoutError):
            await runs()

    def test_bare_decorator_uses_function_name(self):
        client = SecureMCPClient()
        security = SecurityDecorator(client=client)

        @security
        def my_named_tool(x: int) -> int:
            return x

        assert my_named_tool(7) == 7
        assert security.get_config("my_named_tool") is not None

    def test_decorator_preserves_function_metadata(self):
        client = SecureMCPClient()
        security = SecurityDecorator(client=client)

        @security("documented")
        def documented(x: int) -> int:
            """Important docstring."""
            return x

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "Important docstring."

    def test_security_denied_carries_result(self):
        crl = CertificateRevocationList()
        crl.revoke("bad")
        client = SecureMCPClient(crl=crl)
        security = SecurityDecorator(client=client)

        @security("bad")
        def runs() -> None:  # pragma: no cover
            ...

        try:
            runs()
        except SecurityDenied as exc:
            assert exc.result.tool_name == "bad"
            assert exc.result.is_revoked is True
            assert "denied" in str(exc).lower()
        else:
            pytest.fail("SecurityDenied not raised")


# ── Import tests ─────────────────────────────────────────────────


class TestImports:
    def test_sdk_imports(self):
        from fastmcp.server.security.sdk import (
            SecureMCPClient,
        )

        assert SecureMCPClient is not None

    def test_top_level_imports(self):
        from fastmcp.server.security import (
            SecureMCPClient,
        )

        assert SecureMCPClient is not None
