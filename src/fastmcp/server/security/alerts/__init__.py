"""Real-time alert system for SecureMCP.

Provides a centralized event bus with pub/sub, composable filtering,
and severity-based routing. All security layers emit events to the bus,
enabling real-time monitoring, dashboards, and incident response.
"""

from fastmcp.server.security.alerts.bus import SecurityEventBus, Subscription
from fastmcp.server.security.alerts.filters import (
    ActorFilter,
    CompositeFilter,
    EventFilter,
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

__all__ = [
    "ActorFilter",
    "AlertSeverity",
    "BufferedHandler",
    "CallbackHandler",
    "CompositeFilter",
    "EventFilter",
    "EventTypeFilter",
    "LayerFilter",
    "LoggingHandler",
    "SecurityEvent",
    "SecurityEventBus",
    "SecurityEventType",
    "SeverityFilter",
    "Subscription",
]
