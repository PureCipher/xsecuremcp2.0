"""Tests for the BehavioralAnalyzer."""

from __future__ import annotations

from fastmcp.server.security.reflexive.analyzer import BehavioralAnalyzer
from fastmcp.server.security.reflexive.models import DriftSeverity


class TestBehavioralAnalyzerBasics:
    def test_new_analyzer(self):
        analyzer = BehavioralAnalyzer()
        assert analyzer.total_drift_count == 0

    def test_observe_builds_baseline(self):
        analyzer = BehavioralAnalyzer(min_samples=5)
        for _ in range(5):
            analyzer.observe("a1", "metric", 10.0)

        bl = analyzer.get_baseline("a1", "metric")
        assert bl is not None
        assert bl.sample_count == 5
        assert bl.mean == 10.0

    def test_observe_no_drift_within_normal(self):
        analyzer = BehavioralAnalyzer(min_samples=10)
        # Build baseline with consistent values
        for _ in range(15):
            events = analyzer.observe("a1", "calls", 10.0)
        # Normal variation should not trigger drift
        assert analyzer.total_drift_count == 0

    def test_observe_detects_drift(self):
        analyzer = BehavioralAnalyzer(min_samples=10)
        # Build baseline: values around 10 with small variance
        for v in [10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 9, 10]:
            analyzer.observe("a1", "calls", float(v))

        # Now inject a massive spike
        events = analyzer.observe("a1", "calls", 100.0)
        assert len(events) > 0
        assert events[0].severity.value in ("low", "medium", "high", "critical")

    def test_no_drift_before_min_samples(self):
        analyzer = BehavioralAnalyzer(min_samples=20)
        # Even extreme values shouldn't trigger before min_samples
        for _ in range(10):
            analyzer.observe("a1", "calls", 10.0)
        events = analyzer.observe("a1", "calls", 1000.0)
        assert len(events) == 0


class TestBehavioralAnalyzerSeverity:
    def test_severity_classification(self):
        analyzer = BehavioralAnalyzer(
            min_samples=10,
            sigma_thresholds={
                DriftSeverity.LOW: 2.0,
                DriftSeverity.MEDIUM: 3.0,
                DriftSeverity.HIGH: 4.0,
                DriftSeverity.CRITICAL: 5.0,
            },
        )
        # The _classify_severity is internal but we can test via observe
        # First confirm that deviation mapping works
        assert analyzer._classify_severity(1.5) is None
        assert analyzer._classify_severity(2.0) == DriftSeverity.LOW
        assert analyzer._classify_severity(2.5) == DriftSeverity.LOW
        assert analyzer._classify_severity(3.0) == DriftSeverity.MEDIUM
        assert analyzer._classify_severity(4.0) == DriftSeverity.HIGH
        assert analyzer._classify_severity(5.0) == DriftSeverity.CRITICAL
        assert analyzer._classify_severity(10.0) == DriftSeverity.CRITICAL


class TestBehavioralAnalyzerQueries:
    def test_get_baseline_not_found(self):
        analyzer = BehavioralAnalyzer()
        assert analyzer.get_baseline("nobody", "nothing") is None

    def test_get_actor_baselines(self):
        analyzer = BehavioralAnalyzer()
        analyzer.observe("a1", "calls", 10.0)
        analyzer.observe("a1", "errors", 0.0)
        baselines = analyzer.get_actor_baselines("a1")
        assert "calls" in baselines
        assert "errors" in baselines

    def test_get_actor_baselines_empty(self):
        analyzer = BehavioralAnalyzer()
        assert analyzer.get_actor_baselines("nobody") == {}

    def test_drift_history_query(self):
        analyzer = BehavioralAnalyzer(min_samples=5)
        # Build baseline
        for v in [10, 10, 10, 10, 10, 11, 9, 10]:
            analyzer.observe("a1", "m", float(v))
        # Trigger drift
        analyzer.observe("a1", "m", 100.0)

        history = analyzer.get_drift_history(actor_id="a1")
        assert len(history) >= 1

    def test_drift_history_filter_by_severity(self):
        analyzer = BehavioralAnalyzer(min_samples=5)
        for v in [10, 10, 10, 10, 10, 11, 9, 10]:
            analyzer.observe("a1", "m", float(v))
        analyzer.observe("a1", "m", 100.0)

        # Filter by a severity that might not match
        history = analyzer.get_drift_history(severity=DriftSeverity.INFO)
        # INFO drift won't appear since that's below the LOW threshold
        assert all(e.severity == DriftSeverity.INFO for e in history)

    def test_drift_history_limit(self):
        analyzer = BehavioralAnalyzer(min_samples=5)
        for v in [10, 10, 10, 10, 10, 11, 9, 10]:
            analyzer.observe("a1", "m", float(v))
        # Trigger multiple drift events
        for _ in range(5):
            analyzer.observe("a1", "m", 100.0)

        history = analyzer.get_drift_history(limit=2)
        assert len(history) <= 2


class TestBehavioralAnalyzerReset:
    def test_reset_single_metric(self):
        analyzer = BehavioralAnalyzer()
        analyzer.observe("a1", "calls", 10.0)
        analyzer.observe("a1", "errors", 1.0)
        analyzer.reset_baseline("a1", "calls")
        assert analyzer.get_baseline("a1", "calls") is None
        assert analyzer.get_baseline("a1", "errors") is not None

    def test_reset_all_metrics(self):
        analyzer = BehavioralAnalyzer()
        analyzer.observe("a1", "calls", 10.0)
        analyzer.observe("a1", "errors", 1.0)
        analyzer.reset_baseline("a1")
        assert analyzer.get_actor_baselines("a1") == {}
