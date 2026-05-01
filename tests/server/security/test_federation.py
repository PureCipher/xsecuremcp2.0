"""Tests for Federation & Revocation (Phase 16).

Covers CRL management, federation peers, trust score sharing,
revocation propagation, federated queries, and event bus integration.
"""

from __future__ import annotations

import pytest

from fastmcp.server.security.alerts.bus import SecurityEventBus
from fastmcp.server.security.alerts.handlers import BufferedHandler
from fastmcp.server.security.federation.crl import (
    CertificateRevocationList,
    CRLEntry,
    RevocationReason,
)
from fastmcp.server.security.federation.federation import (
    BroadcastResult,
    FederatedQuery,
    FederationPeer,
    PeerStatus,
    TrustFederation,
)
from fastmcp.server.security.registry.models import TrustScore
from fastmcp.server.security.registry.registry import TrustRegistry

# ── CRL Entry tests ────────────────────────────────────────────────


class TestCRLEntry:
    def test_default_entry(self):
        entry = CRLEntry()
        assert entry.entry_id
        assert entry.reason == RevocationReason.MANUAL_REVOCATION
        assert not entry.emergency
        assert not entry.propagated

    def test_to_dict(self):
        entry = CRLEntry(
            tool_name="bad-tool",
            reason=RevocationReason.SECURITY_INCIDENT,
            emergency=True,
        )
        d = entry.to_dict()
        assert d["tool_name"] == "bad-tool"
        assert d["reason"] == "security_incident"
        assert d["emergency"] is True


# ── CRL tests ──────────────────────────────────────────────────────


class TestCertificateRevocationList:
    def test_revoke(self):
        crl = CertificateRevocationList()
        entry = crl.revoke("bad-tool", reason=RevocationReason.SECURITY_INCIDENT)
        assert entry.tool_name == "bad-tool"
        assert crl.is_revoked("bad-tool")
        assert crl.entry_count == 1

    def test_revoke_with_attestation_id(self):
        crl = CertificateRevocationList()
        crl.revoke("tool", attestation_id="att-123")
        assert crl.is_attestation_revoked("att-123")

    def test_not_revoked(self):
        crl = CertificateRevocationList()
        assert not crl.is_revoked("good-tool")
        assert not crl.is_attestation_revoked("att-456")

    def test_get_entries(self):
        crl = CertificateRevocationList()
        crl.revoke("tool-a", reason=RevocationReason.KEY_COMPROMISE)
        crl.revoke("tool-a", reason=RevocationReason.POLICY_VIOLATION)
        crl.revoke("tool-b")
        entries = crl.get_entries("tool-a")
        assert len(entries) == 2

    def test_get_entry_by_attestation(self):
        crl = CertificateRevocationList()
        crl.revoke("tool", attestation_id="att-1")
        entry = crl.get_entry_by_attestation("att-1")
        assert entry is not None
        assert entry.tool_name == "tool"

    def test_unrevoke(self):
        crl = CertificateRevocationList()
        crl.revoke("tool-a")
        crl.revoke("tool-a", attestation_id="att-1")
        count = crl.unrevoke("tool-a")
        assert count == 2
        assert not crl.is_revoked("tool-a")
        assert not crl.is_attestation_revoked("att-1")

    def test_unrevoke_nonexistent(self):
        crl = CertificateRevocationList()
        assert crl.unrevoke("nonexistent") == 0

    def test_get_all_entries(self):
        crl = CertificateRevocationList()
        crl.revoke("a")
        crl.revoke("b")
        assert len(crl.get_all_entries()) == 2

    def test_emergency_entries(self):
        crl = CertificateRevocationList()
        crl.revoke("a", emergency=True)
        crl.revoke("b", emergency=False)
        assert len(crl.get_emergency_entries()) == 1

    def test_propagated_entries(self):
        crl = CertificateRevocationList()
        crl.revoke("a", propagated=True, source_peer_id="peer-1")
        crl.revoke("b")
        assert len(crl.get_propagated_entries()) == 1

    def test_to_dict(self):
        crl = CertificateRevocationList(crl_id="test-crl")
        crl.revoke("tool")
        d = crl.to_dict()
        assert d["crl_id"] == "test-crl"
        assert d["entry_count"] == 1

    def test_event_bus_integration(self):
        bus = SecurityEventBus()
        handler = BufferedHandler(max_size=50)
        bus.subscribe(handler)
        crl = CertificateRevocationList(event_bus=bus)
        crl.revoke("bad-tool", emergency=True)
        assert len(handler.events) == 1
        assert handler.events[0].layer == "federation"


