"""Reflexive Core for SecureMCP (Phase 4 + Phase 11 + Reflexive Execution Engine).

Behavioral drift detection, anomaly analysis, escalation engine,
pluggable anomaly detectors, actor profiling, and introspective
self-examination for monitoring and gating agent behavior.
"""

from fastmcp.server.security.reflexive.analyzer import (
    BehavioralAnalyzer,
    EscalationEngine,
)
from fastmcp.server.security.reflexive.detectors import (
    AnomalyDetector,
    OperationPattern,
    PatternDetector,
    SlidingWindowDetector,
    WindowConfig,
)
from fastmcp.server.security.reflexive.introspection import (
    ConfirmationRequiredError,
    IntrospectionEngine,
)
from fastmcp.server.security.reflexive.models import (
    BehavioralBaseline,
    ComplianceStatus,
    DEFAULT_THREAT_THRESHOLDS,
    DriftEvent,
    DriftSeverity,
    DriftType,
    EscalationAction,
    EscalationRule,
    ExecutionVerdict,
    IntrospectionResult,
    ThreatLevel,
)
from fastmcp.server.security.reflexive.profiles import (
    ActorProfile,
    ActorProfileManager,
)

__all__ = [
    "DEFAULT_THREAT_THRESHOLDS",
    "ActorProfile",
    "ActorProfileManager",
    "AnomalyDetector",
    "BehavioralAnalyzer",
    "BehavioralBaseline",
    "ComplianceStatus",
    "ConfirmationRequiredError",
    "DriftEvent",
    "DriftSeverity",
    "DriftType",
    "EscalationAction",
    "EscalationEngine",
    "EscalationRule",
    "ExecutionVerdict",
    "IntrospectionEngine",
    "IntrospectionResult",
    "OperationPattern",
    "PatternDetector",
    "SlidingWindowDetector",
    "ThreatLevel",
    "WindowConfig",
]
