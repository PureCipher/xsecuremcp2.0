"""Policy decision audit log.

Records every policy evaluation with its decision, context, and timing.
Provides a queryable history for compliance, debugging, and analytics.

Example::

    from fastmcp.server.security.policy.audit import PolicyAuditLog

    audit = PolicyAuditLog(max_entries=10_000)

    # Wire to a PolicyEngine
    engine = PolicyEngine(providers=[...], audit_log=audit)

    # Or record manually
    audit.record(
        context=PolicyEvaluationContext(...),
        result=PolicyResult(...),
    )

    # Query the log
    recent = audit.query(limit=10)
    denied = audit.query(decision=PolicyDecision.DENY)
    by_actor = audit.query(actor_id="agent-1")
    by_resource = audit.query(resource_id="admin-*")

    # Export for compliance
    entries = audit.export()
"""

from __future__ import annotations

import fnmatch
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastmcp.server.security.policy.provider import (
    Citation,
    PolicyDecision,
    PolicyEvaluationContext,
    PolicyResult,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fastmcp.server.security.provenance.ledger import ProvenanceLedger


@dataclass(frozen=True)
class AuditEntry:
    """A single audit log entry recording a policy decision.

    The core 7-tuple (actor/action/resource/decision/reason/policy_id)
    is canonical — every policy evaluation records these. Capability
    fields (environment/risk/principal_type/resource_type/
    approval_granted/approval_ticket) are populated when the caller
    supplied them on the PolicyEvaluationContext; they default to the
    same safe-deny values the context uses so legacy records don't
    look suspicious.

    Attributes:
        actor_id: Who made the request.
        action: What action was attempted.
        resource_id: The target resource.
        decision: The final ALLOW/DENY/DEFER/REQUIRE_APPROVAL decision.
        reason: Human-readable reason from the policy.
        policy_id: ID of the policy that made the decision.
        constraints: Any constraints attached to an ALLOW.
        metadata: Additional context metadata from the request.
        tags: Tags from the evaluation context.
        timestamp: When the evaluation occurred.
        elapsed_ms: Time taken for the evaluation in milliseconds.
        environment: Environment the request was evaluated in.
        risk: Declared or inferred risk level.
        principal_type: Classification of the caller.
        resource_type: Classification of the resource.
        approval_granted: Whether an approval ticket accompanied the call.
        approval_ticket: Opaque ticket id (only present when approval
            was granted). Never contains secrets.
        citations: Regulation citations attached by compliance
            providers. Tuple so the record is hashable and the order
            (first = primary) is preserved for reports that want the
            citation that blocked the call rather than any ancillary
            ones.
    """

    actor_id: str | None
    action: str
    resource_id: str
    decision: PolicyDecision
    reason: str
    policy_id: str
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: frozenset[str] = field(default_factory=frozenset)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    elapsed_ms: float = 0.0
    environment: str = "production"
    risk: str = "low"
    principal_type: str = "agent"
    resource_type: str = "tool"
    approval_granted: bool = False
    approval_ticket: str | None = None
    citations: tuple[Citation, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Export as a JSON-serializable dict."""
        return {
            "actor_id": self.actor_id,
            "action": self.action,
            "resource_id": self.resource_id,
            "decision": self.decision.value,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "constraints": self.constraints,
            "metadata": self.metadata,
            "tags": sorted(self.tags),
            "timestamp": self.timestamp.isoformat(),
            "elapsed_ms": self.elapsed_ms,
            "environment": self.environment,
            "risk": self.risk,
            "principal_type": self.principal_type,
            "resource_type": self.resource_type,
            "approval_granted": self.approval_granted,
            "approval_ticket": self.approval_ticket,
            "citations": [c.to_dict() for c in self.citations],
        }


class PolicyAuditLog:
    """In-memory audit log for policy decisions.

    Thread-safe bounded log with query, filtering, and export capabilities.
    Execution denials are retained ahead of routine discovery decisions so
    repeated component listing cannot erase evidence of blocked operations.
    When a provenance ledger is attached, those denials are also written to
    its tamper-evident chain and inherit the ledger backend's durability.

    Args:
        max_entries: Maximum number of entries to retain. Routine entries are
            evicted before execution denials. Defaults to 10,000.
        provenance_ledger: Optional ledger that receives actionable denials as
            ``ACCESS_DENIED`` records.

    Example::

        audit = PolicyAuditLog(max_entries=5000)
        audit.record(context, result)
        recent_denials = audit.query(decision=PolicyDecision.DENY, limit=20)
    """

    def __init__(
        self,
        max_entries: int = 10_000,
        *,
        provenance_ledger: ProvenanceLedger | None = None,
    ) -> None:
        if max_entries < 0:
            raise ValueError("max_entries must be non-negative")
        self._entries: deque[AuditEntry] = deque()
        self._max_entries = max_entries
        self._provenance_ledger = provenance_ledger
        self._lock = threading.Lock()
        self._total_recorded: int = 0
        self._total_allowed: int = 0
        self._total_denied: int = 0
        self._dropped_entries: int = 0

    @property
    def size(self) -> int:
        """Number of entries currently in the log."""
        return len(self._entries)

    @property
    def max_entries(self) -> int:
        """Maximum capacity of the log."""
        return self._max_entries

    @property
    def total_recorded(self) -> int:
        """Total entries ever recorded (including evicted ones)."""
        return self._total_recorded

    @property
    def total_allowed(self) -> int:
        """Total ALLOW decisions recorded."""
        return self._total_allowed

    @property
    def total_denied(self) -> int:
        """Total DENY decisions recorded."""
        return self._total_denied

    @property
    def dropped_entries(self) -> int:
        """Routine entries omitted because protected denials filled the log."""
        return self._dropped_entries

    @property
    def provenance_ledger(self) -> ProvenanceLedger | None:
        """Ledger receiving durable denial records, when configured."""
        return self._provenance_ledger

    def attach_provenance_ledger(
        self, provenance_ledger: ProvenanceLedger | None
    ) -> None:
        """Attach or detach the ledger used to persist execution denials."""
        self._provenance_ledger = provenance_ledger

    def record(
        self,
        context: PolicyEvaluationContext,
        result: PolicyResult,
        *,
        elapsed_ms: float = 0.0,
    ) -> AuditEntry:
        """Record a policy decision.

        Args:
            context: The evaluation context.
            result: The policy result.
            elapsed_ms: Optional elapsed time for the evaluation.

        Returns:
            The created AuditEntry.
        """
        # Capability fields are optional on older PolicyEvaluationContext
        # instances built via positional-only signatures. Read defensively
        # so hot-path evaluation can't explode on a surprise shape.
        environment = getattr(context, "environment", "production")
        risk = getattr(context, "risk", "low")
        principal_type = getattr(context, "principal_type", "agent")
        resource_type = getattr(context, "resource_type", "tool")
        approval_granted = bool(getattr(context, "approval_granted", False))
        approval_ticket = getattr(context, "approval_ticket", None)

        # ``citations`` is a tuple on the result; audit entries are
        # hashable dataclasses so we keep it as a tuple here too.
        result_citations = getattr(result, "citations", ()) or ()

        entry = AuditEntry(
            actor_id=context.actor_id,
            action=context.action,
            resource_id=context.resource_id,
            decision=result.decision,
            reason=result.reason,
            policy_id=result.policy_id,
            constraints=list(result.constraints),
            metadata=dict(context.metadata),
            tags=context.tags,
            timestamp=datetime.now(UTC),
            elapsed_ms=elapsed_ms,
            environment=environment,
            risk=risk,
            principal_type=principal_type,
            resource_type=resource_type,
            approval_granted=approval_granted,
            approval_ticket=approval_ticket,
            citations=tuple(result_citations),
        )

        with self._lock:
            self._retain(entry)
            self._total_recorded += 1
            if result.decision == PolicyDecision.ALLOW:
                self._total_allowed += 1
            elif result.decision == PolicyDecision.DENY:
                self._total_denied += 1

        if self._is_actionable_denial(entry):
            self._record_provenance_denial(entry)

        return entry

    @staticmethod
    def _is_actionable_denial(entry: AuditEntry) -> bool:
        """Return whether an entry represents a blocked execution attempt."""
        return entry.decision in {
            PolicyDecision.DENY,
            PolicyDecision.REQUIRE_APPROVAL,
        } and not entry.action.startswith("list_")

    def _retain(self, entry: AuditEntry) -> None:
        """Retain an entry while protecting execution denials from list noise.

        The caller holds ``self._lock``. If the bounded log is full, the
        oldest routine entry is evicted first. A routine entry is discarded
        when every retained slot already contains an actionable denial. Only
        a newer actionable denial may evict the oldest protected denial.
        """
        if self._max_entries == 0:
            self._dropped_entries += 1
            return
        if len(self._entries) < self._max_entries:
            self._entries.append(entry)
            return

        for index, retained in enumerate(self._entries):
            if not self._is_actionable_denial(retained):
                del self._entries[index]
                self._entries.append(entry)
                return

        if self._is_actionable_denial(entry):
            self._entries.popleft()
            self._entries.append(entry)
        else:
            self._dropped_entries += 1

    def _record_provenance_denial(self, entry: AuditEntry) -> None:
        """Append a safe, tamper-evident denial record when a ledger exists."""
        ledger = self._provenance_ledger
        if ledger is None:
            return

        from fastmcp.server.security.provenance.records import ProvenanceAction

        try:
            ledger.record(
                action=ProvenanceAction.ACCESS_DENIED,
                actor_id=entry.actor_id or "anonymous",
                resource_id=entry.resource_id,
                input_data={
                    "action": entry.action,
                    "resource_id": entry.resource_id,
                },
                metadata={
                    "decision": entry.decision.value,
                    "policy_id": entry.policy_id,
                    "reason": entry.reason,
                    "requested_action": entry.action,
                    "constraints": list(entry.constraints),
                    "tags": sorted(entry.tags),
                    "environment": entry.environment,
                    "risk": entry.risk,
                    "principal_type": entry.principal_type,
                    "resource_type": entry.resource_type,
                },
            )
        except Exception:
            # Audit persistence must not replace the policy result or turn a
            # deterministic denial into a server error.
            logger.exception(
                "Failed to persist policy denial for %s to provenance",
                entry.resource_id,
            )

    def query(
        self,
        *,
        actor_id: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        decision: PolicyDecision | None = None,
        policy_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[AuditEntry]:
        """Query the audit log with optional filters.

        All filters are ANDed together. String filters on ``resource_id``
        support glob patterns (e.g., ``"admin-*"``).

        Args:
            actor_id: Filter by actor ID (exact match).
            resource_id: Filter by resource ID (exact or glob pattern).
            action: Filter by action (exact match).
            decision: Filter by decision type.
            policy_id: Filter by policy ID (exact match).
            since: Only entries after this timestamp.
            until: Only entries before this timestamp.
            limit: Maximum number of results (most recent first).

        Returns:
            Matching entries, ordered most-recent-first.
        """
        with self._lock:
            entries = list(self._entries)

        # Apply filters
        result = []
        for entry in reversed(entries):  # Most recent first
            if actor_id is not None and entry.actor_id != actor_id:
                continue
            if resource_id is not None:
                if not (
                    entry.resource_id == resource_id
                    or fnmatch.fnmatchcase(entry.resource_id, resource_id)
                ):
                    continue
            if action is not None and entry.action != action:
                continue
            if decision is not None and entry.decision != decision:
                continue
            if policy_id is not None and entry.policy_id != policy_id:
                continue
            if since is not None and entry.timestamp < since:
                continue
            if until is not None and entry.timestamp > until:
                continue

            result.append(entry)
            if limit is not None and len(result) >= limit:
                break

        return result

    def clear(self) -> int:
        """Clear all entries from the log.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def export(self) -> list[dict[str, Any]]:
        """Export all entries as JSON-serializable dicts.

        Returns:
            List of entry dicts, ordered oldest-first.
        """
        with self._lock:
            return [entry.to_dict() for entry in self._entries]

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics about the audit log.

        Returns:
            Dict with counts, rates, and summary info.
        """
        with self._lock:
            entries = list(self._entries)

        # Count by decision
        allow_count = sum(1 for e in entries if e.decision == PolicyDecision.ALLOW)
        deny_count = sum(1 for e in entries if e.decision == PolicyDecision.DENY)
        defer_count = sum(1 for e in entries if e.decision == PolicyDecision.DEFER)

        # Unique actors and resources
        actors = {e.actor_id for e in entries if e.actor_id}
        resources = {e.resource_id for e in entries}

        # Top denied resources
        deny_entries = [e for e in entries if e.decision == PolicyDecision.DENY]
        resource_deny_counts: dict[str, int] = {}
        for e in deny_entries:
            resource_deny_counts[e.resource_id] = (
                resource_deny_counts.get(e.resource_id, 0) + 1
            )
        top_denied = sorted(
            resource_deny_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "entries_in_log": len(entries),
            "max_entries": self._max_entries,
            "total_recorded": self._total_recorded,
            "total_allowed": self._total_allowed,
            "total_denied": self._total_denied,
            "dropped_entries": self._dropped_entries,
            "current_allow": allow_count,
            "current_deny": deny_count,
            "current_defer": defer_count,
            "unique_actors": len(actors),
            "unique_resources": len(resources),
            "top_denied_resources": [
                {"resource_id": r, "count": c} for r, c in top_denied
            ],
            "deny_rate": (deny_count / len(entries) if entries else 0.0),
        }
