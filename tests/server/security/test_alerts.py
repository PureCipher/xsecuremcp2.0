"""Tests for the real-time alert system (Phase 9).

Covers models, filters, event bus, handlers, and component integration.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from fastmcp.server.security.alerts.bus import SecurityEventBus
from fastmcp.server.security.alerts.filters import (
    ActorFilter,
    CompositeFilter,
    EventTypeFilter,
    LayerFilter,
    SeverityFilter,
)
from fastmcp.server.security.alerts.handlers import (
    BufferedHandler,
    CallbackHandler,
    LoggingHandler,
)
from fastmcp.server.security.alerts.models import (
    AlertSeverity,
    SecurityEvent,
    SecurityEventType,
)


def _event(
    event_type: SecurityEventType = SecurityEventType.DRIFT_DETECTED,
    severity: AlertSeverity = AlertSeverity.WARNING,
    layer: str = "reflexive",
    message: str = "test event",
    actor_id: str | None = "agent-1",
    resource_id: str | None = "tool:test",
    data: dict | None = None,
) -> SecurityEvent:
    return SecurityEvent(
        event_type=event_type,
        severity=severity,
        layer=layer,
        message=message,
        actor_id=actor_id,
        resource_id=resource_id,
        data=data or {},
    )


# ── Model Tests ───────────────────────────────────────────────


class TestSecurityEvent:
    def test_event_has_uuid(self):
        e = _event()
        assert len(e.event_id) == 36  # UUID format

    def test_event_has_timestamp(self):
        e = _event()
        assert isinstance(e.timestamp, datetime)

    def test_event_is_frozen(self):
        e = _event()
        with pytest.raises(AttributeError):
            e.message = "changed"  # type: ignore[misc]

    def test_event_fields(self):
        e = _event(
            event_type=SecurityEventType.POLICY_DENIED,
            severity=AlertSeverity.CRITICAL,
            layer="policy",
            message="denied!",
            actor_id="agent-x",
            resource_id="tool:db",
            data={"key": "val"},
        )
        assert e.event_type == SecurityEventType.POLICY_DENIED
        assert e.severity == AlertSeverity.CRITICAL
        assert e.layer == "policy"
        assert e.message == "denied!"
        assert e.actor_id == "agent-x"
        assert e.resource_id == "tool:db"
        assert e.data == {"key": "val"}


class TestAlertSeverity:
    def test_ordering(self):
        assert AlertSeverity.INFO < AlertSeverity.WARNING
        assert AlertSeverity.WARNING < AlertSeverity.CRITICAL
        assert AlertSeverity.CRITICAL > AlertSeverity.INFO

    def test_equality_comparison(self):
        assert AlertSeverity.WARNING >= AlertSeverity.WARNING
        assert AlertSeverity.WARNING <= AlertSeverity.WARNING

    def test_critical_ge_all(self):
        assert AlertSeverity.CRITICAL >= AlertSeverity.INFO
        assert AlertSeverity.CRITICAL >= AlertSeverity.WARNING
        assert AlertSeverity.CRITICAL >= AlertSeverity.CRITICAL


class TestSecurityEventType:
    def test_all_types_have_values(self):
        for t in SecurityEventType:
            assert isinstance(t.value, str)
            assert len(t.value) > 0

    def test_type_count(self):
        assert len(SecurityEventType) == 13


# ── Filter Tests ──────────────────────────────────────────────


class TestSeverityFilter:
    def test_matches_exact(self):
        f = SeverityFilter(min_severity=AlertSeverity.WARNING)
        assert f.matches(_event(severity=AlertSeverity.WARNING))

    def test_matches_higher(self):
        f = SeverityFilter(min_severity=AlertSeverity.WARNING)
        assert f.matches(_event(severity=AlertSeverity.CRITICAL))

    def test_rejects_lower(self):
        f = SeverityFilter(min_severity=AlertSeverity.WARNING)
        assert not f.matches(_event(severity=AlertSeverity.INFO))

    def test_info_matches_all(self):
        f = SeverityFilter(min_severity=AlertSeverity.INFO)
        for sev in AlertSeverity:
            assert f.matches(_event(severity=sev))


class TestLayerFilter:
    def test_matches(self):
        f = LayerFilter(layers={"reflexive", "policy"})
        assert f.matches(_event(layer="reflexive"))
        assert f.matches(_event(layer="policy"))

    def test_rejects(self):
        f = LayerFilter(layers={"reflexive"})
        assert not f.matches(_event(layer="consent"))


class TestEventTypeFilter:
    def test_matches(self):
        f = EventTypeFilter(types={SecurityEventType.DRIFT_DETECTED})
        assert f.matches(_event(event_type=SecurityEventType.DRIFT_DETECTED))

    def test_rejects(self):
        f = EventTypeFilter(types={SecurityEventType.DRIFT_DETECTED})
        assert not f.matches(_event(event_type=SecurityEventType.POLICY_DENIED))


class TestActorFilter:
    def test_matches(self):
        f = ActorFilter(actor_ids={"agent-1"})
        assert f.matches(_event(actor_id="agent-1"))

    def test_rejects_wrong_actor(self):
        f = ActorFilter(actor_ids={"agent-1"})
        assert not f.matches(_event(actor_id="agent-2"))

    def test_rejects_none_actor(self):
        f = ActorFilter(actor_ids={"agent-1"})
        assert not f.matches(_event(actor_id=None))


class TestCompositeFilter:
    def test_all_pass(self):
        f = CompositeFilter(
            SeverityFilter(AlertSeverity.WARNING),
            LayerFilter({"reflexive"}),
        )
        assert f.matches(_event(severity=AlertSeverity.WARNING, layer="reflexive"))

    def test_one_fails(self):
        f = CompositeFilter(
            SeverityFilter(AlertSeverity.WARNING),
            LayerFilter({"policy"}),
        )
        assert not f.matches(_event(severity=AlertSeverity.WARNING, layer="reflexive"))

    def test_empty_passes_all(self):
        f = CompositeFilter()
        assert f.matches(_event())


# ── Event Bus Tests ───────────────────────────────────────────


class TestSecurityEventBus:
    def test_subscribe_and_emit(self):
        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append, name="test")
        bus.emit(_event())
        assert len(received) == 1

    def test_emit_returns_delivery_count(self):
        bus = SecurityEventBus()
        bus.subscribe(handler=lambda e: None, name="h1")
        bus.subscribe(handler=lambda e: None, name="h2")
        count = bus.emit(_event())
        assert count == 2

    def test_filter_limits_delivery(self):
        bus = SecurityEventBus()
        received = []
        bus.subscribe(
            handler=received.append,
            event_filter=SeverityFilter(AlertSeverity.CRITICAL),
            name="critical-only",
        )
        bus.emit(_event(severity=AlertSeverity.INFO))
        bus.emit(_event(severity=AlertSeverity.CRITICAL))
        assert len(received) == 1
        assert received[0].severity == AlertSeverity.CRITICAL

    def test_unsubscribe(self):
        bus = SecurityEventBus()
        received = []
        sub_id = bus.subscribe(handler=received.append, name="test")
        assert bus.unsubscribe(sub_id)
        bus.emit(_event())
        assert len(received) == 0

    def test_unsubscribe_unknown_returns_false(self):
        bus = SecurityEventBus()
        assert not bus.unsubscribe("nonexistent-id")

    def test_handler_error_does_not_break_others(self):
        bus = SecurityEventBus()
        received = []

        def bad_handler(e):
            raise ValueError("boom")

        bus.subscribe(handler=bad_handler, name="bad")
        bus.subscribe(handler=received.append, name="good")

        bus.emit(_event())
        assert len(received) == 1
        assert bus.error_count == 1

    def test_event_count_tracks_total(self):
        bus = SecurityEventBus()
        bus.emit(_event())
        bus.emit(_event())
        assert bus.event_count == 2

    def test_subscription_count(self):
        bus = SecurityEventBus()
        s1 = bus.subscribe(handler=lambda e: None)
        bus.subscribe(handler=lambda e: None)
        assert bus.subscription_count == 2
        bus.unsubscribe(s1)
        assert bus.subscription_count == 1

    def test_clear_removes_all(self):
        bus = SecurityEventBus()
        bus.subscribe(handler=lambda e: None)
        bus.subscribe(handler=lambda e: None)
        bus.clear()
        assert bus.subscription_count == 0

    def test_no_subscribers_returns_zero(self):
        bus = SecurityEventBus()
        count = bus.emit(_event())
        assert count == 0

    def test_composite_filter_on_bus(self):
        bus = SecurityEventBus()
        received = []
        bus.subscribe(
            handler=received.append,
            event_filter=CompositeFilter(
                SeverityFilter(AlertSeverity.WARNING),
                LayerFilter({"reflexive"}),
            ),
        )
        bus.emit(_event(severity=AlertSeverity.INFO, layer="reflexive"))
        bus.emit(_event(severity=AlertSeverity.WARNING, layer="policy"))
        bus.emit(_event(severity=AlertSeverity.WARNING, layer="reflexive"))
        assert len(received) == 1


# ── Handler Tests ─────────────────────────────────────────────


class TestLoggingHandler:
    def test_logs_event(self, caplog):
        handler = LoggingHandler()
        import logging

        with caplog.at_level(logging.WARNING, logger="securemcp.alerts"):
            handler(_event(severity=AlertSeverity.WARNING))
        assert "drift_detected" in caplog.text

    def test_maps_severity_to_log_level(self, caplog):
        handler = LoggingHandler()
        import logging

        with caplog.at_level(logging.INFO, logger="securemcp.alerts"):
            handler(_event(severity=AlertSeverity.INFO))
        assert len(caplog.records) > 0
        assert caplog.records[0].levelno == logging.INFO


class TestCallbackHandler:
    def test_invokes_callback(self):
        received = []
        handler = CallbackHandler(received.append)
        handler(_event())
        assert len(received) == 1

    def test_callback_receives_event(self):
        captured = {}

        def cb(e):
            captured["event"] = e

        handler = CallbackHandler(cb)
        event = _event(message="hello")
        handler(event)
        assert captured["event"].message == "hello"


class TestBufferedHandler:
    def test_collects_events(self):
        handler = BufferedHandler(max_size=100)
        handler(_event())
        handler(_event())
        assert handler.count == 2

    def test_events_property(self):
        handler = BufferedHandler()
        e1 = _event(message="first")
        e2 = _event(message="second")
        handler(e1)
        handler(e2)
        events = handler.events
        assert len(events) == 2
        assert events[0].message == "first"

    def test_max_size_ring_buffer(self):
        handler = BufferedHandler(max_size=3)
        for i in range(5):
            handler(_event(message=f"event-{i}"))
        assert handler.count == 3
        assert handler.events[0].message == "event-2"

    def test_clear(self):
        handler = BufferedHandler()
        handler(_event())
        handler.clear()
        assert handler.count == 0

    def test_latest(self):
        handler = BufferedHandler()
        for i in range(10):
            handler(_event(message=f"e-{i}"))
        latest = handler.latest(3)
        assert len(latest) == 3
        assert latest[0].message == "e-7"
        assert latest[2].message == "e-9"


# ── Integration Tests ─────────────────────────────────────────


class TestAnalyzerIntegration:
    def test_drift_emits_event(self):
        from fastmcp.server.security.reflexive.analyzer import BehavioralAnalyzer
        from fastmcp.server.security.reflexive.models import DriftSeverity

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        analyzer = BehavioralAnalyzer(
            min_samples=5,
            sigma_thresholds={DriftSeverity.LOW: 2.0},
            event_bus=bus,
        )

        # Build a tight baseline around 10.0 with slight variation
        for i in range(20):
            analyzer.observe("agent-1", "metric", 10.0 + (i % 3) * 0.1)

        # Trigger drift with extreme value
        analyzer.observe("agent-1", "metric", 10000.0)

        drift_events = [
            e for e in received if e.event_type == SecurityEventType.DRIFT_DETECTED
        ]
        assert len(drift_events) >= 1
        assert drift_events[0].layer == "reflexive"
        assert drift_events[0].actor_id == "agent-1"

    def test_escalation_emits_event(self):
        from fastmcp.server.security.reflexive.analyzer import EscalationEngine
        from fastmcp.server.security.reflexive.models import (
            DriftEvent,
            DriftSeverity,
            DriftType,
            EscalationAction,
            EscalationRule,
        )

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        engine = EscalationEngine(
            rules=[
                EscalationRule(
                    min_severity=DriftSeverity.HIGH,
                    action=EscalationAction.SUSPEND_AGENT,
                ),
            ],
            event_bus=bus,
        )

        drift = DriftEvent(
            drift_type=DriftType.FREQUENCY_SPIKE,
            severity=DriftSeverity.CRITICAL,
            actor_id="agent-1",
            description="Big spike",
            observed_value=100.0,
            baseline_value=10.0,
            deviation=5.0,
        )
        engine.evaluate(drift)

        escalation_events = [
            e
            for e in received
            if e.event_type == SecurityEventType.ESCALATION_TRIGGERED
        ]
        assert len(escalation_events) == 1
        assert escalation_events[0].severity == AlertSeverity.CRITICAL


class TestPolicyEngineIntegration:
    def test_deny_emits_event(self):
        from fastmcp.server.security.policy.engine import PolicyEngine
        from fastmcp.server.security.policy.provider import (
            DenyAllPolicy,
            PolicyEvaluationContext,
        )

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        engine = PolicyEngine(providers=[DenyAllPolicy()], event_bus=bus)
        ctx = PolicyEvaluationContext(
            actor_id="agent-1",
            action="call_tool",
            resource_id="tool:test",
        )
        asyncio.get_event_loop().run_until_complete(engine.evaluate(ctx))

        deny_events = [
            e for e in received if e.event_type == SecurityEventType.POLICY_DENIED
        ]
        assert len(deny_events) == 1
        assert deny_events[0].actor_id == "agent-1"

    def test_allow_does_not_emit(self):
        from fastmcp.server.security.policy.engine import PolicyEngine
        from fastmcp.server.security.policy.provider import (
            AllowAllPolicy,
            PolicyEvaluationContext,
        )

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        engine = PolicyEngine(providers=[AllowAllPolicy()], event_bus=bus)
        ctx = PolicyEvaluationContext(
            actor_id="agent-1",
            action="call_tool",
            resource_id="tool:test",
        )
        asyncio.get_event_loop().run_until_complete(engine.evaluate(ctx))
        assert len(received) == 0

    def test_hot_swap_emits_event(self):
        from fastmcp.server.security.policy.engine import PolicyEngine
        from fastmcp.server.security.policy.provider import (
            AllowAllPolicy,
            DenyAllPolicy,
        )

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        engine = PolicyEngine(providers=[AllowAllPolicy()], event_bus=bus)
        asyncio.get_event_loop().run_until_complete(
            engine.hot_swap(0, DenyAllPolicy(), reason="testing")
        )

        swap_events = [
            e for e in received if e.event_type == SecurityEventType.POLICY_SWAPPED
        ]
        assert len(swap_events) == 1


class TestConsentGraphIntegration:
    def test_grant_emits_event(self):
        from fastmcp.server.security.consent.graph import ConsentGraph
        from fastmcp.server.security.consent.models import ConsentNode, NodeType

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        graph = ConsentGraph(event_bus=bus)
        graph.add_node(ConsentNode("owner", NodeType.AGENT, "Owner"))
        graph.add_node(ConsentNode("agent", NodeType.AGENT, "Agent"))
        graph.grant("owner", "agent", scopes={"read"})

        grant_events = [
            e for e in received if e.event_type == SecurityEventType.CONSENT_GRANTED
        ]
        assert len(grant_events) == 1
        assert grant_events[0].layer == "consent"

    def test_revoke_emits_event(self):
        from fastmcp.server.security.consent.graph import ConsentGraph
        from fastmcp.server.security.consent.models import ConsentNode, NodeType

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        graph = ConsentGraph(event_bus=bus)
        graph.add_node(ConsentNode("owner", NodeType.AGENT, "Owner"))
        graph.add_node(ConsentNode("agent", NodeType.AGENT, "Agent"))
        edge = graph.grant("owner", "agent", scopes={"read"})
        graph.revoke(edge.edge_id)

        revoke_events = [
            e for e in received if e.event_type == SecurityEventType.CONSENT_REVOKED
        ]
        assert len(revoke_events) == 1

    def test_delegate_emits_event(self):
        from fastmcp.server.security.consent.graph import ConsentGraph
        from fastmcp.server.security.consent.models import ConsentNode, NodeType

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        graph = ConsentGraph(event_bus=bus)
        graph.add_node(ConsentNode("owner", NodeType.AGENT, "Owner"))
        graph.add_node(ConsentNode("a1", NodeType.AGENT, "Agent 1"))
        graph.add_node(ConsentNode("a2", NodeType.AGENT, "Agent 2"))
        edge = graph.grant(
            "owner",
            "a1",
            scopes={"read"},
            delegatable=True,
            max_delegation_depth=2,
        )
        graph.delegate(edge.edge_id, "a2")

        delegate_events = [
            e for e in received if e.event_type == SecurityEventType.CONSENT_DELEGATED
        ]
        assert len(delegate_events) == 1


class TestMarketplaceIntegration:
    def test_register_emits_event(self):
        from fastmcp.server.security.gateway.marketplace import Marketplace

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        mp = Marketplace(event_bus=bus)
        mp.register(name="Test Server", endpoint="https://example.com")

        register_events = [
            e for e in received if e.event_type == SecurityEventType.SERVER_REGISTERED
        ]
        assert len(register_events) == 1

    def test_unregister_emits_event(self):
        from fastmcp.server.security.gateway.marketplace import Marketplace

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        mp = Marketplace(event_bus=bus)
        reg = mp.register(name="Test", endpoint="https://example.com")
        mp.unregister(reg.server_id)

        unreg_events = [
            e for e in received if e.event_type == SecurityEventType.SERVER_UNREGISTERED
        ]
        assert len(unreg_events) == 1

    def test_trust_change_emits_event(self):
        from fastmcp.server.security.gateway.marketplace import Marketplace
        from fastmcp.server.security.gateway.models import TrustLevel

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        mp = Marketplace(event_bus=bus)
        reg = mp.register(name="Test", endpoint="https://example.com")
        mp.update_trust_level(reg.server_id, TrustLevel.AUDITOR_VERIFIED)

        trust_events = [
            e for e in received if e.event_type == SecurityEventType.TRUST_CHANGED
        ]
        assert len(trust_events) == 1
        assert trust_events[0].data["new_level"] == "auditor_verified"


class TestProvenanceLedgerIntegration:
    def test_record_emits_event(self):
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger
        from fastmcp.server.security.provenance.records import ProvenanceAction

        bus = SecurityEventBus()
        received = []
        bus.subscribe(handler=received.append)

        ledger = ProvenanceLedger(event_bus=bus)
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="agent-1",
            resource_id="calculator",
        )

        prov_events = [
            e for e in received if e.event_type == SecurityEventType.PROVENANCE_RECORDED
        ]
        assert len(prov_events) == 1
        assert prov_events[0].actor_id == "agent-1"


# ── Config Tests ──────────────────────────────────────────────


class TestAlertConfig:
    def test_default_creates_bus(self):
        from fastmcp.server.security.config import AlertConfig

        config = AlertConfig()
        bus = config.get_event_bus()
        assert isinstance(bus, SecurityEventBus)

    def test_custom_bus(self):
        from fastmcp.server.security.config import AlertConfig

        bus = SecurityEventBus()
        config = AlertConfig(event_bus=bus)
        assert config.get_event_bus() is bus

    def test_security_config_alerts_enabled(self):
        from fastmcp.server.security.config import AlertConfig, SecurityConfig

        config = SecurityConfig(alerts=AlertConfig())
        assert config.is_alerts_enabled()

    def test_security_config_alerts_disabled(self):
        from fastmcp.server.security.config import SecurityConfig

        config = SecurityConfig()
        assert not config.is_alerts_enabled()


# ── No-bus backwards compatibility ────────────────────────────


class TestNoBusBackwardsCompat:
    """Ensure all components work fine without an event bus (default)."""

    def test_analyzer_no_bus(self):
        from fastmcp.server.security.reflexive.analyzer import BehavioralAnalyzer
        from fastmcp.server.security.reflexive.models import DriftSeverity

        analyzer = BehavioralAnalyzer(
            min_samples=5,
            sigma_thresholds={DriftSeverity.LOW: 2.0},
        )
        for i in range(20):
            analyzer.observe("a", "m", 10.0 + (i % 3) * 0.1)
        events = analyzer.observe("a", "m", 10000.0)
        assert len(events) >= 1  # Still detects drift

    def test_policy_engine_no_bus(self):
        from fastmcp.server.security.policy.engine import PolicyEngine
        from fastmcp.server.security.policy.provider import (
            DenyAllPolicy,
            PolicyDecision,
            PolicyEvaluationContext,
        )

        engine = PolicyEngine(providers=[DenyAllPolicy()])
        ctx = PolicyEvaluationContext(
            actor_id="a", action="call_tool", resource_id="tool:test"
        )
        result = asyncio.get_event_loop().run_until_complete(engine.evaluate(ctx))
        assert result.decision == PolicyDecision.DENY

    def test_consent_graph_no_bus(self):
        from fastmcp.server.security.consent.graph import ConsentGraph
        from fastmcp.server.security.consent.models import (
            ConsentNode,
            ConsentQuery,
            NodeType,
        )

        graph = ConsentGraph()
        graph.add_node(ConsentNode("o", NodeType.AGENT, "O"))
        graph.add_node(ConsentNode("a", NodeType.AGENT, "A"))
        graph.grant("o", "a", scopes={"read"})
        decision = graph.evaluate(
            ConsentQuery(source_id="o", target_id="a", scope="read")
        )
        assert decision.granted

    def test_marketplace_no_bus(self):
        from fastmcp.server.security.gateway.marketplace import Marketplace

        mp = Marketplace()
        reg = mp.register(name="T", endpoint="http://x")
        assert mp.server_count == 1
        mp.unregister(reg.server_id)
        assert mp.server_count == 0

    def test_ledger_no_bus(self):
        from fastmcp.server.security.provenance.ledger import ProvenanceLedger
        from fastmcp.server.security.provenance.records import ProvenanceAction

        ledger = ProvenanceLedger()
        ledger.record(
            action=ProvenanceAction.TOOL_CALLED,
            actor_id="a",
            resource_id="r",
        )
        assert ledger.record_count == 1


class TestEventBusTimeoutsAndAsync:
    """Regression tests for #12: handlers must not block the bus.

    The synchronous emit() path measures and warns on slow handlers.
    The asynchronous aemit() path concurrently dispatches handlers and
    hard-bounds each via asyncio.wait_for so a single slow handler can't
    block delivery to other subscribers.
    """

    def test_default_timeout_is_set(self):
        bus = SecurityEventBus()
        assert bus.default_handler_timeout_ms > 0

    def test_custom_default_timeout(self):
        bus = SecurityEventBus(default_handler_timeout_ms=250)
        assert bus.default_handler_timeout_ms == 250

    def test_emit_warns_on_slow_handler(self, caplog):
        import logging
        import time as _time

        bus = SecurityEventBus(default_handler_timeout_ms=10)

        def slow_handler(_event):
            _time.sleep(0.05)  # 50ms — exceeds the 10ms threshold

        bus.subscribe(slow_handler, name="slow")

        with caplog.at_level(logging.WARNING):
            delivered = bus.emit(_event())

        assert delivered == 1  # slow handler still runs to completion
        assert bus.slow_handler_count == 1
        assert any("Slow handler" in r.message for r in caplog.records)

    def test_emit_does_not_warn_for_fast_handler(self, caplog):
        import logging

        bus = SecurityEventBus(default_handler_timeout_ms=1000)
        bus.subscribe(lambda e: None, name="fast")

        with caplog.at_level(logging.WARNING):
            bus.emit(_event())

        assert bus.slow_handler_count == 0

    def test_emit_rejects_async_handler(self, caplog):
        """A coroutine handler reaching sync emit() must be skipped, not
        silently fired-and-forgotten or fed to asyncio.run."""
        import logging

        bus = SecurityEventBus()
        seen: list = []

        async def async_handler(event):  # pragma: no cover — must not run
            seen.append(event)

        bus.subscribe(async_handler, name="async")

        with caplog.at_level(logging.ERROR):
            delivered = bus.emit(_event())

        assert delivered == 0
        assert seen == []
        assert bus.error_count == 1
        assert any("async but emit() is sync" in r.message for r in caplog.records)

    def test_per_subscription_timeout_overrides_default(self, caplog):
        import logging
        import time as _time

        bus = SecurityEventBus(default_handler_timeout_ms=1000)

        def slow_handler(_event):
            _time.sleep(0.02)

        bus.subscribe(slow_handler, name="strict", timeout_ms=5)

        with caplog.at_level(logging.WARNING):
            bus.emit(_event())

        assert bus.slow_handler_count == 1

    def test_aemit_dispatches_async_handler(self):
        bus = SecurityEventBus()
        seen: list = []

        async def async_handler(event):
            seen.append(event)

        bus.subscribe(async_handler, name="async")
        delivered = asyncio.run(bus.aemit(_event()))

        assert delivered == 1
        assert len(seen) == 1

    def test_aemit_dispatches_sync_handler_off_thread(self):
        bus = SecurityEventBus()
        seen: list = []

        def sync_handler(event):
            seen.append(event)

        bus.subscribe(sync_handler, name="sync")
        delivered = asyncio.run(bus.aemit(_event()))

        assert delivered == 1
        assert len(seen) == 1

    def test_aemit_runs_handlers_concurrently(self):
        """Three handlers each sleeping 100ms should complete in roughly
        100ms total, not 300ms — proving they ran concurrently."""
        import time as _time

        bus = SecurityEventBus(default_handler_timeout_ms=2000)
        for i in range(3):
            bus.subscribe(
                lambda _e: _time.sleep(0.1),
                name=f"handler-{i}",
            )

        start = _time.monotonic()
        delivered = asyncio.run(bus.aemit(_event()))
        elapsed = _time.monotonic() - start

        assert delivered == 3
        # Concurrent execution: ~100ms; serial would be ~300ms.
        # Allow generous slack for thread scheduling.
        assert elapsed < 0.25, f"handlers ran serially ({elapsed:.2f}s)"

    def test_aemit_timeout_isolates_slow_handler(self):
        """A slow handler must not block delivery to fast handlers, and
        the timeout fires deterministically."""
        bus = SecurityEventBus(default_handler_timeout_ms=50)

        async def slow(_event):
            await asyncio.sleep(2.0)  # would exceed test timeout if not cancelled

        fast_seen: list = []

        def fast(event):
            fast_seen.append(event)

        bus.subscribe(slow, name="slow")
        bus.subscribe(fast, name="fast")

        delivered = asyncio.run(bus.aemit(_event()))

        # Fast handler delivered; slow handler timed out.
        assert delivered == 1
        assert len(fast_seen) == 1
        assert bus.timeout_count == 1
        assert bus.error_count == 1

    def test_aemit_failure_does_not_stop_others(self):
        bus = SecurityEventBus()
        ok_seen: list = []

        async def crashing(_event):
            raise RuntimeError("boom")

        async def good(event):
            ok_seen.append(event)

        bus.subscribe(crashing, name="bad")
        bus.subscribe(good, name="good")

        delivered = asyncio.run(bus.aemit(_event()))

        assert delivered == 1
        assert len(ok_seen) == 1
        assert bus.error_count == 1

    def test_aemit_respects_filter(self):
        from fastmcp.server.security.alerts.filters import SeverityFilter

        bus = SecurityEventBus()
        seen: list = []
        bus.subscribe(
            lambda e: seen.append(e),
            event_filter=SeverityFilter(min_severity=AlertSeverity.CRITICAL),
            name="crit-only",
        )

        # WARNING event — filtered out.
        asyncio.run(bus.aemit(_event(severity=AlertSeverity.WARNING)))
        assert seen == []

        # CRITICAL event — passes filter.
        asyncio.run(bus.aemit(_event(severity=AlertSeverity.CRITICAL)))
        assert len(seen) == 1
