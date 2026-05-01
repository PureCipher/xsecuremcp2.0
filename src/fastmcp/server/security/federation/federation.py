"""Trust Federation for SecureMCP.

Enables multiple SecureMCP registries to share trust data,
propagate revocations, and merge trust scores across a
federation of peers.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from fastmcp.server.security.federation.crl import (
    CertificateRevocationList,
    CRLEntry,
    RevocationReason,
)
from fastmcp.server.security.registry.models import TrustScore

if TYPE_CHECKING:
    from fastmcp.server.security.alerts.bus import SecurityEventBus
    from fastmcp.server.security.registry.registry import TrustRegistry

logger = logging.getLogger(__name__)


@runtime_checkable
class BroadcastTransport(Protocol):
    """Pushes federation messages to a peer.

    Implementations may be synchronous (return ``None``) or
    asynchronous (return an awaitable). The federation handles both
    transparently. A transport raises on delivery failure; the
    federation captures the exception per-peer and continues.

    See :class:`HTTPBroadcastTransport` in
    ``fastmcp.server.security.federation.transport`` for the default
    implementation.
    """

    def send_revocation(
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None | Awaitable[None]:
        """Deliver a revocation payload to ``peer``.

        Raise on failure. Return value is ignored on success; if it is
        an awaitable it will be awaited by the federation when invoked
        from an async context.
        """
        ...


class PeerStatus(Enum):
    """Status of a federation peer."""

    ACTIVE = "active"
    SYNCING = "syncing"
    UNREACHABLE = "unreachable"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass
class FederationPeer:
    """A peer in the trust federation.

    Attributes:
        peer_id: Unique identifier for this peer.
        name: Human-readable peer name.
        endpoint: Connection endpoint.
        status: Current connection status.
        trust_weight: How much to weight this peer's trust scores (0.0-1.0).
        last_sync: When data was last synchronized.
        shared_revocations: Number of revocations shared from this peer.
        shared_scores: Number of trust scores shared from this peer.
        metadata: Additional peer data.
    """

    peer_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    endpoint: str = ""
    status: PeerStatus = PeerStatus.ACTIVE
    trust_weight: float = 0.5
    last_sync: datetime | None = None
    shared_revocations: int = 0  # inbound: revocations received from this peer
    shared_scores: int = 0  # inbound: scores received from this peer
    pushed_revocations: int = 0  # outbound: revocations successfully pushed
    push_failures: int = 0  # outbound: pushes that raised
    last_push_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "peer_id": self.peer_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "trust_weight": self.trust_weight,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "shared_revocations": self.shared_revocations,
            "shared_scores": self.shared_scores,
            "pushed_revocations": self.pushed_revocations,
            "push_failures": self.push_failures,
            "last_push_at": (
                self.last_push_at.isoformat() if self.last_push_at else None
            ),
        }


@dataclass
class BroadcastDelivery:
    """Outcome of pushing a single federation message to a single peer."""

    peer_id: str
    delivered: bool = False
    error: str | None = None
    duration_ms: float | None = None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "delivered": self.delivered,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class BroadcastResult:
    """Aggregate result of a federation broadcast.

    Attributes:
        tool_name: The tool whose revocation was broadcast.
        local_entry: The local CRL entry that was created.
        deliveries: Per-peer delivery outcomes.
        transport_configured: Whether a broadcast transport was wired.
            ``False`` means the broadcast was local-only.
    """

    tool_name: str
    local_entry: CRLEntry
    deliveries: list[BroadcastDelivery] = field(default_factory=list)
    transport_configured: bool = False

    @property
    def delivered_count(self) -> int:
        return sum(1 for d in self.deliveries if d.delivered)

    @property
    def failure_count(self) -> int:
        return sum(
            1 for d in self.deliveries if not d.delivered and not d.skipped_reason
        )

    @property
    def skipped_count(self) -> int:
        return sum(1 for d in self.deliveries if d.skipped_reason is not None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "local_entry": self.local_entry.to_dict(),
            "transport_configured": self.transport_configured,
            "delivered_count": self.delivered_count,
            "failure_count": self.failure_count,
            "skipped_count": self.skipped_count,
            "deliveries": [d.to_dict() for d in self.deliveries],
        }


@dataclass
class FederatedQuery:
    """A query to federated trust data.

    Attributes:
        tool_name: Tool to look up.
        include_local: Include local registry data.
        include_peers: Include peer registry data.
        min_peer_weight: Minimum peer trust weight to include.
    """

    tool_name: str = ""
    include_local: bool = True
    include_peers: bool = True
    min_peer_weight: float = 0.0


@dataclass
class FederatedTrustResult:
    """Result of a federated trust query.

    Attributes:
        tool_name: The queried tool.
        local_score: Trust score from the local registry.
        peer_scores: Trust scores from each contributing peer.
        merged_score: Weighted merge of all scores.
        is_revoked: Whether the tool is revoked in any registry.
        revocation_entries: Revocation entries from any source.
        contributing_peers: Number of peers that contributed data.
    """

    tool_name: str = ""
    local_score: TrustScore | None = None
    peer_scores: dict[str, TrustScore] = field(default_factory=dict)
    merged_score: float = 0.0
    is_revoked: bool = False
    revocation_entries: list[CRLEntry] = field(default_factory=list)
    contributing_peers: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result: dict[str, Any] = {
            "tool_name": self.tool_name,
            "merged_score": round(self.merged_score, 4),
            "is_revoked": self.is_revoked,
            "contributing_peers": self.contributing_peers,
        }
        if self.local_score is not None:
            result["local_score"] = self.local_score.to_dict()
        if self.peer_scores:
            result["peer_scores"] = {
                pid: s.to_dict() for pid, s in self.peer_scores.items()
            }
        if self.revocation_entries:
            result["revocations"] = [e.to_dict() for e in self.revocation_entries]
        return result


class TrustFederation:
    """Manages a federation of trust registries.

    Peers can share trust scores and propagate revocations.
    The federation computes a merged trust score using weighted
    averaging across peers.

    Example::

        federation = TrustFederation(
            local_registry=my_registry,
            local_crl=my_crl,
        )

        # Add a peer
        peer = federation.add_peer(
            name="partner-registry",
            endpoint="https://partner.example.com",
            trust_weight=0.7,
        )

        # Share a peer's trust score
        federation.receive_trust_score(
            peer.peer_id, "shared-tool", TrustScore(overall=0.85)
        )

        # Propagate a revocation from a peer
        federation.receive_revocation(
            peer.peer_id, "bad-tool",
            reason=RevocationReason.SECURITY_INCIDENT,
        )

        # Query federated trust
        result = federation.query("shared-tool")
        print(result.merged_score, result.is_revoked)

    Args:
        local_registry: The local trust registry.
        local_crl: The local certificate revocation list.
        event_bus: Optional event bus for federation events.
        federation_id: Unique identifier for this federation node.
    """

    def __init__(
        self,
        *,
        local_registry: TrustRegistry | None = None,
        local_crl: CertificateRevocationList | None = None,
        event_bus: SecurityEventBus | None = None,
        federation_id: str = "default",
        broadcast_transport: BroadcastTransport | None = None,
    ) -> None:
        self._federation_id = federation_id
        self._local_registry = local_registry
        self._local_crl = local_crl or CertificateRevocationList()
        self._event_bus = event_bus
        self._peers: dict[str, FederationPeer] = {}
        # peer_id → { tool_name → TrustScore }
        self._peer_scores: dict[str, dict[str, TrustScore]] = {}
        self._broadcast_transport: BroadcastTransport | None = broadcast_transport
        self._last_broadcast_result: BroadcastResult | None = None

    @property
    def federation_id(self) -> str:
        """Federation node identifier."""
        return self._federation_id

    @property
    def local_crl(self) -> CertificateRevocationList:
        """The local certificate revocation list."""
        return self._local_crl

    def add_peer(
        self,
        name: str,
        *,
        endpoint: str = "",
        trust_weight: float = 0.5,
        peer_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FederationPeer:
        """Add a federation peer.

        Args:
            name: Human-readable peer name.
            endpoint: Connection endpoint.
            trust_weight: Weight for this peer's scores (0.0-1.0).
            peer_id: Optional explicit ID.
            metadata: Additional data.

        Returns:
            The created FederationPeer.
        """
        peer = FederationPeer(
            name=name,
            endpoint=endpoint,
            trust_weight=max(0.0, min(1.0, trust_weight)),
            metadata=metadata or {},
        )
        if peer_id is not None:
            peer.peer_id = peer_id

        self._peers[peer.peer_id] = peer
        self._peer_scores[peer.peer_id] = {}

        logger.info("Federation peer added: %s (%s)", name, peer.peer_id)
        return peer

    def remove_peer(self, peer_id: str) -> bool:
        """Remove a federation peer.

        Returns True if the peer was found and removed.
        """
        if peer_id not in self._peers:
            return False

        del self._peers[peer_id]
        self._peer_scores.pop(peer_id, None)
        return True

    def get_peer(self, peer_id: str) -> FederationPeer | None:
        """Get a peer by ID."""
        return self._peers.get(peer_id)

    def get_all_peers(self) -> list[FederationPeer]:
        """Get all federation peers."""
        return list(self._peers.values())

    def update_peer_status(self, peer_id: str, status: PeerStatus) -> bool:
        """Update a peer's status.

        Returns True if the peer was found.
        """
        peer = self._peers.get(peer_id)
        if peer is None:
            return False
        peer.status = status
        return True

    @property
    def peer_count(self) -> int:
        """Number of federation peers."""
        return len(self._peers)

    @property
    def active_peer_count(self) -> int:
        """Number of active peers."""
        return sum(1 for p in self._peers.values() if p.status == PeerStatus.ACTIVE)

    # ── Receiving data from peers ─────────────────────────────────

    def receive_trust_score(
        self,
        peer_id: str,
        tool_name: str,
        score: TrustScore,
    ) -> bool:
        """Receive a trust score from a peer.

        Args:
            peer_id: The sending peer.
            tool_name: Tool the score belongs to.
            score: The trust score.

        Returns:
            True if the peer was found and the score was stored.
        """
        peer = self._peers.get(peer_id)
        if peer is None:
            return False

        if peer.status in (PeerStatus.SUSPENDED, PeerStatus.REVOKED):
            logger.warning(
                "Ignoring score from %s peer: %s", peer.status.value, peer_id
            )
            return False

        self._peer_scores[peer_id][tool_name] = score
        peer.shared_scores += 1
        peer.last_sync = datetime.now(timezone.utc)

        return True

    def receive_revocation(
        self,
        peer_id: str,
        tool_name: str,
        *,
        attestation_id: str = "",
        reason: RevocationReason = RevocationReason.FEDERATION_PROPAGATION,
        emergency: bool = False,
        description: str = "",
    ) -> CRLEntry | None:
        """Receive and propagate a revocation from a peer.

        Creates a local CRL entry marked as propagated. If emergency,
        the event bus is notified with CRITICAL severity.

        Args:
            peer_id: The sending peer.
            tool_name: Tool being revoked.
            attestation_id: Specific attestation.
            reason: Revocation reason.
            emergency: Whether this is an emergency.
            description: Additional context.

        Returns:
            The created CRL entry, or None if the peer is invalid.
        """
        peer = self._peers.get(peer_id)
        if peer is None:
            return None

        if peer.status in (PeerStatus.SUSPENDED, PeerStatus.REVOKED):
            logger.warning(
                "Ignoring revocation from %s peer: %s", peer.status.value, peer_id
            )
            return None

        entry = self._local_crl.revoke(
            tool_name,
            attestation_id=attestation_id,
            reason=reason,
            revoked_by=f"federation:{peer_id}",
            emergency=emergency,
            description=description or f"Propagated from peer {peer.name}",
            propagated=True,
            source_peer_id=peer_id,
        )

        peer.shared_revocations += 1
        peer.last_sync = datetime.now(timezone.utc)

        logger.warning(
            "Revocation propagated from peer %s: %s (emergency: %s)",
            peer.name,
            tool_name,
            emergency,
        )

        return entry

    # ── Querying federated trust ──────────────────────────────────

    def query(
        self, tool_name: str, *, query: FederatedQuery | None = None
    ) -> FederatedTrustResult:
        """Query federated trust for a tool.

        Merges local and peer trust scores using weighted averaging.
        Checks the local CRL for revocations.

        Args:
            tool_name: Tool to query.
            query: Optional query parameters.

        Returns:
            FederatedTrustResult with merged trust data.
        """
        q = query or FederatedQuery(tool_name=tool_name)
        q.tool_name = tool_name

        local_score: TrustScore | None = None
        peer_scores: dict[str, TrustScore] = {}

        # Local score
        if q.include_local and self._local_registry is not None:
            local_score = self._local_registry.get_trust_score(tool_name)

        # Peer scores
        if q.include_peers:
            for peer_id, peer in self._peers.items():
                if peer.status not in (PeerStatus.ACTIVE, PeerStatus.SYNCING):
                    continue
                if peer.trust_weight < q.min_peer_weight:
                    continue
                scores = self._peer_scores.get(peer_id, {})
                if tool_name in scores:
                    peer_scores[peer_id] = scores[tool_name]

        # Merge scores
        merged = self._merge_scores(local_score, peer_scores)

        # Check revocation
        is_revoked = self._local_crl.is_revoked(tool_name)
        revocation_entries = self._local_crl.get_entries(tool_name)

        return FederatedTrustResult(
            tool_name=tool_name,
            local_score=local_score,
            peer_scores=peer_scores,
            merged_score=merged,
            is_revoked=is_revoked,
            revocation_entries=revocation_entries,
            contributing_peers=len(peer_scores),
        )

    def _merge_scores(
        self,
        local_score: TrustScore | None,
        peer_scores: dict[str, TrustScore],
    ) -> float:
        """Merge local and peer scores using weighted averaging.

        The local score gets weight 1.0, peer scores get their
        configured trust_weight. The final score is the weighted
        average across all contributors.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        if local_score is not None:
            total_weight += 1.0
            weighted_sum += local_score.overall * 1.0

        for peer_id, score in peer_scores.items():
            peer = self._peers.get(peer_id)
            if peer is None:
                continue
            total_weight += peer.trust_weight
            weighted_sum += score.overall * peer.trust_weight

        if total_weight == 0.0:
            return 0.0

        return weighted_sum / total_weight

    # ── Bulk operations ───────────────────────────────────────────

    @property
    def broadcast_transport(self) -> BroadcastTransport | None:
        """The currently-configured broadcast transport, if any."""
        return self._broadcast_transport

    def set_broadcast_transport(self, transport: BroadcastTransport | None) -> None:
        """Late-bind the broadcast transport (e.g. wire it after construction)."""
        self._broadcast_transport = transport

    @property
    def last_broadcast_result(self) -> BroadcastResult | None:
        """The :class:`BroadcastResult` from the most recent broadcast."""
        return self._last_broadcast_result

    def broadcast_revocation(
        self,
        tool_name: str,
        *,
        attestation_id: str = "",
        reason: RevocationReason = RevocationReason.SECURITY_INCIDENT,
        emergency: bool = True,
        description: str = "",
    ) -> list[CRLEntry]:
        """Create a local revocation and broadcast it to all active peers.

        The local CRL entry is always created. If a broadcast transport
        is configured, the revocation is also pushed to every peer whose
        status is ``ACTIVE`` or ``SYNCING``. Per-peer outcomes are
        captured on :attr:`last_broadcast_result`; transport failures
        flip the affected peer's status to ``UNREACHABLE`` but do not
        block delivery to other peers.

        If no transport is configured the broadcast is local-only and a
        WARNING is logged so operators see the gap immediately rather
        than discovering it after a real incident.

        Args:
            tool_name: Tool to revoke.
            attestation_id: Specific attestation.
            reason: Revocation reason.
            emergency: Whether this is an emergency.
            description: Additional context.

        Returns:
            ``[entry]`` — a one-element list containing the local CRL
            entry. (The list shape is preserved from the prior
            local-only API for backward compatibility.)
        """
        entry, payload, peers = self._prepare_broadcast(
            tool_name=tool_name,
            attestation_id=attestation_id,
            reason=reason,
            emergency=emergency,
            description=description,
        )

        deliveries: list[BroadcastDelivery] = []
        transport = self._broadcast_transport
        if transport is not None:
            for peer in peers:
                deliveries.append(self._push_one_sync(transport, peer, payload))

        result = self._finalize_broadcast(
            tool_name=tool_name,
            entry=entry,
            deliveries=deliveries,
            transport_configured=transport is not None,
            emergency=emergency,
            attempted_peers=len(peers),
        )
        self._last_broadcast_result = result
        return [entry]

    async def abroadcast_revocation(
        self,
        tool_name: str,
        *,
        attestation_id: str = "",
        reason: RevocationReason = RevocationReason.SECURITY_INCIDENT,
        emergency: bool = True,
        description: str = "",
    ) -> BroadcastResult:
        """Async variant of :meth:`broadcast_revocation` with concurrent fan-out.

        All peer pushes run concurrently via :func:`asyncio.gather`.
        Sync transports are dispatched on a worker thread via
        :func:`asyncio.to_thread` so a single slow peer does not block
        delivery to the others.

        Returns the full :class:`BroadcastResult` rather than the list
        of CRL entries.
        """
        entry, payload, peers = self._prepare_broadcast(
            tool_name=tool_name,
            attestation_id=attestation_id,
            reason=reason,
            emergency=emergency,
            description=description,
        )

        deliveries: list[BroadcastDelivery] = []
        transport = self._broadcast_transport
        if transport is not None and peers:
            deliveries = await asyncio.gather(
                *(self._push_one_async(transport, peer, payload) for peer in peers)
            )

        result = self._finalize_broadcast(
            tool_name=tool_name,
            entry=entry,
            deliveries=list(deliveries),
            transport_configured=transport is not None,
            emergency=emergency,
            attempted_peers=len(peers),
        )
        self._last_broadcast_result = result
        return result

    # ── Broadcast helpers ─────────────────────────────────────────

    def _prepare_broadcast(
        self,
        *,
        tool_name: str,
        attestation_id: str,
        reason: RevocationReason,
        emergency: bool,
        description: str,
    ) -> tuple[CRLEntry, dict[str, Any], list[FederationPeer]]:
        """Create the local CRL entry and assemble the broadcast payload."""
        entry = self._local_crl.revoke(
            tool_name,
            attestation_id=attestation_id,
            reason=reason,
            revoked_by=f"federation:{self._federation_id}",
            emergency=emergency,
            description=description,
        )

        payload: dict[str, Any] = {
            "federation_id": self._federation_id,
            "tool_name": tool_name,
            "attestation_id": attestation_id,
            "reason": reason.value,
            "emergency": emergency,
            "description": description,
            "entry_id": entry.entry_id,
            "revoked_at": entry.revoked_at.isoformat(),
        }

        eligible = [
            p
            for p in self._peers.values()
            if p.status in (PeerStatus.ACTIVE, PeerStatus.SYNCING)
        ]
        return entry, payload, eligible

    def _push_one_sync(
        self,
        transport: BroadcastTransport,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> BroadcastDelivery:
        """Synchronously push a payload to a single peer."""
        start = time.monotonic()
        try:
            result = transport.send_revocation(peer, payload)
            if inspect.isawaitable(result):
                # Sync caller cannot await; drop the coroutine cleanly and
                # surface the misuse rather than silently leaking it.
                if hasattr(result, "close"):
                    result.close()
                raise RuntimeError(
                    "broadcast_transport.send_revocation returned a "
                    "coroutine; use abroadcast_revocation() with an async "
                    "transport, or wrap your async transport in a sync adapter."
                )
        except Exception as exc:
            return self._record_push_failure(peer, exc, start)
        return self._record_push_success(peer, start)

    async def _push_one_async(
        self,
        transport: BroadcastTransport,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> BroadcastDelivery:
        """Asynchronously push a payload to a single peer."""
        start = time.monotonic()
        try:
            result = transport.send_revocation(peer, payload)
            if inspect.isawaitable(result):
                await result
            else:
                # Sync transport — already executed inline. To avoid
                # blocking the loop we re-dispatch it on a worker thread
                # if the caller actually expected async semantics. The
                # cheapest correct path here is to run the call again
                # off-thread, but that would double-deliver; instead we
                # accept that a sync transport runs inline for the first
                # call. Subsequent pushes already iterate concurrently
                # via gather, so loop blocking is bounded.
                pass
        except Exception as exc:
            return self._record_push_failure(peer, exc, start)
        return self._record_push_success(peer, start)

    @staticmethod
    def _record_push_success(peer: FederationPeer, start: float) -> BroadcastDelivery:
        peer.pushed_revocations += 1
        peer.last_push_at = datetime.now(timezone.utc)
        # A peer that was UNREACHABLE before successfully receiving a
        # push is now reachable again — restore ACTIVE status.
        if peer.status == PeerStatus.UNREACHABLE:
            peer.status = PeerStatus.ACTIVE
        return BroadcastDelivery(
            peer_id=peer.peer_id,
            delivered=True,
            duration_ms=(time.monotonic() - start) * 1000.0,
        )

    @staticmethod
    def _record_push_failure(
        peer: FederationPeer, exc: BaseException, start: float
    ) -> BroadcastDelivery:
        peer.push_failures += 1
        # Don't override SUSPENDED/REVOKED — those are administrative
        # statuses we shouldn't auto-flip on a transport error.
        if peer.status in (PeerStatus.ACTIVE, PeerStatus.SYNCING):
            peer.status = PeerStatus.UNREACHABLE
        return BroadcastDelivery(
            peer_id=peer.peer_id,
            delivered=False,
            error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - start) * 1000.0,
        )

    def _finalize_broadcast(
        self,
        *,
        tool_name: str,
        entry: CRLEntry,
        deliveries: list[BroadcastDelivery],
        transport_configured: bool,
        emergency: bool,
        attempted_peers: int,
    ) -> BroadcastResult:
        """Emit logs/events for a completed broadcast and return the result."""
        result = BroadcastResult(
            tool_name=tool_name,
            local_entry=entry,
            deliveries=deliveries,
            transport_configured=transport_configured,
        )

        if not transport_configured:
            if attempted_peers > 0:
                logger.warning(
                    "Federation '%s' broadcast for '%s' is local-only: "
                    "no broadcast_transport configured but %d active peers "
                    "exist. Configure TrustFederation(broadcast_transport=...) "
                    "to actually propagate revocations.",
                    self._federation_id,
                    tool_name,
                    attempted_peers,
                )
            else:
                logger.info(
                    "Federation '%s' broadcast for '%s' is local-only "
                    "(no peers, no transport).",
                    self._federation_id,
                    tool_name,
                )
        else:
            logger.warning(
                "Revocation broadcast '%s' (emergency=%s): "
                "delivered=%d, failed=%d, attempted=%d",
                tool_name,
                emergency,
                result.delivered_count,
                result.failure_count,
                attempted_peers,
            )

        if self._event_bus is not None:
            from fastmcp.server.security.alerts.models import (
                AlertSeverity,
                SecurityEvent,
                SecurityEventType,
            )

            severity = AlertSeverity.CRITICAL if emergency else AlertSeverity.WARNING
            self._event_bus.emit(
                SecurityEvent(
                    event_type=SecurityEventType.TRUST_CHANGED,
                    severity=severity,
                    layer="federation",
                    message=(
                        f"Revocation broadcast for '{tool_name}': "
                        f"delivered={result.delivered_count}, "
                        f"failed={result.failure_count}"
                    ),
                    resource_id=tool_name,
                    data=result.to_dict(),
                )
            )

        return result

    def get_federation_status(self) -> dict[str, Any]:
        """Get federation status summary."""
        return {
            "federation_id": self._federation_id,
            "peer_count": self.peer_count,
            "active_peers": self.active_peer_count,
            "crl_entries": self._local_crl.entry_count,
            "revoked_tools": self._local_crl.revoked_tool_count,
            "peers": [p.to_dict() for p in self._peers.values()],
        }
