"""Security regressions for federation HTTP broadcast transports."""

from __future__ import annotations

import threading
from typing import Any

import pytest

from fastmcp.server.security.federation import transport as transport_module
from fastmcp.server.security.federation.federation import (
    FederationPeer,
    TrustFederation,
)
from fastmcp.server.security.federation.messages import (
    FEDERATION_NONCE_HEADER,
    FEDERATION_SIGNATURE_HEADER,
    FEDERATION_SIGNATURE_VERSION_HEADER,
    FEDERATION_TIMESTAMP_HEADER,
)
from fastmcp.server.security.federation.transport import (
    AsyncHTTPBroadcastTransport,
    HTTPBroadcastTransport,
)
from fastmcp.server.security.outbound import UnsafeOutboundURLError

_PAYLOAD = {"federation_id": "sender-1", "tool_name": "revoked-tool"}
_PEER = FederationPeer(
    peer_id="peer-1",
    name="Partner",
    endpoint="https://peer.example",
)


class _ThreadRecordingTransport:
    def __init__(self) -> None:
        self.thread_ids: list[int] = []

    def send_revocation(
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None:
        del peer, payload
        self.thread_ids.append(threading.get_ident())


def test_broadcast_refuses_unsigned_messages_by_default():
    transport = HTTPBroadcastTransport()

    with pytest.raises(ValueError, match="require signing_secret"):
        transport.send_revocation(_PEER, dict(_PAYLOAD))


def test_signed_broadcast_uses_hardened_request_boundary(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    def send(url: str, **kwargs: Any) -> None:
        captured["url"] = url
        captured.update(kwargs)

    monkeypatch.setattr(transport_module, "secure_outbound_request", send)
    transport = HTTPBroadcastTransport(signing_secret="shared-secret")

    transport.send_revocation(_PEER, dict(_PAYLOAD))

    assert captured["url"] == "https://peer.example/federation/revocations"
    headers = captured["headers"]
    assert FEDERATION_SIGNATURE_HEADER in headers
    assert FEDERATION_TIMESTAMP_HEADER in headers
    assert FEDERATION_NONCE_HEADER in headers
    assert headers[FEDERATION_SIGNATURE_VERSION_HEADER] == "2"
    assert captured["max_response_bytes"] == 64 * 1024


async def test_async_broadcast_uses_hardened_async_boundary(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    async def send(url: str, **kwargs: Any) -> None:
        captured["url"] = url
        captured.update(kwargs)

    monkeypatch.setattr(transport_module, "async_secure_outbound_request", send)
    transport = AsyncHTTPBroadcastTransport(signing_secret="shared-secret")

    await transport.send_revocation(_PEER, dict(_PAYLOAD))

    assert captured["url"] == "https://peer.example/federation/revocations"
    assert captured["method"] == "POST"


async def test_async_fanout_dispatches_sync_transport_off_event_loop():
    transport = _ThreadRecordingTransport()
    federation = TrustFederation(
        broadcast_transport=transport,
    )
    federation.add_peer("Partner", endpoint="https://peer.example")
    event_loop_thread = threading.get_ident()

    result = await federation.abroadcast_revocation("revoked-tool")

    assert result.delivered_count == 1
    assert transport.thread_ids
    assert transport.thread_ids[0] != event_loop_thread


def test_default_broadcast_policy_rejects_local_cleartext_endpoint():
    peer = FederationPeer(
        peer_id="local",
        name="Local",
        endpoint="http://127.0.0.1:8080",
    )
    transport = HTTPBroadcastTransport(signing_secret="shared-secret")

    with pytest.raises(UnsafeOutboundURLError, match="must use HTTPS"):
        transport.send_revocation(peer, dict(_PAYLOAD))


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://peer.example?target=other",
        "https://peer.example#fragment",
    ],
)
def test_broadcast_endpoint_rejects_query_and_fragment(endpoint: str):
    peer = FederationPeer(peer_id="peer", name="Peer", endpoint=endpoint)
    transport = HTTPBroadcastTransport(signing_secret="shared-secret")

    with pytest.raises(ValueError, match="without a query or fragment"):
        transport._build_url(peer)
