"""Broadcast transports for the trust federation.

Concrete implementations of :class:`BroadcastTransport` that push
federation messages out over the wire. The federation core is
transport-agnostic; pick the transport that matches your deployment
or implement your own.

The default :class:`HTTPBroadcastTransport` POSTs JSON payloads to the
peer's ``endpoint`` and expects the receiver to forward them into its
own :meth:`TrustFederation.receive_revocation` call. The wire path
defaults to ``/federation/revocations`` and is overridable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp.server.security.federation.federation import FederationPeer

logger = logging.getLogger(__name__)


class HTTPBroadcastTransport:
    """Default HTTP broadcast transport.

    POSTs the broadcast payload as JSON to ``{peer.endpoint}{path}``.
    A non-2xx response raises ``httpx.HTTPStatusError``; connection or
    timeout failures raise the underlying ``httpx`` exception. The
    federation captures these per-peer.

    Args:
        path: URL path appended to ``peer.endpoint``. Default
            ``/federation/revocations``.
        timeout: Per-request timeout in seconds. Default 5.0.
        signing_secret: Optional shared secret. When set, an
            ``X-Federation-Signature`` header is attached carrying an
            HMAC-SHA256 of the canonical JSON body. Receivers can
            verify the signature before forwarding the payload to
            :meth:`TrustFederation.receive_revocation`.
        federation_id_header: Header used to identify the sending
            federation. Default ``X-Federation-Id``.
    """

    def __init__(
        self,
        *,
        path: str = "/federation/revocations",
        timeout: float = 5.0,
        signing_secret: str | None = None,
        federation_id_header: str = "X-Federation-Id",
    ) -> None:
        self._path = "/" + path.lstrip("/")
        self._timeout = float(timeout)
        self._signing_secret = signing_secret
        self._federation_id_header = federation_id_header

    def _sign(self, body: bytes) -> str:
        """Compute the canonical HMAC-SHA256 signature of the request body."""
        import hashlib
        import hmac

        assert self._signing_secret is not None  # caller-guarded
        digest = hmac.new(
            self._signing_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    def _build_url(self, peer: FederationPeer) -> str:
        if not peer.endpoint:
            raise ValueError(
                f"Federation peer '{peer.peer_id}' has no endpoint configured; "
                "set endpoint=... when calling federation.add_peer()"
            )
        return peer.endpoint.rstrip("/") + self._path

    def _build_headers(self, body: bytes, payload: dict[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._signing_secret:
            headers["X-Federation-Signature"] = self._sign(body)
        federation_id = payload.get("federation_id")
        if isinstance(federation_id, str) and federation_id:
            headers[self._federation_id_header] = federation_id
        return headers

    def send_revocation(
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None:
        """Synchronously POST the payload to ``peer.endpoint``."""
        # Lazy import keeps httpx optional for users who supply their
        # own transport.
        import json

        import httpx

        url = self._build_url(peer)
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        headers = self._build_headers(body, payload)
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, content=body, headers=headers)
            response.raise_for_status()


class AsyncHTTPBroadcastTransport(HTTPBroadcastTransport):
    """Async variant of :class:`HTTPBroadcastTransport`.

    Uses ``httpx.AsyncClient`` so peer fan-out from
    :meth:`TrustFederation.abroadcast_revocation` runs without blocking
    the event loop.
    """

    async def send_revocation(  # type: ignore[override]
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None:
        import json

        import httpx

        url = self._build_url(peer)
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        headers = self._build_headers(body, payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
