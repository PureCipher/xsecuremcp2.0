"""External domain-ownership proof for registered publisher accounts."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import dns.asyncresolver
import httpx
from psycopg.errors import UniqueViolation
from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole
from purecipher.outbound_security import (
    OutboundResponseTooLargeError,
    PinnedDNSAsyncTransport,
    UnsafeOutboundURLError,
    read_response_body_limited,
)

CHALLENGE_TTL = timedelta(hours=1)
VERIFICATION_TTL = timedelta(days=90)
MAX_ACTIVE_CHALLENGES = 10
MAX_VERIFICATION_ATTEMPTS = 5
PROOF_PREFIX = "purecipher-publisher-verification="


class DomainVerificationMethod(StrEnum):
    """Supported proofs of control over a publisher domain."""

    DNS_TXT = "dns_txt"
    HTTPS_WELL_KNOWN = "https_well_known"


class DomainProofError(ValueError):
    """Raised when a domain proof cannot be safely verified."""


DomainVerifier = Callable[[str, DomainVerificationMethod, str], Awaitable[None]]
DNSLookup = Callable[[str], Awaitable[Iterable[str]]]
HTTPSFetch = Callable[[str], Awaitable[str]]


def normalize_domain(value: Any) -> str:
    """Return a canonical ASCII domain suitable for external verification."""

    if not isinstance(value, str):
        raise ValueError("Provide a valid domain name")
    candidate = value.strip().rstrip(".").lower()
    if not candidate or len(candidate) > 253:
        raise ValueError("Provide a valid domain name")
    if any(character in candidate for character in "/:@\\\x00"):
        raise ValueError("Enter a domain name without a URL, path, port, or wildcard")
    try:
        domain = candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Provide a valid domain name") from exc
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        pass
    else:
        raise ValueError("Domain verification does not accept IP addresses")
    labels = domain.split(".")
    if len(labels) < 2 or len(labels[-1]) < 2:
        raise ValueError("Provide a registrable domain name")
    if any(
        not label
        or len(label) > 63
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("Provide a valid domain name")
    return domain


def proof_value(token: str) -> str:
    return f"{PROOF_PREFIX}{token}"


def challenge_instructions(
    domain: str,
    method: DomainVerificationMethod,
    token: str,
) -> dict[str, str]:
    expected = proof_value(token)
    if method is DomainVerificationMethod.DNS_TXT:
        return {
            "record_type": "TXT",
            "record_name": f"_purecipher-challenge.{domain}",
            "record_value": expected,
        }
    return {
        "url": f"https://{domain}/.well-known/purecipher-verification.txt",
        "body": expected,
    }


async def resolve_dns_txt(name: str) -> tuple[str, ...]:
    """Resolve TXT records without accepting search-domain expansion."""

    try:
        answer = await dns.asyncresolver.resolve(
            name.rstrip(".") + ".",
            "TXT",
            search=False,
            lifetime=5.0,
        )
    except Exception as exc:
        raise DomainProofError("The DNS proof record could not be resolved") from exc
    values: list[str] = []
    for record in answer:
        strings = getattr(record, "strings", ())
        try:
            value = b"".join(strings).decode("utf-8")
        except (AttributeError, UnicodeDecodeError, TypeError):
            continue
        values.append(value)
    return tuple(values)


async def fetch_https_proof(url: str) -> str:
    """Fetch a bounded HTTPS proof through the DNS-pinned outbound boundary."""

    transport = PinnedDNSAsyncTransport(resolver=_public_address_resolver)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
            timeout=httpx.Timeout(5.0),
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET",
                url,
                headers={"Accept": "text/plain"},
            ) as response:
                if response.status_code != 200:
                    raise DomainProofError(
                        "The HTTPS proof endpoint did not return status 200"
                    )
                body = await read_response_body_limited(response, max_bytes=4096)
    except DomainProofError:
        raise
    except (
        httpx.HTTPError,
        UnsafeOutboundURLError,
        OutboundResponseTooLargeError,
    ) as exc:
        raise DomainProofError(
            "The HTTPS proof endpoint could not be verified"
        ) from exc
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DomainProofError("The HTTPS proof must be UTF-8 text") from exc


def _public_address_resolver(host: str, port: int) -> list[tuple]:
    """Resolve only global addresses, ignoring proxy-specific private allowlists."""

    try:
        entries = list(socket.getaddrinfo(host, port))
    except OSError as exc:
        raise OSError(f"Could not resolve publisher proof host {host!r}") from exc
    if not entries:
        raise OSError(f"Could not resolve publisher proof host {host!r}")
    for entry in entries:
        try:
            address = ipaddress.ip_address(str(entry[4][0]))
        except (IndexError, TypeError, ValueError) as exc:
            raise OSError(
                "Resolver returned an invalid publisher proof address"
            ) from exc
        if not address.is_global:
            raise OSError("Publisher proof hosts must resolve only to public addresses")
    return entries


async def verify_domain_proof(
    domain: str,
    method: DomainVerificationMethod,
    token: str,
    *,
    dns_lookup: DNSLookup = resolve_dns_txt,
    https_fetch: HTTPSFetch = fetch_https_proof,
) -> None:
    """Verify that the challenge value is externally visible for ``domain``."""

    expected = proof_value(token)
    if method is DomainVerificationMethod.DNS_TXT:
        values = await dns_lookup(f"_purecipher-challenge.{domain}")
        if not any(hmac.compare_digest(value.strip(), expected) for value in values):
            raise DomainProofError("The DNS proof record is missing or does not match")
        return
    body = await https_fetch(
        f"https://{domain}/.well-known/purecipher-verification.txt"
    )
    if not hmac.compare_digest(body.strip(), expected):
        raise DomainProofError("The HTTPS proof body is missing or does not match")


def challenge_key(challenge_id: str) -> str:
    return f"publisher-domain-challenge-{challenge_id}"


def identity_key(domain: str) -> str:
    digest = hashlib.sha256(domain.encode("ascii")).hexdigest()
    return f"publisher-domain-identity-{digest}"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _is_current_identity(item: dict[str, Any], *, now: datetime) -> bool:
    expires_at = _parse_time(item.get("verification_expires_at"))
    return (
        item.get("kind") == "publisher-domain-identity"
        and item.get("status") == "verified"
        and expires_at is not None
        and expires_at > now
    )


def verified_publisher_identities(
    records: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Aggregate current internal proof records into safe public identity data."""

    resolved_now = now or datetime.now(UTC)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        owner = item.get("owner")
        domain = item.get("domain")
        if (
            not isinstance(owner, str)
            or not isinstance(domain, str)
            or not _is_current_identity(item, now=resolved_now)
        ):
            continue
        grouped.setdefault(owner, []).append(item)
    result: dict[str, dict[str, Any]] = {}
    for owner, items in grouped.items():
        verified_at = max(str(item.get("verified_at") or "") for item in items)
        result[owner] = {
            "domain_verified": True,
            "verified_domains": sorted({str(item["domain"]) for item in items}),
            "identity_verified_at": verified_at,
        }
    return result


