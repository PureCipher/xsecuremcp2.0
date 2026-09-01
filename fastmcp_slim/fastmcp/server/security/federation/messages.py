"""Authentication and replay protection for federation wire messages."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

FEDERATION_ID_HEADER = "X-Federation-Id"
FEDERATION_NONCE_HEADER = "X-Federation-Nonce"
FEDERATION_SIGNATURE_HEADER = "X-Federation-Signature"
FEDERATION_SIGNATURE_VERSION_HEADER = "X-Federation-Signature-Version"
FEDERATION_TIMESTAMP_HEADER = "X-Federation-Timestamp"
FEDERATION_SIGNATURE_VERSION = "2"
DEFAULT_MAX_FEDERATION_MESSAGE_BYTES = 256 * 1024
DEFAULT_FEDERATION_MESSAGE_MAX_AGE_SECONDS = 300
DEFAULT_FEDERATION_CLOCK_SKEW_SECONDS = 30

_NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
NonceFactory = Callable[[], str]
FederationSigningSecrets = bytes | str | Mapping[str, bytes | str]


class FederationMessageError(ValueError):
    """Raised when a federation message cannot be authenticated safely."""


class FederationReplayGuard:
    """Bounded, thread-safe nonce cache for recently accepted messages."""

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self._max_entries = max_entries
        self._seen: OrderedDict[tuple[str, str], float] = OrderedDict()
        self._lock = threading.Lock()

    def accept(
        self,
        federation_id: str,
        nonce: str,
        *,
        expires_at: float,
        now: float,
    ) -> bool:
        """Atomically reserve a nonce, returning false if it is a replay."""
        key = (federation_id, nonce)
        with self._lock:
            expired = [item for item, expiry in self._seen.items() if expiry <= now]
            for item in expired:
                self._seen.pop(item, None)
            if key in self._seen:
                return False
            if len(self._seen) >= self._max_entries:
                raise FederationMessageError(
                    "Federation replay cache capacity has been reached"
                )
            self._seen[key] = expires_at
            return True


def _default_nonce() -> str:
    return secrets.token_urlsafe(24)


def canonical_federation_body(payload: Mapping[str, Any]) -> bytes:
    """Serialize a federation payload deterministically for signing."""
    try:
        return json.dumps(
            dict(payload),
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FederationMessageError(
            "Federation payload must contain JSON-compatible data"
        ) from exc


def build_signed_federation_headers(
    body: bytes,
    *,
    federation_id: str,
    signing_secret: bytes | str,
    timestamp: int | None = None,
    nonce: str | None = None,
    nonce_factory: NonceFactory = _default_nonce,
) -> dict[str, str]:
    """Create authenticated headers for one canonical message body."""
    resolved_secret = _secret_bytes(signing_secret)
    resolved_federation_id = _required_text(federation_id, "federation_id")
    resolved_timestamp = int(time.time()) if timestamp is None else timestamp
    if type(resolved_timestamp) is not int or resolved_timestamp < 0:
        raise FederationMessageError("Federation timestamp must be a positive integer")
    resolved_nonce = nonce_factory() if nonce is None else nonce
    if type(resolved_nonce) is not str or not _NONCE_PATTERN.fullmatch(resolved_nonce):
        raise FederationMessageError("Federation nonce has an invalid format")

    timestamp_text = str(resolved_timestamp)
    signature = _signature(
        body,
        timestamp=timestamp_text,
        nonce=resolved_nonce,
        signing_secret=resolved_secret,
    )
    return {
        "Content-Type": "application/json",
        FEDERATION_ID_HEADER: resolved_federation_id,
        FEDERATION_NONCE_HEADER: resolved_nonce,
        FEDERATION_SIGNATURE_HEADER: f"sha256={signature}",
        FEDERATION_SIGNATURE_VERSION_HEADER: FEDERATION_SIGNATURE_VERSION,
        FEDERATION_TIMESTAMP_HEADER: timestamp_text,
    }


def verify_federation_message(
    body: bytes,
    headers: Mapping[str, str],
    *,
    signing_secrets: FederationSigningSecrets,
    replay_guard: FederationReplayGuard,
    max_age_seconds: int = DEFAULT_FEDERATION_MESSAGE_MAX_AGE_SECONDS,
    max_clock_skew_seconds: int = DEFAULT_FEDERATION_CLOCK_SKEW_SECONDS,
    max_message_bytes: int = DEFAULT_MAX_FEDERATION_MESSAGE_BYTES,
    federation_id_header: str = FEDERATION_ID_HEADER,
    now: float | None = None,
) -> dict[str, Any]:
    """Authenticate, freshness-check, and deserialize a federation message."""
    if type(body) is not bytes:
        raise FederationMessageError("Federation message body must be bytes")
    if max_message_bytes <= 0 or len(body) > max_message_bytes:
        raise FederationMessageError("Federation message exceeds its byte limit")
    if max_age_seconds <= 0 or max_clock_skew_seconds < 0:
        raise ValueError("Federation freshness limits are invalid")

    normalized_headers: dict[str, str] = {}
    for key, value in headers.items():
        if type(key) is not str or type(value) is not str:
            raise FederationMessageError("Federation headers must contain text")
        normalized_headers[key.lower()] = value
    federation_id = _required_header(normalized_headers, federation_id_header)
    nonce = _required_header(normalized_headers, FEDERATION_NONCE_HEADER)
    signature = _required_header(normalized_headers, FEDERATION_SIGNATURE_HEADER)
    timestamp_text = _required_header(normalized_headers, FEDERATION_TIMESTAMP_HEADER)
    version = _required_header(
        normalized_headers,
        FEDERATION_SIGNATURE_VERSION_HEADER,
    )
    if version != FEDERATION_SIGNATURE_VERSION:
        raise FederationMessageError("Unsupported federation signature version")
    if not _NONCE_PATTERN.fullmatch(nonce):
        raise FederationMessageError("Federation nonce has an invalid format")
    if not signature.startswith("sha256="):
        raise FederationMessageError("Federation signature has an invalid format")

    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise FederationMessageError("Federation timestamp is invalid") from exc
    resolved_now = time.time() if now is None else now
    age = resolved_now - timestamp
    if age > max_age_seconds:
        raise FederationMessageError("Federation message has expired")
    if age < -max_clock_skew_seconds:
        raise FederationMessageError("Federation message timestamp is in the future")

    expected = _signature(
        body,
        timestamp=timestamp_text,
        nonce=nonce,
        signing_secret=_secret_for_federation(signing_secrets, federation_id),
    )
    if not hmac.compare_digest(signature[7:], expected):
        raise FederationMessageError("Federation signature is invalid")

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FederationMessageError("Federation message is not valid JSON") from exc
    if type(payload) is not dict or any(type(key) is not str for key in payload):
        raise FederationMessageError("Federation payload must be a JSON object")
    payload_federation_id = payload.get("federation_id")
    if type(payload_federation_id) is not str or payload_federation_id != federation_id:
        raise FederationMessageError(
            "Federation header identity does not match the signed payload"
        )

    expires_at = timestamp + max_age_seconds + max_clock_skew_seconds
    if not replay_guard.accept(
        federation_id,
        nonce,
        expires_at=expires_at,
        now=resolved_now,
    ):
        raise FederationMessageError("Federation message nonce has already been used")
    return payload


def _signature(
    body: bytes,
    *,
    timestamp: str,
    nonce: str,
    signing_secret: bytes,
) -> str:
    signed = b".".join((timestamp.encode("ascii"), nonce.encode("ascii"), body))
    return hmac.new(signing_secret, signed, hashlib.sha256).hexdigest()


def _secret_bytes(value: bytes | str) -> bytes:
    secret = value.encode("utf-8") if type(value) is str else value
    if type(secret) is not bytes or not secret:
        raise FederationMessageError("Federation signing secret must not be empty")
    return secret


def _secret_for_federation(
    signing_secrets: FederationSigningSecrets,
    federation_id: str,
) -> bytes:
    if isinstance(signing_secrets, Mapping):
        secret = signing_secrets.get(federation_id)
        if secret is None:
            raise FederationMessageError(
                "Federation message authentication is not configured"
            )
        return _secret_bytes(secret)
    return _secret_bytes(signing_secrets)


def _required_header(headers: Mapping[str, str], name: str) -> str:
    value = headers.get(name.lower())
    if type(value) is not str or not value:
        raise FederationMessageError(f"Missing required federation header {name}")
    return value


def _required_text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise FederationMessageError(f"Federation {name} must not be empty")
    return value.strip()


__all__ = [
    "DEFAULT_FEDERATION_CLOCK_SKEW_SECONDS",
    "DEFAULT_FEDERATION_MESSAGE_MAX_AGE_SECONDS",
    "DEFAULT_MAX_FEDERATION_MESSAGE_BYTES",
    "FEDERATION_ID_HEADER",
    "FEDERATION_NONCE_HEADER",
    "FEDERATION_SIGNATURE_HEADER",
    "FEDERATION_SIGNATURE_VERSION",
    "FEDERATION_SIGNATURE_VERSION_HEADER",
    "FEDERATION_TIMESTAMP_HEADER",
    "FederationMessageError",
    "FederationReplayGuard",
    "FederationSigningSecrets",
    "build_signed_federation_headers",
    "canonical_federation_body",
    "verify_federation_message",
]
