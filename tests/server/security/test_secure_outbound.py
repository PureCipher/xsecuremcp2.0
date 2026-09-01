"""Adversarial tests for SecureMCP's shared outbound HTTP boundary."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterable
from typing import Any

import httpx2
import pytest

from fastmcp.server.security.outbound import (
    OutboundNetworkPolicy,
    OutboundRequestError,
    OutboundResponseTooLargeError,
    UnsafeOutboundURLError,
    async_secure_outbound_request,
    secure_outbound_request,
)


def _resolver(*addresses: str):
    def resolve(_host: str, port: int) -> Iterable[tuple[Any, ...]]:
        return [
            (socket.AF_UNSPEC, socket.SOCK_STREAM, 0, "", (address, port))
            for address in addresses
        ]

    return resolve


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/api",
        "ftp://public.example/api",
        "https://user:secret@public.example/api",
        "https://public.example/api#fragment",
        "https://public.example/has a space",
    ],
)
def test_outbound_policy_rejects_unsafe_url_shapes(url: str):
    policy = OutboundNetworkPolicy(resolver=_resolver("93.184.216.34"))

    with pytest.raises(UnsafeOutboundURLError):
        policy.resolve(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "64:ff9b::7f00:1",
    ],
)
def test_outbound_policy_rejects_protected_addresses(address: str):
    policy = OutboundNetworkPolicy(resolver=_resolver(address))

    with pytest.raises(UnsafeOutboundURLError, match="protected address"):
        policy.resolve("https://service.example/api")


def test_outbound_policy_rejects_mixed_public_and_private_dns_answers():
    policy = OutboundNetworkPolicy(resolver=_resolver("93.184.216.34", "127.0.0.1"))

    with pytest.raises(UnsafeOutboundURLError, match="protected address"):
        policy.resolve("https://service.example/api")


def test_local_http_requires_both_explicit_host_exceptions():
    policy = OutboundNetworkPolicy(
        allow_http_hosts={"localhost"},
        resolver=_resolver("127.0.0.1"),
    )

    with pytest.raises(UnsafeOutboundURLError, match="protected address"):
        policy.resolve("http://localhost:8181/v1/data/policy")


def test_local_http_is_allowed_when_both_exceptions_are_explicit():
    policy = OutboundNetworkPolicy(
        allow_http_hosts={"LOCALHOST."},
        allow_private_hosts={"localhost"},
        resolver=_resolver("127.0.0.1"),
    )

    validated = policy.resolve("http://localhost:8181/v1/data/policy")

    assert validated.resolved_addresses == ("127.0.0.1",)
    assert validated.connection_urls() == ("http://127.0.0.1:8181/v1/data/policy",)


def test_sync_request_pins_address_and_preserves_host_identity():
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, content=b"ok")

    response = secure_outbound_request(
        "https://service.example:8443/evaluate?q=1",
        method="POST",
        content=b"{}",
        policy=OutboundNetworkPolicy(resolver=_resolver("93.184.216.34")),
        transport_factory=lambda: httpx2.MockTransport(handler),
    )

    assert response.content == b"ok"
    assert str(seen[0].url) == "https://93.184.216.34:8443/evaluate?q=1"
    assert seen[0].headers["host"] == "service.example:8443"
    assert seen[0].extensions["sni_hostname"] == "service.example"


def test_sync_request_retries_only_connection_failures_across_pinned_addresses():
    hosts: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        hosts.append(request.url.host)
        if len(hosts) == 1:
            raise httpx2.ConnectError("unreachable", request=request)
        return httpx2.Response(204)

    response = secure_outbound_request(
        "https://service.example/event",
        method="POST",
        content=b"{}",
        policy=OutboundNetworkPolicy(
            resolver=_resolver("93.184.216.34", "93.184.216.35")
        ),
        transport_factory=lambda: httpx2.MockTransport(handler),
    )

    assert response.status_code == 204
    assert hosts == ["93.184.216.34", "93.184.216.35"]


def test_sync_request_rejects_redirect_without_following_it():
    calls = 0

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(302, headers={"Location": "https://other.example"})

    with pytest.raises(OutboundRequestError, match="Redirects"):
        secure_outbound_request(
            "https://service.example/event",
            method="POST",
            content=b"{}",
            policy=OutboundNetworkPolicy(resolver=_resolver("93.184.216.34")),
            transport_factory=lambda: httpx2.MockTransport(handler),
        )

    assert calls == 1


def test_sync_request_rejects_declared_oversized_response():
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers={"Content-Length": "100"})

    with pytest.raises(OutboundResponseTooLargeError):
        secure_outbound_request(
            "https://service.example/event",
            method="POST",
            content=b"{}",
            policy=OutboundNetworkPolicy(resolver=_resolver("93.184.216.34")),
            max_response_bytes=10,
            transport_factory=lambda: httpx2.MockTransport(handler),
        )


def test_sync_request_rejects_oversized_request_before_transport():
    called = False

    def handler(_request: httpx2.Request) -> httpx2.Response:
        nonlocal called
        called = True
        return httpx2.Response(200)

    with pytest.raises(OutboundRequestError, match="request exceeds"):
        secure_outbound_request(
            "https://service.example/event",
            method="POST",
            content=b"too large",
            policy=OutboundNetworkPolicy(resolver=_resolver("93.184.216.34")),
            max_request_bytes=2,
            transport_factory=lambda: httpx2.MockTransport(handler),
        )

    assert called is False


async def test_async_request_uses_the_same_dns_pinning_boundary():
    seen: list[httpx2.Request] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, content=b"ok")

    response = await async_secure_outbound_request(
        "https://service.example/event",
        method="POST",
        content=b"{}",
        policy=OutboundNetworkPolicy(resolver=_resolver("93.184.216.34")),
        transport_factory=lambda: httpx2.MockTransport(handler),
    )

    assert response.content == b"ok"
    assert seen[0].url.host == "93.184.216.34"
    assert seen[0].headers["host"] == "service.example"
    assert seen[0].extensions["sni_hostname"] == "service.example"


async def test_async_request_resolves_dns_off_the_event_loop():
    event_loop_thread = threading.get_ident()
    resolver_threads: list[int] = []

    def resolver(_host: str, port: int) -> Iterable[tuple[Any, ...]]:
        resolver_threads.append(threading.get_ident())
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                0,
                "",
                ("93.184.216.34", port),
            )
        ]

    async def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(204)

    await async_secure_outbound_request(
        "https://service.example/event",
        method="POST",
        content=b"{}",
        policy=OutboundNetworkPolicy(resolver=resolver),
        transport_factory=lambda: httpx2.MockTransport(handler),
    )

    assert resolver_threads
    assert resolver_threads[0] != event_loop_thread