def _response(payload: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


def _publisher_session(registry: Any, request: Any):
    session = registry._session_from_request(request)
    if session is None:
        return None, _response({"error": "Authentication required"}, 401)
    if session.role is not RegistryRole.PUBLISHER:
        return None, _response({"error": "Publisher account required"}, 403)
    return session, None


def _serialize_challenge(item: dict[str, Any]) -> dict[str, Any]:
    method = DomainVerificationMethod(item["method"])
    token = str(item.get("token") or "")
    payload = {
        "challenge_id": item["challenge_id"],
        "domain": item["domain"],
        "method": method.value,
        "status": item["status"],
        "created_at": item["created_at"],
        "expires_at": item["expires_at"],
        "attempts": item.get("attempts", 0),
    }
    if token and item["status"] == "pending":
        payload["instructions"] = challenge_instructions(item["domain"], method, token)
    return payload


def _serialize_identity(item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "domain": item["domain"],
        "status": item["status"],
        "verification_method": item["verification_method"],
        "verified_at": item.get("verified_at"),
        "verification_expires_at": item.get("verification_expires_at"),
    }
    if item.get("revoked_at"):
        payload["revoked_at"] = item["revoked_at"]
    return payload


def _active_challenge(item: dict[str, Any], *, now: datetime) -> bool:
    expires_at = _parse_time(item.get("expires_at"))
    return item.get("status") == "pending" and bool(expires_at and expires_at > now)


def _prune_expired_challenges(registry: Any, owner: str, *, now: datetime) -> None:
    for item in registry._workspace.list(owner, "publisher-domain-challenge"):
        expires_at = _parse_time(item.get("expires_at"))
        if expires_at is None or expires_at <= now:
            registry._workspace.delete(item)


async def _request_object(request: Any) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > 10_000:
        raise ValueError("Request is too large")
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("Request body must be an object")
    return body


def mount_publisher_identity(registry: Any, prefix: str) -> None:
    """Mount publisher and administrator routes for external identity proof."""

    base = f"{prefix}/workspace/publisher-identity"

    @registry.custom_route(base, methods=["GET"])
    async def identity_status(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        now = datetime.now(UTC)
        _prune_expired_challenges(registry, session.username, now=now)
        challenges = [
            _serialize_challenge(item)
            for item in registry._workspace.list(
                session.username, "publisher-domain-challenge"
            )
            if _active_challenge(item, now=now)
        ]
        identities = [
            _serialize_identity(item)
            for item in registry._workspace.list(
                session.username, "publisher-domain-identity"
            )
        ]
        identities.sort(key=lambda item: item["domain"])
        return _response(
            {
                "publisher_id": session.username,
                "domain_verified": any(
                    _is_current_identity(item, now=now)
                    for item in registry._workspace.list(
                        session.username, "publisher-domain-identity"
                    )
                ),
                "identities": identities,
                "challenges": challenges,
            }
        )

    @registry.custom_route(f"{base}/challenges", methods=["POST"])
    async def create_challenge(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        try:
            body = await _request_object(request)
            if set(body) - {"domain", "method"}:
                raise ValueError("Only domain and method may be provided")
            domain = normalize_domain(body.get("domain"))
            method = DomainVerificationMethod(body.get("method"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return _response({"error": str(exc)}, 400)
        now = datetime.now(UTC)
        _prune_expired_challenges(registry, session.username, now=now)
        active = [
            item
            for item in registry._workspace.list(
                session.username, "publisher-domain-challenge"
            )
            if _active_challenge(item, now=now)
        ]
        if len(active) >= MAX_ACTIVE_CHALLENGES:
            return _response({"error": "Too many active verification challenges"}, 429)
        if any(
            item.get("domain") == domain and item.get("method") == method.value
            for item in active
        ):
            return _response(
                {
                    "error": "An active challenge already exists for this domain and method"
                },
                409,
            )
        challenge_id = secrets.token_urlsafe(18)
        token = "pcpv1_" + secrets.token_urlsafe(32)
        record = {
            "id": challenge_key(challenge_id),
            "challenge_id": challenge_id,
            "owner": session.username,
            "kind": "publisher-domain-challenge",
            "domain": domain,
            "method": method.value,
            "token": token,
            "status": "pending",
            "attempts": 0,
            "created_at": now.isoformat(),
            "expires_at": (now + CHALLENGE_TTL).isoformat(),
        }
        try:
            saved = registry._workspace.save(record)
        except (ValueError, UniqueViolation):
            return _response({"error": "Could not create a unique challenge"}, 409)
        return _response({"challenge": _serialize_challenge(saved)}, 201)

    @registry.custom_route(
        f"{base}/challenges/{{challenge_id}}/verify",
        methods=["POST"],
    )
    async def verify_challenge(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        challenge_id = request.path_params.get("challenge_id", "")
        item = registry._workspace.get(challenge_key(challenge_id))
        if (
            item is None
            or item.get("owner") != session.username
            or item.get("kind") != "publisher-domain-challenge"
        ):
            return _response({"error": "Verification challenge not found"}, 404)
        now = datetime.now(UTC)
        if item.get("status") != "pending":
            return _response(
                {"error": "Verification challenge is no longer active"}, 409
            )
        if not _active_challenge(item, now=now):
            return _response({"error": "Verification challenge has expired"}, 410)
        if int(item.get("attempts", 0)) >= MAX_VERIFICATION_ATTEMPTS:
            return _response({"error": "Verification attempt limit reached"}, 429)
        method = DomainVerificationMethod(item["method"])
        try:
            await registry._publisher_domain_verifier(
                item["domain"], method, item["token"]
            )
        except DomainProofError as exc:
            item["attempts"] = int(item.get("attempts", 0)) + 1
            item["last_attempt_at"] = now.isoformat()
            try:
                registry._workspace.save(item, expected=item["revision"])
            except (ValueError, UniqueViolation):
                return _response(
                    {"error": "Challenge changed; reload and try again"}, 409
                )
            return _response({"error": str(exc)}, 422)

        current = registry._workspace.get(item["id"])
        if current is None or current.get("revision") != item.get("revision"):
            return _response({"error": "Challenge changed; reload and try again"}, 409)
        key = identity_key(item["domain"])
        existing = registry._workspace.get(key)
        if existing is not None and existing.get("status") == "revoked":
            return _response(
                {"error": "This domain was revoked by an administrator"}, 409
            )
        if (
            existing is not None
            and existing.get("owner") != session.username
            and _is_current_identity(existing, now=now)
        ):
            return _response(
                {"error": "This domain is already verified by another publisher"},
                409,
            )
        if existing is not None and existing.get("owner") != session.username:
            registry._workspace.delete(existing)
            existing = None
        identity = {
            "id": key,
            "owner": session.username,
            "kind": "publisher-domain-identity",
            "domain": item["domain"],
            "status": "verified",
            "verification_method": method.value,
            "verified_at": now.isoformat(),
            "verification_expires_at": (now + VERIFICATION_TTL).isoformat(),
            "proof_digest": hashlib.sha256(item["token"].encode()).hexdigest(),
        }
        try:
            saved_identity = registry._workspace.save(
                identity,
                expected=existing.get("revision") if existing else None,
            )
        except (ValueError, UniqueViolation):
            return _response({"error": "Verification state changed; reload"}, 409)
        # The durable identity retains a digest of the proof. Removing the
        # one-time challenge ensures its plaintext token is not kept after use.
        registry._workspace.delete(current)
        return _response({"identity": _serialize_identity(saved_identity)})

    @registry.custom_route(
        f"{base}/challenges/{{challenge_id}}",
        methods=["DELETE"],
    )
    async def cancel_challenge(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        challenge_id = request.path_params.get("challenge_id", "")
        item = registry._workspace.get(challenge_key(challenge_id))
        if (
            item is None
            or item.get("owner") != session.username
            or item.get("kind") != "publisher-domain-challenge"
        ):
            return _response({"error": "Verification challenge not found"}, 404)
        registry._workspace.delete(item)
        return _response({"deleted": True})

    @registry.custom_route(
        f"{prefix}/admin/publisher-identities/{{domain}}",
        methods=["POST"],
    )
    async def administer_identity(request):
        session = registry._session_from_request(request)
        if session is None:
            return _response({"error": "Authentication required"}, 401)
        if session.role is not RegistryRole.ADMIN:
            return _response({"error": "Administrator access required"}, 403)
        try:
            domain = normalize_domain(request.path_params.get("domain"))
            body = await _request_object(request)
            if set(body) - {"action", "reason"}:
                raise ValueError("Only action and reason may be provided")
            action = body.get("action")
            reason = body.get("reason", "")
            if action not in {"revoke", "require_reverification"}:
                raise ValueError("Choose revoke or require_reverification")
            if not isinstance(reason, str) or len(reason) > 1000:
                raise ValueError("Reason must be at most 1000 characters")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return _response({"error": str(exc)}, 400)
        item = registry._workspace.get(identity_key(domain))
        if item is None or item.get("kind") != "publisher-domain-identity":
            return _response({"error": "Verified domain not found"}, 404)
        now = datetime.now(UTC).isoformat()
        item["status"] = "revoked" if action == "revoke" else "reverification_required"
        event = "revoked" if action == "revoke" else "reverification_required"
        item[f"{event}_at"] = now
        item[f"{event}_by"] = session.username
        item[f"{event}_reason"] = reason.strip()
        try:
            saved = registry._workspace.save(item, expected=item["revision"])
        except (ValueError, UniqueViolation):
            return _response({"error": "Identity changed; reload and try again"}, 409)
        return _response({"identity": _serialize_identity(saved)})


__all__ = [
    "DomainProofError",
    "DomainVerificationMethod",
    "DomainVerifier",
    "challenge_instructions",
    "fetch_https_proof",
    "identity_key",
    "mount_publisher_identity",
    "normalize_domain",
    "proof_value",
    "resolve_dns_txt",
    "verified_publisher_identities",
    "verify_domain_proof",
]
