"""Tests for OpenAPI proxy egress restrictions."""

import socket

import pytest

from purecipher.outbound_security import UnsafeOutboundURLError, validate_outbound_url


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
    validate_outbound_url(
        "https://service.invalid/data", resolver=_resolver_for("93.184.216.34")
    )


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