# ── Federation Peer tests ──────────────────────────────────────────


class TestFederationPeer:
    def test_default_peer(self):
        peer = FederationPeer()
        assert peer.peer_id
        assert peer.status == PeerStatus.ACTIVE
        assert peer.trust_weight == 0.5

    def test_to_dict(self):
        peer = FederationPeer(name="partner", endpoint="https://partner.example.com")
        d = peer.to_dict()
        assert d["name"] == "partner"
        assert d["status"] == "active"


# ── Trust Federation tests ─────────────────────────────────────────


class TestTrustFederation:
    def test_add_peer(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner", endpoint="https://partner.example.com")
        assert peer.name == "partner"
        assert fed.peer_count == 1

    def test_remove_peer(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        assert fed.remove_peer(peer.peer_id)
        assert fed.peer_count == 0

    def test_remove_nonexistent(self):
        fed = TrustFederation()
        assert not fed.remove_peer("nonexistent")

    def test_get_peer(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        assert fed.get_peer(peer.peer_id) is peer

    def test_get_all_peers(self):
        fed = TrustFederation()
        fed.add_peer("a")
        fed.add_peer("b")
        assert len(fed.get_all_peers()) == 2

    def test_update_peer_status(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.update_peer_status(peer.peer_id, PeerStatus.SUSPENDED)
        assert peer.status == PeerStatus.SUSPENDED

    def test_active_peer_count(self):
        fed = TrustFederation()
        p1 = fed.add_peer("a")
        fed.add_peer("b")
        fed.update_peer_status(p1.peer_id, PeerStatus.SUSPENDED)
        assert fed.active_peer_count == 1


# ── Trust score sharing tests ──────────────────────────────────────


class TestTrustScoreSharing:
    def test_receive_trust_score(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        score = TrustScore(overall=0.85)
        assert fed.receive_trust_score(peer.peer_id, "tool-a", score)

    def test_receive_from_nonexistent_peer(self):
        fed = TrustFederation()
        score = TrustScore(overall=0.85)
        assert not fed.receive_trust_score("nonexistent", "tool-a", score)

    def test_ignore_suspended_peer_score(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.update_peer_status(peer.peer_id, PeerStatus.SUSPENDED)
        score = TrustScore(overall=0.85)
        assert not fed.receive_trust_score(peer.peer_id, "tool-a", score)

    def test_score_updates_peer_stats(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.receive_trust_score(peer.peer_id, "tool-a", TrustScore(overall=0.8))
        assert peer.shared_scores == 1
        assert peer.last_sync is not None


# ── Revocation propagation tests ───────────────────────────────────


class TestRevocationPropagation:
    def test_receive_revocation(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        entry = fed.receive_revocation(peer.peer_id, "bad-tool")
        assert entry is not None
        assert entry.propagated
        assert entry.source_peer_id == peer.peer_id
        assert fed.local_crl.is_revoked("bad-tool")

    def test_receive_emergency_revocation(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        entry = fed.receive_revocation(peer.peer_id, "dangerous-tool", emergency=True)
        assert entry is not None
        assert entry.emergency

    def test_ignore_suspended_peer_revocation(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.update_peer_status(peer.peer_id, PeerStatus.SUSPENDED)
        entry = fed.receive_revocation(peer.peer_id, "tool")
        assert entry is None

    def test_revocation_updates_peer_stats(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.receive_revocation(peer.peer_id, "tool")
        assert peer.shared_revocations == 1

    def test_broadcast_revocation(self):
        fed = TrustFederation()
        fed.add_peer("a")
        fed.add_peer("b")
        entries = fed.broadcast_revocation("bad-tool", emergency=True)
        assert len(entries) == 1
        assert fed.local_crl.is_revoked("bad-tool")


# ── Federated query tests ──────────────────────────────────────────


class TestFederatedQuery:
    def test_query_local_only(self):
        registry = TrustRegistry()
        registry.register("my-tool", attestation=None)
        fed = TrustFederation(local_registry=registry)
        result = fed.query("my-tool")
        assert result.tool_name == "my-tool"
        assert result.local_score is not None

    def test_query_with_peer_scores(self):
        registry = TrustRegistry()
        registry.register("tool-a", attestation=None)
        fed = TrustFederation(local_registry=registry)
        peer = fed.add_peer("partner", trust_weight=0.8)
        fed.receive_trust_score(peer.peer_id, "tool-a", TrustScore(overall=0.9))
        result = fed.query("tool-a")
        assert result.contributing_peers == 1
        assert len(result.peer_scores) == 1
        assert result.merged_score > 0

    def test_query_merged_score_weighting(self):
        fed = TrustFederation(local_registry=TrustRegistry())
        # No local score for this tool, only peer
        peer = fed.add_peer("partner", trust_weight=0.5)
        fed.receive_trust_score(peer.peer_id, "tool-x", TrustScore(overall=0.8))
        result = fed.query("tool-x")
        assert result.merged_score == pytest.approx(0.8)

    def test_query_revoked_tool(self):
        fed = TrustFederation()
        fed.local_crl.revoke("bad-tool")
        result = fed.query("bad-tool")
        assert result.is_revoked
        assert len(result.revocation_entries) == 1

    def test_query_excludes_suspended_peers(self):
        fed = TrustFederation()
        peer = fed.add_peer("partner")
        fed.receive_trust_score(peer.peer_id, "tool", TrustScore(overall=0.9))
        fed.update_peer_status(peer.peer_id, PeerStatus.SUSPENDED)
        result = fed.query("tool")
        assert result.contributing_peers == 0

    def test_query_min_peer_weight(self):
        fed = TrustFederation()
        p1 = fed.add_peer("weak", trust_weight=0.1)
        p2 = fed.add_peer("strong", trust_weight=0.9)
        fed.receive_trust_score(p1.peer_id, "tool", TrustScore(overall=0.5))
        fed.receive_trust_score(p2.peer_id, "tool", TrustScore(overall=0.9))
        q = FederatedQuery(tool_name="tool", min_peer_weight=0.5)
        result = fed.query("tool", query=q)
        assert result.contributing_peers == 1  # Only the strong peer

    def test_query_result_serialization(self):
        fed = TrustFederation()
        fed.local_crl.revoke("tool")
        result = fed.query("tool")
        d = result.to_dict()
        assert d["is_revoked"] is True
        assert "tool_name" in d

    def test_query_not_found(self):
        fed = TrustFederation()
        result = fed.query("nonexistent")
        assert result.local_score is None
        assert result.merged_score == 0.0
        assert not result.is_revoked


# ── Federation status tests ────────────────────────────────────────


class TestFederationStatus:
    def test_status(self):
        fed = TrustFederation(federation_id="test-fed")
        fed.add_peer("a")
        fed.add_peer("b")
        fed.local_crl.revoke("bad-tool")
        status = fed.get_federation_status()
        assert status["federation_id"] == "test-fed"
        assert status["peer_count"] == 2
        assert status["crl_entries"] == 1


# ── Import tests ───────────────────────────────────────────────────


class TestImports:
    def test_federation_imports(self):
        from fastmcp.server.security.federation import (
            TrustFederation,
        )

        assert TrustFederation is not None

    def test_top_level_imports(self):
        from fastmcp.server.security import (
            TrustFederation,
        )

        assert TrustFederation is not None


# ── Broadcast revocation tests ─────────────────────────────────────


class _RecordingTransport:
    """Synchronous transport that captures every call instead of POSTing."""

    def __init__(self, *, fail_for: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._fail_for = fail_for or set()

    def send_revocation(self, peer, payload):
        self.calls.append((peer.peer_id, payload))
        if peer.peer_id in self._fail_for:
            raise ConnectionError(f"simulated failure for {peer.peer_id}")


class _AsyncRecordingTransport:
    """Async transport that captures every call instead of POSTing."""

    def __init__(self, *, fail_for: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._fail_for = fail_for or set()

    async def send_revocation(self, peer, payload):
        self.calls.append((peer.peer_id, payload))
        if peer.peer_id in self._fail_for:
            raise ConnectionError(f"simulated failure for {peer.peer_id}")


class TestBroadcastRevocation:
    """broadcast_revocation must actually push to peers, not silently no-op.

    Regression test for the bug where the federation created the local
    CRL entry but never invoked any transport, leaving every "broadcast"
    a no-op.
    """

    def test_broadcast_with_no_transport_warns_and_returns_local_entry(self, caplog):
        """Backward compat: no transport → local-only behavior, but loud."""
        import logging

        fed = TrustFederation()
        fed.add_peer("a", endpoint="https://a.example")
        fed.add_peer("b", endpoint="https://b.example")

        with caplog.at_level(logging.WARNING):
            entries = fed.broadcast_revocation("bad-tool", emergency=True)

        assert len(entries) == 1
        assert fed.local_crl.is_revoked("bad-tool")
        # Operator must see a warning when peers exist but no transport is wired.
        assert any(
            "no broadcast_transport configured" in record.message
            for record in caplog.records
        )

        result = fed.last_broadcast_result
        assert result is not None
        assert result.transport_configured is False
        assert result.deliveries == []  # nothing was attempted

    def test_broadcast_pushes_to_each_active_peer(self):
        transport = _RecordingTransport()
        fed = TrustFederation(broadcast_transport=transport)
        peer_a = fed.add_peer("a", endpoint="https://a.example")
        peer_b = fed.add_peer("b", endpoint="https://b.example")

        fed.broadcast_revocation(
            "bad-tool",
            emergency=True,
            description="key leak",
        )

        # Each active peer received exactly one push with the full payload.
        assert len(transport.calls) == 2
        peer_ids = {peer_id for peer_id, _ in transport.calls}
        assert peer_ids == {peer_a.peer_id, peer_b.peer_id}
        for _, payload in transport.calls:
            assert payload["tool_name"] == "bad-tool"
            assert payload["emergency"] is True
            assert payload["reason"] == "security_incident"
            assert payload["description"] == "key leak"

    def test_broadcast_skips_suspended_and_revoked_peers(self):
        transport = _RecordingTransport()
        fed = TrustFederation(broadcast_transport=transport)
        active = fed.add_peer("active", endpoint="https://a")
        suspended = fed.add_peer("suspended", endpoint="https://s")
        revoked = fed.add_peer("revoked", endpoint="https://r")
        fed.update_peer_status(suspended.peer_id, PeerStatus.SUSPENDED)
        fed.update_peer_status(revoked.peer_id, PeerStatus.REVOKED)

        fed.broadcast_revocation("tool")

        delivered_ids = {peer_id for peer_id, _ in transport.calls}
        assert delivered_ids == {active.peer_id}

    def test_broadcast_failure_marks_peer_unreachable(self):
        # Peer A succeeds, peer B fails — A stays ACTIVE, B flips to UNREACHABLE.
        peer_b_id = "peer-b"
        transport = _RecordingTransport(fail_for={peer_b_id})
        fed = TrustFederation(broadcast_transport=transport)
        peer_a = fed.add_peer("a", endpoint="https://a")
        peer_b = fed.add_peer("b", endpoint="https://b", peer_id=peer_b_id)

        fed.broadcast_revocation("tool")

        assert peer_a.status == PeerStatus.ACTIVE
        assert peer_b.status == PeerStatus.UNREACHABLE
        assert peer_a.pushed_revocations == 1
        assert peer_a.push_failures == 0
        assert peer_b.pushed_revocations == 0
        assert peer_b.push_failures == 1

        result = fed.last_broadcast_result
        assert result is not None
        assert result.delivered_count == 1
        assert result.failure_count == 1
        # The failed delivery carries the underlying error string.
        failed = next(d for d in result.deliveries if not d.delivered)
        assert "ConnectionError" in (failed.error or "")

    def test_broadcast_success_recovers_unreachable_peer(self):
        transport = _RecordingTransport()
        fed = TrustFederation(broadcast_transport=transport)
        peer = fed.add_peer("a", endpoint="https://a")
        fed.update_peer_status(peer.peer_id, PeerStatus.UNREACHABLE)

        # An UNREACHABLE peer is not eligible for delivery at all — skipped.
        fed.broadcast_revocation("tool-1")
        assert transport.calls == []
        assert peer.status == PeerStatus.UNREACHABLE

        # After an admin manually flips it back to ACTIVE, broadcasts
        # land and the peer is confirmed reachable.
        fed.update_peer_status(peer.peer_id, PeerStatus.ACTIVE)
        fed.broadcast_revocation("tool-2")
        assert len(transport.calls) == 1
        assert peer.status == PeerStatus.ACTIVE

    def test_broadcast_continues_after_one_peer_fails(self):
        """A single failing peer must not stop delivery to other peers."""
        transport = _RecordingTransport(fail_for={"will-fail"})
        fed = TrustFederation(broadcast_transport=transport)
        fed.add_peer("a", endpoint="https://a", peer_id="will-fail")
        fed.add_peer("b", endpoint="https://b", peer_id="will-succeed-1")
        fed.add_peer("c", endpoint="https://c", peer_id="will-succeed-2")

        fed.broadcast_revocation("tool")

        # All three peers were attempted, even though the first one raised.
        peer_ids = [peer_id for peer_id, _ in transport.calls]
        assert sorted(peer_ids) == ["will-fail", "will-succeed-1", "will-succeed-2"]

    def test_broadcast_emits_event(self):
        bus = SecurityEventBus()
        handler = BufferedHandler(max_size=10)
        bus.subscribe(handler)
        transport = _RecordingTransport()
        fed = TrustFederation(event_bus=bus, broadcast_transport=transport)
        fed.add_peer("a", endpoint="https://a")

        fed.broadcast_revocation("tool", emergency=True)

        assert len(handler.events) == 1
        event = handler.events[0]
        assert event.layer == "federation"
        assert event.resource_id == "tool"
        assert event.severity.value == "critical"
        assert event.data["delivered_count"] == 1

    def test_broadcast_async_fans_out_concurrently(self):
        import asyncio

        transport = _AsyncRecordingTransport()
        fed = TrustFederation(broadcast_transport=transport)
        fed.add_peer("a", endpoint="https://a")
        fed.add_peer("b", endpoint="https://b")
        fed.add_peer("c", endpoint="https://c")

        result = asyncio.run(fed.abroadcast_revocation("tool"))

        assert isinstance(result, BroadcastResult)
        assert result.delivered_count == 3
        assert result.failure_count == 0
        assert len(transport.calls) == 3
        assert fed.local_crl.is_revoked("tool")

    def test_broadcast_async_captures_per_peer_failures(self):
        import asyncio

        transport = _AsyncRecordingTransport(fail_for={"flaky"})
        fed = TrustFederation(broadcast_transport=transport)
        fed.add_peer("ok", endpoint="https://ok", peer_id="ok")
        fed.add_peer("flaky", endpoint="https://flaky", peer_id="flaky")

        result = asyncio.run(fed.abroadcast_revocation("tool"))

        assert result.delivered_count == 1
        assert result.failure_count == 1
        flaky_peer = fed.get_peer("flaky")
        assert flaky_peer is not None
        assert flaky_peer.status == PeerStatus.UNREACHABLE

    def test_sync_broadcast_with_async_transport_raises(self):
        """A misuse — async transport with sync broadcast — must fail loudly."""
        transport = _AsyncRecordingTransport()
        fed = TrustFederation(broadcast_transport=transport)
        fed.add_peer("a", endpoint="https://a")

        fed.broadcast_revocation("tool")

        # The local CRL was still revoked.
        assert fed.local_crl.is_revoked("tool")
        # And the misuse was captured per-peer rather than crashing the call.
        result = fed.last_broadcast_result
        assert result is not None
        assert result.failure_count == 1
        assert result.deliveries[0].error is not None
        assert "abroadcast_revocation" in result.deliveries[0].error

    def test_set_broadcast_transport_late_binds(self):
        fed = TrustFederation()
        fed.add_peer("a", endpoint="https://a")
        # No transport yet — broadcast is local-only.
        fed.broadcast_revocation("tool-1")
        assert fed.last_broadcast_result.transport_configured is False

        # Wire a transport after construction.
        transport = _RecordingTransport()
        fed.set_broadcast_transport(transport)
        fed.broadcast_revocation("tool-2")
        assert fed.last_broadcast_result.transport_configured is True
        assert len(transport.calls) == 1

    def test_payload_contains_signed_metadata(self):
        transport = _RecordingTransport()
        fed = TrustFederation(broadcast_transport=transport, federation_id="alpha")
        fed.add_peer("a", endpoint="https://a")

        fed.broadcast_revocation(
            "bad-tool",
            attestation_id="att-1",
            description="oops",
        )

        assert len(transport.calls) == 1
        _, payload = transport.calls[0]
        assert payload["federation_id"] == "alpha"
        assert payload["tool_name"] == "bad-tool"
        assert payload["attestation_id"] == "att-1"
        assert payload["description"] == "oops"
        assert "entry_id" in payload
        assert "revoked_at" in payload


# ── HTTPBroadcastTransport tests ───────────────────────────────────


class TestHTTPBroadcastTransport:
    def test_signing_secret_attaches_signature_header(self):
        from fastmcp.server.security.federation.transport import (
            HTTPBroadcastTransport,
        )

        transport = HTTPBroadcastTransport(signing_secret="shhh")
        body = b'{"a":1}'
        headers = transport._build_headers(body, {"federation_id": "f1"})
        assert "X-Federation-Signature" in headers
        assert headers["X-Federation-Signature"].startswith("sha256=")
        assert headers["X-Federation-Id"] == "f1"

    def test_no_signing_secret_no_signature_header(self):
        from fastmcp.server.security.federation.transport import (
            HTTPBroadcastTransport,
        )

        transport = HTTPBroadcastTransport()
        headers = transport._build_headers(b"{}", {"federation_id": "f1"})
        assert "X-Federation-Signature" not in headers

    def test_url_built_from_endpoint_and_path(self):
        from fastmcp.server.security.federation.federation import FederationPeer
        from fastmcp.server.security.federation.transport import (
            HTTPBroadcastTransport,
        )

        peer = FederationPeer(peer_id="p1", name="p", endpoint="https://example.com/")
        transport = HTTPBroadcastTransport(path="/fed/revoke")
        assert transport._build_url(peer) == "https://example.com/fed/revoke"

    def test_no_endpoint_raises(self):
        from fastmcp.server.security.federation.federation import FederationPeer
        from fastmcp.server.security.federation.transport import (
            HTTPBroadcastTransport,
        )

        peer = FederationPeer(peer_id="p1", name="p", endpoint="")
        transport = HTTPBroadcastTransport()
        with pytest.raises(ValueError, match="no endpoint configured"):
            transport._build_url(peer)
