"""Built-in event handlers for the SecureMCP alert system.

Handlers are callables that receive ``SecurityEvent`` instances from the bus.
These built-in handlers cover common use cases.

Example::

    bus = SecurityEventBus()

    # Log all warnings and above
    bus.subscribe(
        handler=LoggingHandler(),
        event_filter=SeverityFilter(AlertSeverity.WARNING),
    )

    # Collect events in a buffer for batch processing
    buffer = BufferedHandler(max_size=1000)
    bus.subscribe(handler=buffer)
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from typing import Any, ClassVar

from fastmcp.server.security.alerts.models import AlertSeverity, SecurityEvent

logger = logging.getLogger(__name__)


class LoggingHandler:
    """Logs security events using Python's logging module.

    Maps event severity to log levels:
    - INFO → logging.INFO
    - WARNING → logging.WARNING
    - CRITICAL → logging.CRITICAL

    Attributes:
        logger_name: Name for the logger instance.
    """

    _severity_map: ClassVar[dict[AlertSeverity, int]] = {
        AlertSeverity.INFO: logging.INFO,
        AlertSeverity.WARNING: logging.WARNING,
        AlertSeverity.CRITICAL: logging.CRITICAL,
    }

    def __init__(self, logger_name: str = "securemcp.alerts") -> None:
        self._logger = logging.getLogger(logger_name)

    def __call__(self, event: SecurityEvent) -> None:
        level = self._severity_map.get(event.severity, logging.INFO)
        self._logger.log(
            level,
            "[%s] %s: %s (actor=%s, resource=%s)",
            event.layer,
            event.event_type.value,
            event.message,
            event.actor_id or "N/A",
            event.resource_id or "N/A",
        )


class CallbackHandler:
    """Wraps a user-provided callback as a handler.

    Example::

        def my_callback(event: SecurityEvent) -> None:
            send_to_slack(event.message)

        handler = CallbackHandler(my_callback)
    """

    def __init__(self, callback: Callable[[SecurityEvent], Any]) -> None:
        self._callback = callback

    def __call__(self, event: SecurityEvent) -> None:
        self._callback(event)


class BufferedHandler:
    """Collects events in an in-memory ring buffer.

    Useful for batch processing, dashboards, or testing.

    Attributes:
        max_size: Maximum number of events to retain. Oldest events
            are dropped when the buffer is full.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._buffer: deque[SecurityEvent] = deque(maxlen=max_size)
        self.max_size = max_size

    def __call__(self, event: SecurityEvent) -> None:
        self._buffer.append(event)

    @property
    def events(self) -> list[SecurityEvent]:
        """Get all buffered events (oldest first)."""
        return list(self._buffer)

    @property
    def count(self) -> int:
        """Number of events currently in the buffer."""
        return len(self._buffer)

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()

    def latest(self, n: int = 10) -> list[SecurityEvent]:
        """Get the N most recent events."""
        return list(self._buffer)[-n:]
