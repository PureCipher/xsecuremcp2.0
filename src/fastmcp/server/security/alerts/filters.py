"""Composable event filters for the SecureMCP alert system.

Filters determine which events reach a subscriber. They compose with
AND logic via ``CompositeFilter``.

Example::

    # Only critical events from the reflexive layer
    my_filter = CompositeFilter(
        SeverityFilter(min_severity=AlertSeverity.CRITICAL),
        LayerFilter(layers={"reflexive"}),
    )
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastmcp.server.security.alerts.models import (
    AlertSeverity,
    SecurityEvent,
    SecurityEventType,
)


@runtime_checkable
class EventFilter(Protocol):
    """Protocol for event filters."""

    def matches(self, event: SecurityEvent) -> bool:
        """Return True if the event passes this filter."""
        ...


class SeverityFilter:
    """Filter events by minimum severity level.

    Example::

        f = SeverityFilter(min_severity=AlertSeverity.WARNING)
        f.matches(info_event)      # False
        f.matches(warning_event)   # True
        f.matches(critical_event)  # True
    """

    def __init__(self, min_severity: AlertSeverity = AlertSeverity.INFO) -> None:
        self.min_severity = min_severity

    def matches(self, event: SecurityEvent) -> bool:
        return event.severity >= self.min_severity


class LayerFilter:
    """Filter events by security layer.

    Example::

        f = LayerFilter(layers={"reflexive", "policy"})
    """

    def __init__(self, layers: set[str]) -> None:
        self.layers = layers

    def matches(self, event: SecurityEvent) -> bool:
        return event.layer in self.layers


class EventTypeFilter:
    """Filter events by event type.

    Example::

        f = EventTypeFilter(types={SecurityEventType.DRIFT_DETECTED})
    """

    def __init__(self, types: set[SecurityEventType]) -> None:
        self.types = types

    def matches(self, event: SecurityEvent) -> bool:
        return event.event_type in self.types


class ActorFilter:
    """Filter events by actor ID.

    Example::

        f = ActorFilter(actor_ids={"agent-1", "agent-2"})
    """

    def __init__(self, actor_ids: set[str]) -> None:
        self.actor_ids = actor_ids

    def matches(self, event: SecurityEvent) -> bool:
        return event.actor_id is not None and event.actor_id in self.actor_ids


class CompositeFilter:
    """Combine multiple filters with AND logic.

    All sub-filters must match for the event to pass.

    Example::

        f = CompositeFilter(
            SeverityFilter(AlertSeverity.WARNING),
            LayerFilter({"reflexive"}),
        )
    """

    def __init__(self, *filters: EventFilter) -> None:
        self.filters = list(filters)

    def matches(self, event: SecurityEvent) -> bool:
        return all(f.matches(event) for f in self.filters)
