"""HTTP boundary tests for signed federation revocation ingestion."""

from __future__ import annotations

from starlette.testclient import TestClient

from fastmcp import FastMCP
from fastmcp.server.security.federation.federation import TrustFederation
from fastmcp.server.security.federation.http import mount_federation_receiver
from fastmcp.server.security.federation.messages import (
    build_signed_federation_headers,
    canonical_federation_body,
)

_SECRET = "federation-http-test-secret"


def _mounted_client() -> tuple[TestClient, TrustFederation]:
    server = FastMCP("federation-receiver-test")
    federation = TrustFederation()
    federation.add_peer("Partner", peer_id="peer-1")
    mount_federation_receiver(
        server,
        federation,
        signing_secrets=_SECRET,
    )
    return TestClient(server.http_app(transport="streamable-http")), federation


def _signed_request(
    *,
    federation_id: str = "peer-1",
    tool_name: str = "revoked-tool",
) -> tuple[bytes, dict[str, str]]:
    body = canonical_federation_body(
        {
            "federation_id": federation_id,
            "tool_name": tool_name,
            "reason": "security_incident",
            "emergency": True,
        }
    )
    headers = build_signed_federation_headers(
        body,
        federation_id=federation_id,
        signing_secret=_SECRET,
    )
    return body, headers


def test_receiver_accepts_authenticated_fresh_revocation():
    client, federation = _mounted_client()
    body, headers = _signed_request()

    response = client.post(
        "/federation/revocations",
        content=body,
        headers=headers,
    )

    assert response.status_code == 202
    assert federation.local_crl.is_revoked("revoked-tool") is True


def test_receiver_rejects_tampered_body_without_changing_crl():
    client, federation = _mounted_client()
    body, headers = _signed_request()
    tampered = body.replace(b"revoked-tool", b"trusted-tool")

    response = client.post(
        "/federation/revocations",
        content=tampered,
        headers=headers,
    )

    assert response.status_code == 401
    assert federation.local_crl.entry_count == 0


def test_receiver_rejects_replayed_message():
    client, federation = _mounted_client()
    body, headers = _signed_request()
    first = client.post(
        "/federation/revocations",
        content=body,
        headers=headers,
    )

    second = client.post(
        "/federation/revocations",
        content=body,
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 401
    assert federation.local_crl.entry_count == 1


def test_receiver_rejects_authenticated_unknown_peer():
    client, federation = _mounted_client()
    body, headers = _signed_request(federation_id="unknown-peer")

    response = client.post(
        "/federation/revocations",
        content=body,
        headers=headers,
    )

    assert response.status_code == 403
    assert federation.local_crl.entry_count == 0


def test_receiver_rejects_oversized_body_before_authentication():
    server = FastMCP("bounded-federation-receiver")
    federation = TrustFederation()
    mount_federation_receiver(
        server,
        federation,
        signing_secrets=_SECRET,
        max_message_bytes=8,
    )
    client = TestClient(server.http_app(transport="streamable-http"))

    response = client.post(
        "/federation/revocations",
        content=b"more-than-eight-bytes",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_receiver_requires_json_content_type():
    client, federation = _mounted_client()

    response = client.post(
        "/federation/revocations",
        content=b"{}",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 415
    assert federation.local_crl.entry_count == 0
