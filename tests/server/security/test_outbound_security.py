"""Tests for OpenAPI proxy egress restrictions."""

import socket

import httpx
import pytest

from purecipher.outbound_security import (
    OutboundResponseTooLargeError,
    PinnedDNSAsyncTransport,
    UnsafeOutboundPathError,
    UnsafeOutboundURLError,
    encode_outbound_path_segment,
    read_response_body_limited,
    resolve_outbound_addresses,
    validate_outbound_url,
)


def _resolver_for(address: str):
    def resolve(host: str, port: int):
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (address, port))]

    return resolve


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.4", "169.254.169.254", "::1", "fc00::1"],
)
def test_rejects_hosts_resolving_to_protected_addresses(address):
    with pytest.raises(UnsafeOutboundURLError, match="protected address"):
        validate_outbound_url(
            "https://service.invalid/data", resolver=_resolver_for(address)
        )


def test_accepts_public_https_address():
    addresses = resolve_outbound_addresses(
        "https://service.invalid/data", resolver=_resolver_for("93.184.216.34")
    )
    assert addresses == ("93.184.216.34",)


def test_rejects_cleartext_http_by_default():
    with pytest.raises(UnsafeOutboundURLError, match="must use HTTPS"):
        validate_outbound_url(
            "http://service.invalid/data", resolver=_resolver_for("93.184.216.34")
        )


def test_rejects_urls_with_embedded_credentials():
    with pytest.raises(UnsafeOutboundURLError, match="plain hostname"):
        validate_outbound_url(
            "https://user:password@service.invalid/data",
            resolver=_resolver_for("93.184.216.34"),
        )


@pytest.mark.parametrize(
    "value",
    [
        "..",
        "../admin",
        "..;matrix/admin",
        r"..\admin",
        "%2e%2e%2fadmin",
        "%252e%252e%252fadmin",
    ],
)
def test_rejects_traversal_shaped_path_segments(value: str):
    with pytest.raises(UnsafeOutboundPathError, match="dot segments"):
        encode_outbound_path_segment(value)


def test_path_segment_encoder_preserves_segment_boundary():
    assert encode_outbound_path_segment("abc/def") == "abc%2Fdef"


async def test_transport_connects_to_the_validated_address_once():
    resolutions = 0

    def resolver(host: str, port: int):
        nonlocal resolutions
        resolutions += 1
        address = "93.184.216.34" if resolutions == 1 else "127.0.0.1"
        return _resolver_for(address)(host, port)

    def handle(request):
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "service.invalid"
        assert request.extensions["sni_hostname"] == "service.invalid"
        return httpx.Response(200, json={"ok": True})

    transport = PinnedDNSAsyncTransport(
        resolver=resolver,
        transport=httpx.MockTransport(handle),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://service.invalid/data")

    assert response.json() == {"ok": True}
    assert resolutions == 1


async def test_transport_rejects_protected_address_before_inner_transport():
    called = False

    def handle(request):
        nonlocal called
        called = True
        return httpx.Response(200)

    transport = PinnedDNSAsyncTransport(
        resolver=_resolver_for("127.0.0.1"),
        transport=httpx.MockTransport(handle),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(UnsafeOutboundURLError, match="protected address"):
            await client.get("https://service.invalid/data")

    assert called is False


async def test_transport_falls_back_to_next_validated_address():
    def resolver(host: str, port: int):
        return [
            *list(_resolver_for("93.184.216.34")(host, port)),
            *list(_resolver_for("93.184.216.35")(host, port)),
        ]

    attempts: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        attempts.append(request.url.host)
        if request.url.host == "93.184.216.34":
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, json={"ok": True})

    transport = PinnedDNSAsyncTransport(
        resolver=resolver,
        transport=httpx.MockTransport(handle),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://service.invalid/data")

    assert response.json() == {"ok": True}
    assert attempts == ["93.184.216.34", "93.184.216.35"]


async def test_limited_reader_rejects_declared_oversize_response():
    response = httpx.Response(
        200,
        headers={"content-length": "11"},
        content=b"hello world",
    )
    with pytest.raises(OutboundResponseTooLargeError, match="10-byte limit"):
        await read_response_body_limited(response, max_bytes=10)


async def test_limited_reader_rejects_stream_without_content_length():
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"12345"
            yield b"67890"
            yield b"x"

    response = httpx.Response(200, stream=Stream())
    with pytest.raises(OutboundResponseTooLargeError, match="10-byte limit"):
        await read_response_body_limited(response, max_bytes=10)
