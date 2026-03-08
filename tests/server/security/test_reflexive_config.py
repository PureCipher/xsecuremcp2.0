"""Tests for Reflexive Core configuration."""

from __future__ import annotations

from fastmcp.server.security.config import (
    ReflexiveConfig,
    SecurityConfig,
)
from fastmcp.server.security.reflexive.analyzer import (
    BehavioralAnalyzer,
    EscalationEngine,
)
from fastmcp.server.security.reflexive.models import (
    DriftSeverity,
    EscalationAction,
    EscalationRule,
)


class TestReflexiveConfig:
    def test_default_config(self):
        config = ReflexiveConfig()
        assert config.analyzer is None
        assert config.escalation_engine is None
        assert config.min_samples == 10

    def test_get_analyzer_default(self):
        config = ReflexiveConfig()
        analyzer = config.get_analyzer()
        assert isinstance(analyzer, BehavioralAnalyzer)

    def test_get_analyzer_custom(self):
        custom = BehavioralAnalyzer(min_samples=50)
        config = ReflexiveConfig(analyzer=custom)
        assert config.get_analyzer() is custom

    def test_get_analyzer_with_thresholds(self):
        thresholds = {DriftSeverity.LOW: 1.5, DriftSeverity.CRITICAL: 3.0}
        config = ReflexiveConfig(sigma_thresholds=thresholds, min_samples=5)
        analyzer = config.get_analyzer()
        # Verify the thresholds were passed through
        assert analyzer._sigma_thresholds == thresholds
        assert analyzer._min_samples == 5

    def test_get_escalation_engine_default(self):
        config = ReflexiveConfig()
        engine = config.get_escalation_engine()
        assert isinstance(engine, EscalationEngine)
        assert len(engine.rules) == 0

    def test_get_escalation_engine_custom(self):
        custom = EscalationEngine()
        config = ReflexiveConfig(escalation_engine=custom)
        assert config.get_escalation_engine() is custom

    def test_get_escalation_engine_with_rules(self):
        rules = [
            EscalationRule(
                min_severity=DriftSeverity.HIGH,
                action=EscalationAction.SUSPEND_AGENT,
            ),
        ]
        config = ReflexiveConfig(escalation_rules=rules)
        engine = config.get_escalation_engine()
        assert len(engine.rules) == 1


class TestSecurityConfigReflexive:
    def test_reflexive_not_enabled_by_default(self):
        config = SecurityConfig()
        assert not config.is_reflexive_enabled()

    def test_reflexive_enabled(self):
        config = SecurityConfig(reflexive=ReflexiveConfig())
        assert config.is_reflexive_enabled()

    def test_reflexive_disabled_by_master_switch(self):
        config = SecurityConfig(
            reflexive=ReflexiveConfig(),
            enabled=False,
        )
        assert not config.is_reflexive_enabled()
