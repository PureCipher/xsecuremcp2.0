"""Authenticated HTTP receiver for federation revocation messages."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse

from fastmcp.server.security.federation.federation import TrustFederation
from fastmcp.server.security.federation.messages import (
    DEFAULT_FEDERATION_CLOCK_SKEW_SECONDS,
    DEFAULT_FEDERATION_MESSAGE_MAX_AGE_SECONDS,
    DEFAULT_MAX_FEDERATION_MESSAGE_BYTES,
    FederationMessageError,
    FederationSigningSecrets,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def mount_federation_receiver(
    server: FastMCP,
    federation: TrustFederation,
    *,
    signing_secrets: FederationSigningSecrets,
    path: str = "/federation/revocations",
    max_age_seconds: int = DEFAULT_FEDERATION_MESSAGE_MAX_AGE_SECONDS,
    max_clock_skew_seconds: int = DEFAULT_FEDERATION_CLOCK_SKEW_SECONDS,
    max_message_bytes: int = DEFAULT_MAX_FEDERATION_MESSAGE_BYTES,
    federation_id_header: str = "X-Federation-Id",
) -> None:
    """Mount a bounded, signed revocation receiver on ``server``.

    This route intentionally uses federation HMAC authentication instead of the
    SecureMCP operator bearer-token gate. Every accepted body is signature,
    timestamp, nonce, schema, and peer-status checked before changing the CRL.
    """
    _validate_mount_options(
        signing_secrets=signing_secrets,
        path=path,
        max_age_seconds=max_age_seconds,
        max_clock_skew_seconds=max_clock_skew_seconds,
        max_message_bytes=max_message_bytes,
    )

    @server.custom_route(path, methods=["POST"])
    async def federation_revocation_endpoint(request: Request) -> JSONResponse:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
        if media_type.lower() != "application/json":
            return JSONResponse(
                {"error": "Federation messages require application/json"},
                status_code=415,
            )
        declared_length = _content_length(request)
        if declared_length is not None and declared_length > max_message_bytes:
            return JSONResponse(
                {"error": "Federation message exceeds its byte limit"},
                status_code=413,
            )

        body = await _read_body_limited(request, max_message_bytes=max_message_bytes)
        if body is None:
            return JSONResponse(
                {"error": "Federation message exceeds its byte limit"},
                status_code=413,
            )
        try:
            entry = federation.receive_signed_revocation(
                body,
                request.headers,
                signing_secrets=signing_secrets,
                max_age_seconds=max_age_seconds,
                max_clock_skew_seconds=max_clock_skew_seconds,
                max_message_bytes=max_message_bytes,
                federation_id_header=federation_id_header,
            )
        except FederationMessageError as exc:
            logger.warning("Rejected federation revocation message: %s", exc)
            return JSONResponse(
                {"error": "Federation message authentication failed"},
                status_code=401,
            )
        if entry is None:
            return JSONResponse(
                {"error": "Federation peer is not authorized"},
                status_code=403,
            )
        return JSONResponse(entry.to_dict(), status_code=202)


async def _read_body_limited(
    request: Request,
    *,
    max_message_bytes: int,
) -> bytes | None:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > max_message_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _validate_mount_options(
    *,
    signing_secrets: FederationSigningSecrets,
    path: str,
    max_age_seconds: int,
    max_clock_skew_seconds: int,
    max_message_bytes: int,
) -> None:
    _validate_signing_secrets(signing_secrets)
    if not path.startswith("/") or "?" in path or "#" in path:
        raise ValueError("Federation receiver path must be a plain absolute path")
    if max_age_seconds <= 0 or max_clock_skew_seconds < 0:
        raise ValueError("Federation freshness limits are invalid")
    if max_message_bytes <= 0:
        raise ValueError("max_message_bytes must be greater than zero")


def _validate_signing_secrets(signing_secrets: FederationSigningSecrets) -> None:
    if isinstance(signing_secrets, Mapping):
        if not signing_secrets:
            raise ValueError("signing_secrets must not be empty")
        values = signing_secrets.items()
    else:
        values = (("shared", signing_secrets),)
    for federation_id, secret_value in values:
        secret = (
            secret_value.encode("utf-8")
            if type(secret_value) is str
            else secret_value
        )
        if type(federation_id) is not str or not federation_id:
            raise ValueError("signing_secrets peer IDs must not be empty")
        if type(secret) is not bytes or not secret:
            raise ValueError("signing_secrets values must not be empty")


__all__ = ["mount_federation_receiver"]
