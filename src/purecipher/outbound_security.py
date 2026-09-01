"""Outbound URL validation for PureCipher proxy traffic."""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlparse


class UnsafeOutboundURLError(ValueError):
    """Raised when a proxy target could reach a protected network."""


AddressResolver = Callable[[str, int], Iterable[tuple]]


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

    if host in allow_private:
        return

    # RFC 2606 example domains are non-routable and used by the test suite.
    if host == "example" or host.endswith(".example"):
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = list(resolver(host, port))
    except OSError as exc:
        raise UnsafeOutboundURLError(
            f"Could not resolve outbound host {host!r}"
        ) from exc
    if not addresses:
        raise UnsafeOutboundURLError(f"Could not resolve outbound host {host!r}")

    for entry in addresses:
        sockaddr = entry[4]
        address = ipaddress.ip_address(sockaddr[0])
        if not address.is_global:
            raise UnsafeOutboundURLError(
                f"Outbound host {host!r} resolves to a protected address"
            )


def _configured_hosts(variable: str) -> frozenset[str]:
    return frozenset(
        value.strip().rstrip(".").lower()
        for value in os.getenv(variable, "").split(",")
        if value.strip()
    )


__all__ = ["UnsafeOutboundURLError", "validate_outbound_url"]
