"""Tests for SecureMCP-owned settings and helper integration."""

from __future__ import annotations

import pytest

from fastmcp import FastMCP
from fastmcp.server.security import attach_security, get_security_context
from fastmcp.server.security.config import PolicyConfig, SecurityConfig
from fastmcp.server.security.middleware.policy_enforcement import (
    PolicyEnforcementMiddleware,
)
from fastmcp.server.security.orchestrator import SecurityContext
from fastmcp.server.security.policy.provider import AllowAllPolicy
from fastmcp.server.security.settings import SecuritySettings, get_security_settings
from fastmcp.settings import Settings


def _clear_security_env(monkeypatch) -> None:
    for name in [
        "SECUREMCP_ENABLED",
        "SECUREMCP_POLICY_FAIL_CLOSED",
        "SECUREMCP_POLICY_BYPASS_STDIO",
        "SECUREMCP_POLICY_HOT_SWAP",
        "FASTMCP_SECURITY_ENABLED",
        "FASTMCP_SECURITY_POLICY_FAIL_CLOSED",
        "FASTMCP_SECURITY_POLICY_BYPASS_STDIO",
        "FASTMCP_SECURITY_POLICY_HOT_SWAP",
    ]:
        monkeypatch.delenv(name, raising=False)


class TestSecuritySettings:
    def test_core_settings_no_longer_expose_security(self):
        settings = Settings()
        assert not hasattr(settings, "security")

    def test_get_security_context_ignores_legacy_server_field(self):
        server = FastMCP("test")
        setattr(server, "_security_context", SecurityContext(config=SecurityConfig()))

        assert get_security_context(server) is None

    def test_reads_securemcp_prefix(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_ENABLED", "false")
        monkeypatch.setenv("SECUREMCP_POLICY_BYPASS_STDIO", "false")

        settings = SecuritySettings()

        assert settings.enabled is False
        assert settings.policy_bypass_stdio is False

    def test_reads_legacy_fastmcp_prefix(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("FASTMCP_SECURITY_ENABLED", "false")
        monkeypatch.setenv("FASTMCP_SECURITY_POLICY_HOT_SWAP", "false")

        settings = get_security_settings()

        assert settings.enabled is False
        assert settings.policy_hot_swap is False

    def test_canonical_prefix_wins_over_legacy_prefix(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_BYPASS_STDIO", "false")
        monkeypatch.setenv("FASTMCP_SECURITY_POLICY_BYPASS_STDIO", "true")

        settings = SecuritySettings()

        assert settings.policy_bypass_stdio is False


class TestAttachSecuritySettings:
    def test_fastmcp_security_config_kwarg_is_removed(self):
        with pytest.raises(TypeError, match="attach_security"):
            FastMCP("test", security_config=SecurityConfig())

    def test_attach_security_uses_settings_bypass_stdio(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_BYPASS_STDIO", "false")

        server = FastMCP("test")
        attach_security(
            server,
            SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
        )

        policy_mw = next(
            m for m in server.middleware if isinstance(m, PolicyEnforcementMiddleware)
        )
        assert policy_mw.bypass_stdio is False

    def test_attach_security_override_beats_settings(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_BYPASS_STDIO", "false")

        server = FastMCP("test")
        attach_security(
            server,
            SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
            bypass_stdio=True,
        )

        policy_mw = next(
            m for m in server.middleware if isinstance(m, PolicyEnforcementMiddleware)
        )
        assert policy_mw.bypass_stdio is True

    def test_attach_security_respects_disabled_setting(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_ENABLED", "false")

        server = FastMCP("test")
        ctx = attach_security(
            server,
            SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
        )

        assert get_security_context(server) is ctx
        assert ctx.policy_engine is None
        assert ctx.middleware == []
        assert not any(
            isinstance(m, PolicyEnforcementMiddleware) for m in server.middleware
        )

    def test_fail_closed_env_var_overrides_policy_config(self, monkeypatch):
        """Operator setting SECUREMCP_POLICY_FAIL_CLOSED=false must propagate
        all the way to the live PolicyEngine, even though PolicyConfig
        defaults to fail_closed=True."""
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_FAIL_CLOSED", "false")

        server = FastMCP("test")
        ctx = attach_security(
            server,
            SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
        )
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.fail_closed is False

    def test_hot_swap_env_var_overrides_policy_config(self, monkeypatch):
        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_HOT_SWAP", "false")

        server = FastMCP("test")
        ctx = attach_security(
            server,
            SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
        )
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.allow_hot_swap is False

    def test_no_explicit_env_vars_leaves_policy_config_alone(self, monkeypatch):
        """Without explicit env vars set, PolicyConfig values must be honored
        verbatim — no surprise overrides."""
        _clear_security_env(monkeypatch)

        server = FastMCP("test")
        ctx = attach_security(
            server,
            SecurityConfig(
                policy=PolicyConfig(
                    providers=[AllowAllPolicy()],
                    fail_closed=False,
                    allow_hot_swap=False,
                )
            ),
        )
        assert ctx.policy_engine is not None
        assert ctx.policy_engine.fail_closed is False
        assert ctx.policy_engine.allow_hot_swap is False

    def test_env_var_override_warns_when_no_policy_config(self, monkeypatch, caplog):
        import logging

        _clear_security_env(monkeypatch)
        monkeypatch.setenv("SECUREMCP_POLICY_FAIL_CLOSED", "false")

        server = FastMCP("test")
        with caplog.at_level(logging.WARNING):
            attach_security(server, SecurityConfig())

        assert any(
            "has no effect" in r.message and "config.policy is None" in r.message
            for r in caplog.records
        )

    def test_attach_security_warns_about_stdio_bypass(self, monkeypatch, caplog):
        """When STDIO bypass is on AND a policy is configured, operators
        must see a startup warning so they don't discover the bypass after
        a security incident."""
        import logging

        _clear_security_env(monkeypatch)

        server = FastMCP("test")
        with caplog.at_level(logging.WARNING):
            attach_security(
                server,
                SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
                bypass_stdio=True,
            )

        assert any(
            "bypass_stdio=True" in r.message and "STDIO transport" in r.message
            for r in caplog.records
        )

    def test_attach_security_no_stdio_warning_when_bypass_false(
        self, monkeypatch, caplog
    ):
        import logging

        _clear_security_env(monkeypatch)

        server = FastMCP("test")
        with caplog.at_level(logging.WARNING):
            attach_security(
                server,
                SecurityConfig(policy=PolicyConfig(providers=[AllowAllPolicy()])),
                bypass_stdio=False,
            )

        assert not any("bypass_stdio=True" in r.message for r in caplog.records)

    def test_orchestrator_uses_public_event_bus_setter(self, monkeypatch):
        """Regression test: the orchestrator must wire event buses through
        the public ``attach_event_bus`` API rather than poking the private
        ``_event_bus`` attribute. We verify by replacing ``attach_event_bus``
        on a built engine and asserting the orchestrator calls it."""
        from fastmcp.server.security.alerts.bus import SecurityEventBus
        from fastmcp.server.security.config import AlertConfig
        from fastmcp.server.security.policy.engine import PolicyEngine

        _clear_security_env(monkeypatch)
        engine = PolicyEngine(providers=[AllowAllPolicy()])
        captured: list[SecurityEventBus | None] = []
        original = engine.attach_event_bus

        def _spy(bus: SecurityEventBus | None) -> None:
            captured.append(bus)
            original(bus)

        engine.attach_event_bus = _spy  # type: ignore[method-assign]

        server = FastMCP("test")
        attach_security(
            server,
            SecurityConfig(
                policy=PolicyConfig(engine=engine),
                alerts=AlertConfig(),
            ),
        )

        # The spy was called with a real SecurityEventBus — proving the
        # orchestrator went through the public API and not the underscore.
        assert len(captured) == 1
        assert captured[0] is not None
        assert isinstance(captured[0], SecurityEventBus)
