"""Rate limiting policy.

Enforces per-actor request limits using a sliding time window.

Example::

    policy = RateLimitPolicy(
        max_requests=100,
        window_seconds=3600,  # 100 requests per hour
    )
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fastmcp.server.security.policy.provider import (
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

logger = logging.getLogger(__name__)


@dataclass
class RateLimitPolicy:
    """Sliding window rate limiter per actor.

    Attributes:
        max_requests: Maximum requests allowed within the window.
        window_seconds: Size of the sliding window in seconds.
        policy_id: Unique identifier for this policy instance.
        version: Version string.
    """

    max_requests: int = 100
    window_seconds: int = 3600
    policy_id: str = "rate-limit-policy"
    version: str = "1.0.0"
    _request_log: dict[str, list[datetime]] = field(
        default_factory=lambda: defaultdict(list),
        repr=False,
    )

    def _prune(self, actor_id: str, now: datetime) -> None:
        """Remove expired entries from the actor's request log."""
        cutoff = now - timedelta(seconds=self.window_seconds)
        log = self._request_log[actor_id]
        # Binary-style prune: remove all entries before cutoff
        self._request_log[actor_id] = [ts for ts in log if ts > cutoff]

    async def evaluate(self, context: PolicyEvaluationContext) -> PolicyResult:
        """Check if actor has exceeded their rate limit."""
        actor_id = context.actor_id or "__anonymous__"
        now = context.timestamp

        self._prune(actor_id, now)

        current_count = len(self._request_log[actor_id])

        if current_count >= self.max_requests:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=(
                    f"Rate limit exceeded: {current_count}/{self.max_requests} "
                    f"requests in {self.window_seconds}s window"
                ),
                policy_id=self.policy_id,
            )

        # Record this request
        self._request_log[actor_id].append(now)

        remaining = self.max_requests - current_count - 1
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"Rate limit OK: {remaining} requests remaining",
            policy_id=self.policy_id,
            constraints=[f"rate_limit:{remaining}_remaining"],
        )

    def get_remaining(self, actor_id: str) -> int:
        """Get remaining requests for an actor in the current window."""
        now = datetime.now(timezone.utc)
        self._prune(actor_id, now)
        return max(0, self.max_requests - len(self._request_log[actor_id]))

    def reset(self, actor_id: str | None = None) -> None:
        """Reset rate limit counters.

        Args:
            actor_id: Reset for a specific actor. If None, reset all.
        """
        if actor_id is not None:
            self._request_log.pop(actor_id, None)
        else:
            self._request_log.clear()

    async def get_policy_id(self) -> str:
        return self.policy_id

    async def get_policy_version(self) -> str:
        return self.version
