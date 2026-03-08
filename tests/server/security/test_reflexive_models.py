"""Tests for Reflexive Core data models."""

from __future__ import annotations

from fastmcp.server.security.reflexive.models import (
    BehavioralBaseline,
    DriftEvent,
    DriftSeverity,
    DriftType,
    EscalationAction,
    EscalationRule,
)


class TestDriftEvent:
    def test_default_drift_event(self):
        event = DriftEvent()
        assert event.drift_type == DriftType.CUSTOM
        assert event.severity == DriftSeverity.INFO
        assert event.actor_id == ""
        assert event.observed_value == 0.0

    def test_drift_event_with_values(self):
        event = DriftEvent(
            drift_type=DriftType.FREQUENCY_SPIKE,
            severity=DriftSeverity.HIGH,
            actor_id="agent-1",
            observed_value=50.0,
            baseline_value=10.0,
            deviation=4.5,
            description="Spike detected",
        )
        assert event.drift_type == DriftType.FREQUENCY_SPIKE
        assert event.severity == DriftSeverity.HIGH
        assert event.actor_id == "agent-1"
        assert event.deviation == 4.5

    def test_drift_event_unique_ids(self):
        e1 = DriftEvent()
        e2 = DriftEvent()
        assert e1.event_id != e2.event_id

    def test_drift_event_frozen(self):
        event = DriftEvent()
        try:
            event.severity = DriftSeverity.CRITICAL  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestBehavioralBaseline:
    def test_default_baseline(self):
        bl = BehavioralBaseline()
        assert bl.sample_count == 0
        assert bl.mean == 0.0
        assert bl.variance == 0.0
        assert bl.std_dev == 0.0

    def test_update_single(self):
        bl = BehavioralBaseline(metric_name="test", actor_id="a1")
        bl.update(10.0)
        assert bl.sample_count == 1
        assert bl.mean == 10.0
        assert bl.min_value == 10.0
        assert bl.max_value == 10.0

    def test_update_multiple(self):
        bl = BehavioralBaseline()
        for v in [10, 20, 30]:
            bl.update(float(v))
        assert bl.sample_count == 3
        assert bl.mean == 20.0
        assert bl.min_value == 10.0
        assert bl.max_value == 30.0

    def test_std_dev(self):
        bl = BehavioralBaseline()
        # Known dataset: [2, 4, 4, 4, 5, 5, 7, 9]
        for v in [2, 4, 4, 4, 5, 5, 7, 9]:
            bl.update(float(v))
        assert bl.sample_count == 8
        assert abs(bl.mean - 5.0) < 0.01
        assert bl.std_dev > 0

    def test_std_dev_insufficient_data(self):
        bl = BehavioralBaseline()
        bl.update(5.0)
        assert bl.std_dev == 0.0

    def test_compute_deviation(self):
        bl = BehavioralBaseline()
        for v in [10, 10, 10, 10, 10, 11, 9, 10, 10, 10]:
            bl.update(float(v))
        # Now check deviation for a value far from mean
        dev = bl.compute_deviation(20.0)
        assert dev > 0

    def test_compute_deviation_insufficient_data(self):
        bl = BehavioralBaseline()
        bl.update(10.0)
        bl.update(10.0)
        assert bl.compute_deviation(100.0) == 0.0


class TestEscalationRule:
    def test_default_rule(self):
        rule = EscalationRule()
        assert rule.min_severity == DriftSeverity.MEDIUM
        assert rule.action == EscalationAction.ALERT
        assert rule.enabled is True

    def test_rule_matches_severity(self):
        rule = EscalationRule(min_severity=DriftSeverity.MEDIUM)
        low_event = DriftEvent(severity=DriftSeverity.LOW)
        med_event = DriftEvent(severity=DriftSeverity.MEDIUM)
        high_event = DriftEvent(severity=DriftSeverity.HIGH)

        assert not rule.matches(low_event)
        assert rule.matches(med_event)
        assert rule.matches(high_event)

    def test_rule_matches_drift_type(self):
        rule = EscalationRule(
            drift_types=[DriftType.FREQUENCY_SPIKE],
            min_severity=DriftSeverity.LOW,
        )
        spike = DriftEvent(
            drift_type=DriftType.FREQUENCY_SPIKE,
            severity=DriftSeverity.MEDIUM,
        )
        error = DriftEvent(
            drift_type=DriftType.ERROR_RATE,
            severity=DriftSeverity.MEDIUM,
        )
        assert rule.matches(spike)
        assert not rule.matches(error)

    def test_rule_disabled(self):
        rule = EscalationRule(
            min_severity=DriftSeverity.LOW,
            enabled=False,
        )
        event = DriftEvent(severity=DriftSeverity.CRITICAL)
        assert not rule.matches(event)

    def test_rule_empty_drift_types_matches_all(self):
        rule = EscalationRule(
            drift_types=[],
            min_severity=DriftSeverity.LOW,
        )
        for dt in DriftType:
            event = DriftEvent(drift_type=dt, severity=DriftSeverity.HIGH)
            assert rule.matches(event)
