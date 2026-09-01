"""Authentication and replay regressions for federation wire messages."""

from __future__ import annotations

import json

import pytest

from fastmcp.server.security.federation.federation import TrustFederation
from fastmcp.server.security.federation.messages import (
    FEDERATION_ID_HEADER,
    FEDERATION_NONCE_HEADER,
    FEDERATION_TIMESTAMP_HEADER,
    FederationMessageError,
    FederationReplayGuard,
    build_signed_federation_headers,
    canonical_federation_body,
    verify_federation_message,
)

_SECRET = "federation-test-signing-secret"
_TIMESTAMP = 1_000
_NONCE = "n" * 24


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "federation_id": "peer-1",
        "tool_name": "revoked-tool",
        "attestation_id": "att-1",
        "reason": "security_incident",
        "emergency": True,
        "description": "compromised",
    }
    payload.update(overrides)
    return payload


def _signed_message(
    payload: dict[str, object] | None = None,
    *,
    nonce: str = _NONCE,
    timestamp: int = _TIMESTAMP,
) -> tuple[bytes, dict[str, str]]:
    resolved_payload = payload or _payload()
    body = canonical_federation_body(resolved_payload)
    headers = build_signed_federation_headers(
        body,
        federation_id=str(resolved_payload["federation_id"]),
        signing_secret=_SECRET,
        timestamp=timestamp,
        nonce=nonce,
    )
    return body, headers


def test_signed_message_round_trips_after_authentication():
    body, headers = _signed_message()

    verified = verify_federation_message(
        body,
        headers,
        signing_secrets=_SECRET,
        replay_guard=FederationReplayGuard(),
        now=_TIMESTAMP + 1,
    )

    assert verified == _payload()


def test_body_tampering_invalidates_signature():
    body, headers = _signed_message()
    tampered = body.replace(b"revoked-tool", b"trusted-tool")

    with pytest.raises(FederationMessageError, match="signature is invalid"):
        verify_federation_message(
            tampered,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            now=_TIMESTAMP + 1,
        )


@pytest.mark.parametrize(
    ("header", "value"),
    [
        (FEDERATION_TIMESTAMP_HEADER, str(_TIMESTAMP + 1)),
        (FEDERATION_NONCE_HEADER, "x" * 24),
    ],
)
def test_freshness_header_tampering_invalidates_signature(header: str, value: str):
    body, headers = _signed_message()
    headers[header] = value

    with pytest.raises(FederationMessageError, match="signature is invalid"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            now=_TIMESTAMP + 1,
        )


def test_expired_message_is_rejected_before_application():
    body, headers = _signed_message()

    with pytest.raises(FederationMessageError, match="expired"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            max_age_seconds=30,
            now=_TIMESTAMP + 31,
        )


def test_future_message_outside_clock_skew_is_rejected():
    body, headers = _signed_message(timestamp=_TIMESTAMP + 31)

    with pytest.raises(FederationMessageError, match="in the future"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            max_clock_skew_seconds=30,
            now=_TIMESTAMP,
        )


def test_repeated_nonce_is_rejected_as_replay():
    body, headers = _signed_message()
    replay_guard = FederationReplayGuard()
    verify_federation_message(
        body,
        headers,
        signing_secrets=_SECRET,
        replay_guard=replay_guard,
        now=_TIMESTAMP + 1,
    )

    with pytest.raises(FederationMessageError, match="already been used"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=replay_guard,
            now=_TIMESTAMP + 2,
        )


def test_replay_cache_fails_closed_at_capacity():
    replay_guard = FederationReplayGuard(max_entries=1)
    body, headers = _signed_message(nonce="a" * 24)
    verify_federation_message(
        body,
        headers,
        signing_secrets=_SECRET,
        replay_guard=replay_guard,
        now=_TIMESTAMP + 1,
    )
    second_body, second_headers = _signed_message(nonce="b" * 24)

    with pytest.raises(FederationMessageError, match="capacity"):
        verify_federation_message(
            second_body,
            second_headers,
            signing_secrets=_SECRET,
            replay_guard=replay_guard,
            now=_TIMESTAMP + 1,
        )


def test_header_identity_must_match_signed_payload():
    body, headers = _signed_message()
    headers[FEDERATION_ID_HEADER] = "peer-2"

    with pytest.raises(FederationMessageError, match="does not match"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            now=_TIMESTAMP + 1,
        )


def test_peer_specific_secret_binds_the_authenticated_identity():
    body, headers = _signed_message(_payload(federation_id="peer-2"))

    with pytest.raises(FederationMessageError, match="signature is invalid"):
        verify_federation_message(
            body,
            headers,
            signing_secrets={"peer-1": _SECRET, "peer-2": "peer-2-secret"},
            replay_guard=FederationReplayGuard(),
            now=_TIMESTAMP + 1,
        )


def test_peer_specific_secret_accepts_its_own_identity():
    body, headers = _signed_message()

    verified = verify_federation_message(
        body,
        headers,
        signing_secrets={"peer-1": _SECRET},
        replay_guard=FederationReplayGuard(),
        now=_TIMESTAMP + 1,
    )

    assert verified["federation_id"] == "peer-1"


def test_authenticated_payload_must_be_a_json_object():
    body = json.dumps(["not", "an", "object"]).encode()
    headers = build_signed_federation_headers(
        body,
        federation_id="peer-1",
        signing_secret=_SECRET,
        timestamp=_TIMESTAMP,
        nonce=_NONCE,
    )

    with pytest.raises(FederationMessageError, match="JSON object"):
        verify_federation_message(
            body,
            headers,
            signing_secrets=_SECRET,
            replay_guard=FederationReplayGuard(),
            now=_TIMESTAMP + 1,
        )


def test_receive_signed_revocation_applies_authenticated_peer_message():
    federation = TrustFederation()
    federation.add_peer("Partner", peer_id="peer-1")
    body, headers = _signed_message()

    entry = federation.receive_signed_revocation(
        body,
        headers,
        signing_secrets=_SECRET,
        now=_TIMESTAMP + 1,
    )

    assert entry is not None
    assert entry.tool_name == "revoked-tool"
    assert entry.revoked_by == "federation:peer-1"


def test_receive_signed_revocation_rejects_malformed_authenticated_schema():
    federation = TrustFederation()
    federation.add_peer("Partner", peer_id="peer-1")
    body, headers = _signed_message(_payload(emergency="yes"))

    with pytest.raises(FederationMessageError, match="must be boolean"):
        federation.receive_signed_revocation(
            body,
            headers,
            signing_secrets=_SECRET,
            now=_TIMESTAMP + 1,
        )
