"""Outbound network controls for PureCipher proxy traffic."""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable, Iterable
from urllib.parse import quote, unquote, urlparse

import httpx

DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class UnsafeOutboundURLError(ValueError):
    """Raised when a proxy target could reach a protected network."""


class OutboundResponseTooLargeError(RuntimeError):
    """Raised when an upstream response exceeds the configured byte limit."""


class UnsafeOutboundPathError(ValueError):
    """Raised when a path parameter could be normalized outside its segment."""


AddressResolver = Callable[[str, int], Iterable[tuple]]


def encode_outbound_path_segment(value: str) -> str:
    """Encode one path parameter after rejecting traversal-shaped values."""
    decoded = value
    for _ in range(5):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    else:
        raise UnsafeOutboundPathError(
            "Outbound path parameters may not be repeatedly encoded"
        )
    normalized = decoded.replace("\\", "/")
    for segment in normalized.split("/"):
        # Some application servers strip matrix parameters before routing.
        if segment.split(";", 1)[0] in {".", ".."}:
            raise UnsafeOutboundPathError(
                "Outbound path parameters may not contain dot segments"
            )
    return quote(value, safe="")


def validate_outbound_url(
    url: str,
    *,
    resolver: AddressResolver = socket.getaddrinfo,
) -> None:
    """Reject non-HTTPS and non-public OpenAPI proxy destinations.

    Operators may explicitly permit development hosts through
    ``PURECIPHER_OPENAPI_ALLOW_HTTP_HOSTS`` or private destinations through
    ``PURECIPHER_OPENAPI_ALLOW_PRIVATE_HOSTS``. Both variables contain
    comma-separated exact hostnames.
    """
    resolve_outbound_addresses(url, resolver=resolver)


def resolve_outbound_addresses(
    url: str,
    *,
    resolver: AddressResolver = socket.getaddrinfo,
) -> tuple[str, ...]:
    """Validate an outbound URL and return its approved network addresses.

    The returned addresses are intended to be used for the actual connection,
    rather than resolving the hostname a second time after validation. Reserved
    ``.example`` names return an empty tuple because they are a non-routable
    test seam.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host or parsed.username or parsed.password:
        raise UnsafeOutboundURLError("Outbound URL must contain a plain hostname")

    allow_http = _configured_hosts("PURECIPHER_OPENAPI_ALLOW_HTTP_HOSTS")
    allow_private = _configured_hosts("PURECIPHER_OPENAPI_ALLOW_PRIVATE_HOSTS")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and host in allow_http
    ):
        raise UnsafeOutboundURLError("OpenAPI proxy destinations must use HTTPS")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeOutboundURLError("Outbound URL contains an invalid port") from exc
    try:
        addresses = list(resolver(host, port))
    except OSError as exc:
        # RFC 2606 example domains are non-routable test fixtures. If a local
        # resolver does map one, it must pass the same address checks below.
        if host == "example" or host.endswith(".example"):
            return ()
        raise UnsafeOutboundURLError(
            f"Could not resolve outbound host {host!r}"
        ) from exc
    if not addresses:
        raise UnsafeOutboundURLError(f"Could not resolve outbound host {host!r}")

    approved: list[str] = []
    for entry in addresses:
        sockaddr = entry[4]
        address_text = str(sockaddr[0])
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError as exc:
            raise UnsafeOutboundURLError(
                f"Resolver returned an invalid address for {host!r}"
            ) from exc
        if host not in allow_private and not address.is_global:
            raise UnsafeOutboundURLError(
                f"Outbound host {host!r} resolves to a protected address"
            )
        normalized = str(address)
        if normalized not in approved:
            approved.append(normalized)
    return tuple(approved)


class PinnedDNSAsyncTransport(httpx.AsyncBaseTransport):
    """Connect to the same IP address that passed outbound validation.

    HTTP ``Host`` and TLS SNI continue to use the original hostname, while the
    socket destination is rewritten to the validated address. This closes the
    DNS-rebinding window between a preflight lookup and the real connection.
    """

    def __init__(
        self,
        *,
        resolver: AddressResolver = socket.getaddrinfo,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._resolver = resolver
        self._injected_transport = transport
        self._transports: dict[
            tuple[str, str, int | None], httpx.AsyncBaseTransport
        ] = {}

    def _transport_for(self, url: httpx.URL) -> httpx.AsyncBaseTransport:
        if self._injected_transport is not None:
            return self._injected_transport
        origin = (url.scheme, url.host, url.port)
        transport = self._transports.get(origin)
        if transport is None:
            # Keep pools isolated by the original hostname. Two virtual hosts
            # that share an IP must not reuse one another's TLS connection.
            transport = httpx.AsyncHTTPTransport(trust_env=False)
            self._transports[origin] = transport
        return transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        original_url = request.url
        addresses = resolve_outbound_addresses(
            str(original_url),
            resolver=self._resolver,
        )
        if not addresses:
            raise UnsafeOutboundURLError(
                f"Could not resolve outbound host {original_url.host!r} "
                "to a validated address"
            )
        transport = self._transport_for(original_url)

        headers = request.headers.copy()
        headers["Host"] = original_url.netloc.decode("ascii")
        extensions = dict(request.extensions)
        extensions["sni_hostname"] = original_url.host
        last_connect_error: httpx.ConnectError | httpx.ConnectTimeout | None = None
        for address in addresses:
            pinned_request = httpx.Request(
                method=request.method,
                url=original_url.copy_with(host=address),
                headers=headers,
                stream=request.stream,
                extensions=extensions,
            )
            try:
                return await transport.handle_async_request(pinned_request)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_connect_error = exc
        assert last_connect_error is not None
        raise last_connect_error

    async def aclose(self) -> None:
        if self._injected_transport is not None:
            await self._injected_transport.aclose()
            return
        transports = list(self._transports.values())
        self._transports = {}
        for transport in transports:
            await transport.aclose()


async def read_response_body_limited(
    response: httpx.Response,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> bytes:
    """Read a streaming response without allowing unbounded memory growth."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    content_length = response.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = -1
        if declared_size > max_bytes:
            raise OutboundResponseTooLargeError(
                f"Upstream response exceeds the {max_bytes}-byte limit"
            )

    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise OutboundResponseTooLargeError(
                f"Upstream response exceeds the {max_bytes}-byte limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _configured_hosts(variable: str) -> frozenset[str]:
    return frozenset(
        value.strip().rstrip(".").lower()
        for value in os.getenv(variable, "").split(",")
        if value.strip()
    )


__all__ = [
    "DEFAULT_MAX_RESPONSE_BYTES",
    "OutboundResponseTooLargeError",
    "PinnedDNSAsyncTransport",
    "UnsafeOutboundPathError",
    "UnsafeOutboundURLError",
    "encode_outbound_path_segment",
    "read_response_body_limited",
    "resolve_outbound_addresses",
    "validate_outbound_url",
]
