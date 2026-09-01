"""Hardened HTTP transports for trust-federation revocation broadcasts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

from fastmcp.server.security.federation.messages import (
    build_signed_federation_headers,
    canonical_federation_body,
)
from fastmcp.server.security.outbound import (
    OutboundNetworkPolicy,
    async_secure_outbound_request,
    secure_outbound_request,
)

if TYPE_CHECKING:
    from fastmcp.server.security.federation.federation import FederationPeer

DEFAULT_MAX_FEDERATION_RESPONSE_BYTES = 64 * 1024


class HTTPBroadcastTransport:
    """Synchronously deliver signed revocations over hardened HTTP.

    Destinations must be public HTTPS URLs by default. Supply an
    :class:`~fastmcp.server.security.outbound.OutboundNetworkPolicy` with exact
    host exceptions for an intentional local-development deployment. Redirects,
    environment proxies, DNS rebinding, and unbounded responses are rejected by
    the shared outbound request boundary.

    Messages require an HMAC signing secret by default. Set
    ``allow_unsigned=True`` only when a separate authenticated transport protects
    the entire path.
    """

    def __init__(
        self,
        *,
        path: str = "/federation/revocations",
        timeout: float = 5.0,
        signing_secret: bytes | str | None = None,
        federation_id_header: str = "X-Federation-Id",
        outbound_policy: OutboundNetworkPolicy | None = None,
        max_response_bytes: int = DEFAULT_MAX_FEDERATION_RESPONSE_BYTES,
        allow_unsigned: bool = False,
    ) -> None:
        if not path or "?" in path or "#" in path:
            raise ValueError("Federation path must be a plain URL path")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be greater than zero")
        self._path = "/" + path.lstrip("/")
        self._timeout = float(timeout)
        self._signing_secret = signing_secret
        self._federation_id_header = federation_id_header
        self._outbound_policy = outbound_policy or OutboundNetworkPolicy()
        self._max_response_bytes = max_response_bytes
        self._allow_unsigned = allow_unsigned

    def _build_url(self, peer: FederationPeer) -> str:
        if not peer.endpoint:
            raise ValueError(
                f"Federation peer '{peer.peer_id}' has no endpoint configured; "
                "set endpoint=... when calling federation.add_peer()"
            )
        try:
            parsed = urlsplit(peer.endpoint)
        except ValueError as exc:
            raise ValueError("Federation peer endpoint is invalid") from exc
        if not parsed.scheme or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(
                "Federation peer endpoint must be an HTTP(S) origin or base path "
                "without a query or fragment"
            )
        path = parsed.path.rstrip("/") + self._path
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))

    def _build_headers(
        self,
        body: bytes,
        payload: Mapping[str, Any],
    ) -> dict[str, str]:
        federation_id = payload.get("federation_id")
        if type(federation_id) is not str or not federation_id:
            raise ValueError("Federation payload requires a federation_id")
        if self._signing_secret is None:
            return {
                "Content-Type": "application/json",
                self._federation_id_header: federation_id,
            }

        headers = build_signed_federation_headers(
            body,
            federation_id=federation_id,
            signing_secret=self._signing_secret,
        )
        if self._federation_id_header != "X-Federation-Id":
            headers[self._federation_id_header] = headers.pop("X-Federation-Id")
        return headers

    def _prepare_request(
        self,
        payload: Mapping[str, Any],
    ) -> tuple[bytes, dict[str, str]]:
        if self._signing_secret is None and not self._allow_unsigned:
            raise ValueError(
                "Federation broadcasts require signing_secret; set "
                "allow_unsigned=True only behind another authenticated transport"
            )
        body = canonical_federation_body(payload)
        return body, self._build_headers(body, payload)

    def send_revocation(
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None:
        """Synchronously POST one authenticated, bounded message."""
        body, headers = self._prepare_request(payload)
        secure_outbound_request(
            self._build_url(peer),
            method="POST",
            content=body,
            headers=headers,
            policy=self._outbound_policy,
            timeout=self._timeout,
            overall_timeout=self._timeout,
            max_request_bytes=256 * 1024,
            max_response_bytes=self._max_response_bytes,
        )


class AsyncHTTPBroadcastTransport(HTTPBroadcastTransport):
    """Asynchronously deliver signed revocations over hardened HTTP."""

    async def send_revocation(  # ty: ignore[invalid-method-override]
        self,
        peer: FederationPeer,
        payload: dict[str, Any],
    ) -> None:
        body, headers = self._prepare_request(payload)
        await async_secure_outbound_request(
            self._build_url(peer),
            method="POST",
            content=body,
            headers=headers,
            policy=self._outbound_policy,
            timeout=self._timeout,
            overall_timeout=self._timeout,
            max_request_bytes=256 * 1024,
            max_response_bytes=self._max_response_bytes,
        )


__all__ = [
    "DEFAULT_MAX_FEDERATION_RESPONSE_BYTES",
    "AsyncHTTPBroadcastTransport",
    "HTTPBroadcastTransport",
]
