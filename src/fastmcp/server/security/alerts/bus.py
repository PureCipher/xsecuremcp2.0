"""Central event bus for SecureMCP security alerts.

The ``SecurityEventBus`` is the core pub/sub hub. Components emit events
via ``emit()`` (synchronous) or ``aemit()`` (asynchronous), and
subscribers receive events that match their filters.

Per-handler timeouts apply to both paths: in ``emit()`` they bound how
long the bus will *wait* on a single handler before logging a slow
warning (the bus cannot forcibly interrupt sync code), and in
``aemit()`` they hard-cap each handler via ``asyncio.wait_for``.
A slow remote logging handler can no longer block the policy engine
from delivering ``POLICY_DENIED`` events to other subscribers.

Example::

    bus = SecurityEventBus(default_handler_timeout_ms=500)

    # Subscribe with a filter
    bus.subscribe(
        handler=my_handler,
        event_filter=SeverityFilter(min_severity=AlertSeverity.WARNING),
    )

    # Components emit events
    bus.emit(SecurityEvent(
        event_type=SecurityEventType.DRIFT_DETECTED,
        severity=AlertSeverity.WARNING,
        layer="reflexive",
        message="Drift detected",
    ))
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastmcp.server.security.alerts.filters import EventFilter
from fastmcp.server.security.alerts.models import SecurityEvent

logger = logging.getLogger(__name__)

# Default per-handler timeout (ms). 1 second is generous for fast in-process
# handlers and tight enough to surface remote/blocking handlers as slow.
_DEFAULT_HANDLER_TIMEOUT_MS = 1_000


@dataclass
class Subscription:
    """A registered event subscription.

    Attributes:
        subscription_id: Unique identifier for this subscription.
        handler: Callable invoked when a matching event is emitted.
        event_filter: Optional filter to limit which events reach the handler.
        name: Human-readable name for debugging.
        timeout_ms: Per-handler timeout in milliseconds. Overrides the
            bus-wide default. ``None`` means "use the bus default".
    """

    subscription_id: str
    handler: Callable[[SecurityEvent], Any]
    event_filter: EventFilter | None = None
    name: str = ""
    timeout_ms: float | None = None


class SecurityEventBus:
    """Central pub/sub event bus for security alerts.

    All SecureMCP components can emit events to the bus, and external
    systems can subscribe to receive filtered events in real-time.

    The bus is **synchronous** — ``emit()`` calls handlers inline.
    Handlers should be fast; long-running work should be offloaded.

    Example::

        bus = SecurityEventBus()
        events = []
        bus.subscribe(handler=events.append, name="collector")
        bus.emit(some_event)
        assert len(events) == 1
    """

    def __init__(
        self,
        *,
        default_handler_timeout_ms: float = _DEFAULT_HANDLER_TIMEOUT_MS,
    ) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._event_count: int = 0
        self._error_count: int = 0
        self._slow_count: int = 0
        self._timeout_count: int = 0
        self._default_timeout_ms = float(default_handler_timeout_ms)

    @property
    def default_handler_timeout_ms(self) -> float:
        """Default per-handler timeout in milliseconds."""
        return self._default_timeout_ms

    def subscribe(
        self,
        handler: Callable[[SecurityEvent], Any],
        event_filter: EventFilter | None = None,
        name: str = "",
        *,
        timeout_ms: float | None = None,
    ) -> str:
        """Register a handler to receive events.

        Args:
            handler: Callable invoked with each matching ``SecurityEvent``.
                May be sync or async; ``aemit()`` awaits async handlers,
                ``emit()`` invokes them via ``asyncio.run`` if no loop is
                running and otherwise refuses async handlers.
            event_filter: Optional filter to limit events. If None, all events
                are delivered.
            name: Human-readable name for this subscription.
            timeout_ms: Per-handler timeout. ``None`` means "use the bus
                default" (see ``default_handler_timeout_ms``).

        Returns:
            Subscription ID (use with ``unsubscribe()``).
        """
        sub_id = str(uuid.uuid4())
        self._subscriptions[sub_id] = Subscription(
            subscription_id=sub_id,
            handler=handler,
            event_filter=event_filter,
            name=name or f"sub-{sub_id[:8]}",
            timeout_ms=timeout_ms,
        )
        logger.debug("Subscription added: %s (%s)", name or sub_id[:8], sub_id)
        return sub_id

    def _effective_timeout_ms(self, sub: Subscription) -> float:
        return (
            sub.timeout_ms if sub.timeout_ms is not None else self._default_timeout_ms
        )

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription.

        Args:
            subscription_id: The ID returned by ``subscribe()``.

        Returns:
            True if the subscription was found and removed, False otherwise.
        """
        sub = self._subscriptions.pop(subscription_id, None)
        if sub is not None:
            logger.debug("Subscription removed: %s", sub.name)
            return True
        return False

    def emit(self, event: SecurityEvent) -> int:
        """Emit an event to all matching subscribers (synchronous).

        Each handler is wall-clock-timed against its effective timeout.
        Sync code cannot be safely interrupted from outside, so a slow
        handler is logged at WARNING and counted (``slow_handler_count``)
        but allowed to finish — the warning gives operators a signal to
        re-architect blocking handlers without dropping an event.

        Async handlers (coroutines) are not supported here: this method
        is synchronous and would have to invoke ``asyncio.run``, which
        is unsafe inside an active event loop. Use :meth:`aemit` from
        async contexts. A coroutine handler reaching ``emit()`` is
        logged as an error and the handler is skipped — never silently
        leaked.

        Args:
            event: The security event to broadcast.

        Returns:
            Number of handlers that received the event.
        """
        self._event_count += 1
        delivered = 0

        for sub in list(self._subscriptions.values()):
            try:
                if sub.event_filter is not None and not sub.event_filter.matches(event):
                    continue
                if inspect.iscoroutinefunction(sub.handler):
                    logger.error(
                        "Handler '%s' is async but emit() is sync; use aemit() "
                        "to dispatch this subscription. Skipping.",
                        sub.name,
                    )
                    self._error_count += 1
                    continue

                start = time.monotonic()
                result = sub.handler(event)
                if inspect.isawaitable(result):
                    # Defensive: a sync-typed handler returning an awaitable
                    # (e.g. a class with ``__call__`` decorated as async).
                    # We close the coroutine to prevent leaks rather than
                    # silently fire-and-forget.
                    if hasattr(result, "close"):
                        result.close()
                    logger.error(
                        "Handler '%s' returned an awaitable from sync emit(); "
                        "skipping. Use aemit() for async handlers.",
                        sub.name,
                    )
                    self._error_count += 1
                    continue
                elapsed_ms = (time.monotonic() - start) * 1000.0
                self._record_slow_handler(sub, event, elapsed_ms)
                delivered += 1
            except Exception as exc:
                self._error_count += 1
                logger.error(
                    "Handler '%s' failed on event %s: %s",
                    sub.name,
                    event.event_type.value,
                    exc,
                )

        return delivered

    async def aemit(self, event: SecurityEvent) -> int:
        """Emit an event to all matching subscribers (asynchronous).

        Handlers run concurrently via :func:`asyncio.gather`. Each
        async handler is hard-bounded by its effective timeout via
        :func:`asyncio.wait_for` — a slow remote handler can no longer
        block delivery to other subscribers. Sync handlers are
        dispatched on a worker thread via :func:`asyncio.to_thread`,
        also bounded by ``wait_for``, so a blocking sync handler can
        be cancelled without blocking the loop.

        Returns:
            Number of handlers that received the event successfully.
        """
        self._event_count += 1

        targets: list[Subscription] = []
        for sub in list(self._subscriptions.values()):
            if sub.event_filter is not None and not sub.event_filter.matches(event):
                continue
            targets.append(sub)

        if not targets:
            return 0

        results = await asyncio.gather(
            *(self._dispatch_async(sub, event) for sub in targets),
            return_exceptions=False,
        )
        return sum(1 for ok in results if ok)

    async def _dispatch_async(
        self, sub: Subscription, event: SecurityEvent
    ) -> bool:
        timeout_s = self._effective_timeout_ms(sub) / 1000.0
        start = time.monotonic()
        try:
            if inspect.iscoroutinefunction(sub.handler):
                await asyncio.wait_for(sub.handler(event), timeout=timeout_s)
            else:
                # Run sync handler off-thread so a blocking handler
                # cannot stall the loop. wait_for cancels the wrapper
                # if the timeout fires; the underlying thread finishes
                # in the background, but the loop is unblocked.
                await asyncio.wait_for(
                    asyncio.to_thread(sub.handler, event),
                    timeout=timeout_s,
                )
        except asyncio.TimeoutError:
            self._timeout_count += 1
            self._error_count += 1
            logger.warning(
                "Handler '%s' exceeded %.0fms timeout on event %s",
                sub.name,
                timeout_s * 1000.0,
                event.event_type.value,
            )
            return False
        except Exception as exc:
            self._error_count += 1
            logger.error(
                "Handler '%s' failed on event %s: %s",
                sub.name,
                event.event_type.value,
                exc,
            )
            return False
        elapsed_ms = (time.monotonic() - start) * 1000.0
        self._record_slow_handler(sub, event, elapsed_ms)
        return True

    def _record_slow_handler(
        self,
        sub: Subscription,
        event: SecurityEvent,
        elapsed_ms: float,
    ) -> None:
        timeout_ms = self._effective_timeout_ms(sub)
        if elapsed_ms > timeout_ms:
            self._slow_count += 1
            logger.warning(
                "Slow handler '%s' on event %s: %.0fms (timeout %.0fms)",
                sub.name,
                event.event_type.value,
                elapsed_ms,
                timeout_ms,
            )

    @property
    def subscription_count(self) -> int:
        """Number of active subscriptions."""
        return len(self._subscriptions)

    @property
    def event_count(self) -> int:
        """Total number of events emitted."""
        return self._event_count

    @property
    def error_count(self) -> int:
        """Total number of handler errors."""
        return self._error_count

    @property
    def slow_handler_count(self) -> int:
        """Total number of handlers that exceeded their timeout (any path)."""
        return self._slow_count

    @property
    def timeout_count(self) -> int:
        """Total number of async handlers cancelled by timeout in aemit()."""
        return self._timeout_count

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subscriptions.clear()
