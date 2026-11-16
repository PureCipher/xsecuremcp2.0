"""Publisher signing-key enrollment and manifest-author verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from psycopg.errors import UniqueViolation
from starlette.responses import JSONResponse

from fastmcp.server.security.certification.manifest import SecurityManifest
from fastmcp.server.security.contracts.crypto import compute_digest
from purecipher.auth import RegistryRole
from purecipher.publisher_identity import verified_publisher_identities
from purecipher.publishers import publisher_id_from_author

KEY_CHALLENGE_TTL = timedelta(hours=1)
MAX_ACTIVE_KEYS = 5
MAX_ACTIVE_KEY_CHALLENGES = 10
MAX_KEY_CHALLENGE_ATTEMPTS = 5
KEY_ALGORITHM = "ed25519"
KEY_BINDING_SCHEMA = "purecipher.publisher-key-binding.v1"
MANIFEST_SIGNATURE_SCHEMA = "purecipher.manifest-author-signature.v1"
KEY_ID_PATTERN = re.compile(r"pcpk_[A-Za-z0-9_-]{43}")


@dataclass(frozen=True)
class PublisherManifestSignature:
    """Detached Ed25519 signature supplied with a publisher manifest."""

    key_id: str
    signature: str
    algorithm: str = KEY_ALGORITHM

    def to_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class PublisherAuthorVerification:
    """Result of applying the enrolled author-signature policy."""

    required: bool
    signature_supplied: bool
    verified: bool
    status: str
    manifest_digest: str
    key_id: str = ""
    verified_domains: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        return self.verified or (not self.required and not self.signature_supplied)

    @property
    def message(self) -> str:
        messages = {
            "not_enrolled": "Publisher author signing is not enrolled.",
            "signing_key_not_enrolled": (
                "The supplied publisher signature does not match an enrolled key."
            ),
            "no_active_signing_key": (
                "Publisher author signing is enrolled, but no active signing key is available."
            ),
            "signature_required": (
                "This publisher requires an Ed25519 manifest-author signature."
            ),
            "signing_key_inactive_or_unknown": (
                "The publisher signing key is inactive or unknown."
            ),
            "domain_verification_required": (
                "Renew the domain verification bound to this publisher signing key."
            ),
            "signature_invalid": "The publisher manifest-author signature is invalid.",
            "verified": "Publisher manifest author and signing key verified.",
            "not_applicable": "Publisher author signing does not apply to curator attestations.",
        }
        return messages.get(
            self.status, "Publisher author-signature verification failed."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "author_signature_required": self.required,
            "author_signature_supplied": self.signature_supplied,
            "author_signature_verified": self.verified,
            "author_signature_status": self.status,
            "manifest_digest": self.manifest_digest,
            "signing_key_id": self.key_id,
            "verified_domains": list(self.verified_domains),
        }


def canonical_json(payload: dict[str, Any]) -> str:
    """Return the exact UTF-8 JSON text publishers sign."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def manifest_signature_payload(manifest: SecurityManifest) -> dict[str, str]:
    """Bind a signature to the complete canonical manifest and its author."""

    return {
        "schema": MANIFEST_SIGNATURE_SCHEMA,
        "publisher_id": manifest.author,
        "manifest_digest": compute_digest(manifest.to_dict()),
    }


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("Provide a valid base64 Ed25519 signature")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Provide a valid base64 Ed25519 signature") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signatures must contain exactly 64 bytes")
    return decoded


def parse_publisher_manifest_signature(
    value: Any,
) -> PublisherManifestSignature | None:
    """Strictly parse an optional publisher signature from an HTTP body."""

    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "algorithm",
        "key_id",
        "signature",
    }:
        raise ValueError(
            "`publisher_signature` must contain algorithm, key_id, and signature"
        )
    algorithm = value.get("algorithm")
    key_id = value.get("key_id")
    signature = value.get("signature")
    if algorithm != KEY_ALGORITHM:
        raise ValueError("`publisher_signature.algorithm` must be `ed25519`")
    if not isinstance(key_id, str) or KEY_ID_PATTERN.fullmatch(key_id) is None:
        raise ValueError("`publisher_signature.key_id` is invalid")
    _decode_signature(signature)
    return PublisherManifestSignature(
        key_id=key_id,
        signature=signature,
        algorithm=algorithm,
    )


def canonicalize_public_key(value: Any) -> tuple[str, str, Ed25519PublicKey]:
    """Validate and canonicalize one Ed25519 SubjectPublicKeyInfo PEM."""

    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Provide an Ed25519 public key in PEM format")
    try:
        key = serialization.load_pem_public_key(value.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("Provide an Ed25519 public key in PEM format") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Only Ed25519 publisher signing keys are supported")
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    canonical_pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    fingerprint = (
        base64.urlsafe_b64encode(hashlib.sha256(der).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return canonical_pem, f"pcpk_{fingerprint}", key


def key_binding_payload(
    *,
    publisher_id: str,
    key_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, str]:
    return {
        "schema": KEY_BINDING_SCHEMA,
        "publisher_id": publisher_id,
        "key_id": key_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def signing_key_record_id(key_id: str) -> str:
    return f"publisher-signing-key-{key_id}"


def key_challenge_record_id(challenge_id: str) -> str:
    return f"publisher-key-challenge-{challenge_id}"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _current_domains(registry: Any, owner: str) -> tuple[str, ...]:
    identities = verified_publisher_identities(
        registry._workspace.list_kind("publisher-domain-identity")
    )
    details = identities.get(owner, {})
    domains = details.get("verified_domains", [])
    if not isinstance(domains, list):
        return ()
    return tuple(sorted(domain for domain in domains if isinstance(domain, str)))


def _key_current_domains(
    record: dict[str, Any],
    current_domains: tuple[str, ...],
) -> tuple[str, ...]:
    bound = record.get("verified_domains", [])
    if not isinstance(bound, list):
        return ()
    return tuple(sorted(set(current_domains) & {str(domain) for domain in bound}))


def _active_key_records(registry: Any, owner: str) -> list[dict[str, Any]]:
    return [
        item
        for item in registry._workspace.list(owner, "publisher-signing-key")
        if item.get("status") == "active"
    ]


def verify_publisher_author_signature(
    registry: Any,
    manifest: SecurityManifest,
    signature: PublisherManifestSignature | None,
) -> PublisherAuthorVerification:
    """Apply permanent opt-in author-signature enforcement for a manifest."""

    digest = compute_digest(manifest.to_dict())
    enrolled = registry._workspace.list(manifest.author, "publisher-signing-key")
    required = bool(enrolled)
    supplied = signature is not None
    if not required and signature is None:
        return PublisherAuthorVerification(
            required=False,
            signature_supplied=False,
            verified=False,
            status="not_enrolled",
            manifest_digest=digest,
        )
    if not required:
        return PublisherAuthorVerification(
            required=False,
            signature_supplied=True,
            verified=False,
            status="signing_key_not_enrolled",
            manifest_digest=digest,
            key_id=signature.key_id if signature else "",
        )
    active = _active_key_records(registry, manifest.author)
    if not active:
        return PublisherAuthorVerification(
            required=True,
            signature_supplied=supplied,
            verified=False,
            status="no_active_signing_key",
            manifest_digest=digest,
            key_id=signature.key_id if signature else "",
        )
    if signature is None:
        return PublisherAuthorVerification(
            required=True,
            signature_supplied=False,
            verified=False,
            status="signature_required",
            manifest_digest=digest,
        )
    record = next(
        (item for item in active if item.get("key_id") == signature.key_id), None
    )
    if record is None:
        return PublisherAuthorVerification(
            required=True,
            signature_supplied=True,
            verified=False,
            status="signing_key_inactive_or_unknown",
            manifest_digest=digest,
            key_id=signature.key_id,
        )
    domains = _key_current_domains(record, _current_domains(registry, manifest.author))
    if not domains:
        return PublisherAuthorVerification(
            required=True,
            signature_supplied=True,
            verified=False,
            status="domain_verification_required",
            manifest_digest=digest,
            key_id=signature.key_id,
        )
    try:
        _canonical, derived_key_id, key = canonicalize_public_key(
            record.get("public_key_pem")
        )
        if derived_key_id != signature.key_id:
            raise ValueError("Stored publisher key fingerprint does not match")
        key.verify(
            _decode_signature(signature.signature),
            canonical_json(manifest_signature_payload(manifest)).encode("utf-8"),
        )
    except (InvalidSignature, ValueError):
        return PublisherAuthorVerification(
            required=True,
            signature_supplied=True,
            verified=False,
            status="signature_invalid",
            manifest_digest=digest,
            key_id=signature.key_id,
        )
    return PublisherAuthorVerification(
        required=True,
        signature_supplied=True,
        verified=True,
        status="verified",
        manifest_digest=digest,
        key_id=signature.key_id,
        verified_domains=domains,
    )


def validate_stored_publisher_identity(
    registry: Any,
    *,
    author: str,
    manifest: SecurityManifest | dict[str, Any] | None,
    metadata: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Re-check enrolled identity evidence before delayed approval."""

    enrolled = registry._workspace.list(author, "publisher-signing-key")
    if not enrolled:
        return True, "Publisher author signing is not enrolled."
    evidence = (metadata or {}).get("publisher_identity")
    if (
        not isinstance(evidence, dict)
        or evidence.get("author_signature_verified") is not True
    ):
        return False, "The staged listing has no verified publisher author signature."
    key_id = evidence.get("signing_key_id")
    if not isinstance(key_id, str):
        return False, "The staged publisher signing key is invalid."
    record = registry._workspace.get(signing_key_record_id(key_id))
    if (
        not isinstance(record, dict)
        or record.get("owner") != author
        or record.get("kind") != "publisher-signing-key"
        or record.get("status") != "active"
    ):
        return False, "The staged publisher signing key is no longer active."
    current_domains = _key_current_domains(record, _current_domains(registry, author))
    if not current_domains:
        return False, "The staged publisher key no longer has current domain proof."
    if isinstance(manifest, SecurityManifest):
        manifest_data = manifest.to_dict()
    elif isinstance(manifest, dict):
        manifest_data = manifest
    else:
        return False, "The staged publisher manifest is unavailable."
    if manifest_data.get("author") != author:
        return False, "The staged manifest author does not match the publisher."
    digest = compute_digest(manifest_data)
    if evidence.get("manifest_digest") != digest:
        return False, "The staged publisher signature does not match the manifest."
    evidence_domains = evidence.get("verified_domains", [])
    if not isinstance(evidence_domains, list) or not (
        set(current_domains) & {str(domain) for domain in evidence_domains}
    ):
        return False, "The staged publisher signature has no current domain binding."
    return True, "Publisher manifest author and signing key remain verified."


def public_signing_bindings(
    records: list[dict[str, Any]],
    domain_identities: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate current key bindings into safe public publisher fields."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        owner = record.get("owner")
        if (
            isinstance(owner, str)
            and record.get("kind") == "publisher-signing-key"
            and record.get("status") == "active"
        ):
            grouped.setdefault(owner, []).append(record)
    result: dict[str, dict[str, Any]] = {}
    for owner, keys in grouped.items():
        details = domain_identities.get(owner, {})
        domains = details.get("verified_domains", [])
        current_domains = tuple(domains) if isinstance(domains, list) else ()
        valid_keys = [
            item for item in keys if _key_current_domains(item, current_domains)
        ]
        if valid_keys:
            result[owner] = {
                "signing_key_bound": True,
                "signing_key_ids": sorted(str(item["key_id"]) for item in valid_keys),
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


async def _request_object(request: Any) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > 20_000:
        raise ValueError("Request is too large")
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("Request body must be an object")
    return body


def _serialize_key(
    record: dict[str, Any], *, include_public_key: bool
) -> dict[str, Any]:
    payload = {
        "key_id": record["key_id"],
        "algorithm": record["algorithm"],
        "label": record.get("label", ""),
        "status": record["status"],
        "verified_domains": list(record.get("verified_domains", [])),
        "activated_at": record.get("activated_at"),
    }
    if include_public_key:
        payload["public_key_pem"] = record["public_key_pem"]
    if record.get("revoked_at"):
        payload["revoked_at"] = record["revoked_at"]
    return payload


def _challenge_active(record: dict[str, Any], *, now: datetime) -> bool:
    expires_at = _parse_time(record.get("expires_at"))
    return record.get("status") == "pending" and bool(expires_at and expires_at > now)


def _prune_key_challenges(registry: Any, owner: str, *, now: datetime) -> None:
    for record in registry._workspace.list(owner, "publisher-key-challenge"):
        if not _challenge_active(record, now=now):
            registry._workspace.delete(record)


def _serialize_challenge(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "challenge_id": record["challenge_id"],
        "key_id": record["key_id"],
        "algorithm": KEY_ALGORITHM,
        "label": record.get("label", ""),
        "payload": dict(record["payload"]),
        "canonical_payload": record["canonical_payload"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "attempts": record.get("attempts", 0),
    }


def mount_publisher_signing(registry: Any, prefix: str) -> None:
    """Mount key enrollment, revocation, and public key-discovery routes."""

    base = f"{prefix}/workspace/publisher-identity/keys"

    @registry.custom_route(base, methods=["GET"])
    async def list_signing_keys(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        now = datetime.now(UTC)
        _prune_key_challenges(registry, session.username, now=now)
        keys = [
            _serialize_key(item, include_public_key=True)
            for item in registry._workspace.list(
                session.username, "publisher-signing-key"
            )
        ]
        challenges = [
            _serialize_challenge(item)
            for item in registry._workspace.list(
                session.username, "publisher-key-challenge"
            )
            if _challenge_active(item, now=now)
        ]
        return _response(
            {
                "publisher_id": publisher_id_from_author(session.username),
                "signing_required": bool(keys),
                "keys": keys,
                "challenges": challenges,
            }
        )

    @registry.custom_route(f"{base}/challenges", methods=["POST"])
    async def create_key_challenge(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        try:
            body = await _request_object(request)
            if set(body) - {"public_key_pem", "label"}:
                raise ValueError("Only public_key_pem and label may be provided")
            canonical_pem, key_id, _key = canonicalize_public_key(
                body.get("public_key_pem")
            )
            label = body.get("label", "")
            if not isinstance(label, str) or len(label) > 120:
                raise ValueError("Key label must be at most 120 characters")
            label = label.strip()
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return _response({"error": str(exc)}, 400)
        domains = _current_domains(registry, session.username)
        if not domains:
            return _response(
                {"error": "Verify a publisher domain before binding a signing key"},
                409,
            )
        existing = registry._workspace.get(signing_key_record_id(key_id))
        if existing is not None:
            return _response(
                {"error": "This signing key has already been enrolled or revoked"},
                409,
            )
        now = datetime.now(UTC)
        _prune_key_challenges(registry, session.username, now=now)
        active_keys = _active_key_records(registry, session.username)
        if len(active_keys) >= MAX_ACTIVE_KEYS:
            return _response({"error": "Active signing key limit reached"}, 429)
        challenges = registry._workspace.list(
            session.username, "publisher-key-challenge"
        )
        if len(challenges) >= MAX_ACTIVE_KEY_CHALLENGES:
            return _response({"error": "Too many active signing-key challenges"}, 429)
        if any(item.get("key_id") == key_id for item in challenges):
            return _response(
                {"error": "An active challenge already exists for this signing key"},
                409,
            )
        challenge_id = secrets.token_urlsafe(18)
        created_at = now.isoformat()
        expires_at = (now + KEY_CHALLENGE_TTL).isoformat()
        payload = key_binding_payload(
            publisher_id=session.username,
            key_id=key_id,
            nonce=secrets.token_urlsafe(32),
            issued_at=created_at,
            expires_at=expires_at,
        )
        record = {
            "id": key_challenge_record_id(challenge_id),
            "challenge_id": challenge_id,
            "owner": session.username,
            "kind": "publisher-key-challenge",
            "key_id": key_id,
            "algorithm": KEY_ALGORITHM,
            "public_key_pem": canonical_pem,
            "label": label,
            "payload": payload,
            "canonical_payload": canonical_json(payload),
            "status": "pending",
            "attempts": 0,
            "created_at": created_at,
            "expires_at": expires_at,
        }
        try:
            saved = registry._workspace.save(record)
        except (ValueError, UniqueViolation):
            return _response({"error": "Could not create a unique key challenge"}, 409)
        return _response({"challenge": _serialize_challenge(saved)}, 201)

    @registry.custom_route(
        f"{base}/challenges/{{challenge_id}}/complete",
        methods=["POST"],
    )
    async def complete_key_challenge(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        challenge_id = request.path_params.get("challenge_id", "")
        record = registry._workspace.get(key_challenge_record_id(challenge_id))
        if (
            record is None
            or record.get("owner") != session.username
            or record.get("kind") != "publisher-key-challenge"
        ):
            return _response({"error": "Signing-key challenge not found"}, 404)
        now = datetime.now(UTC)
        if not _challenge_active(record, now=now):
            return _response({"error": "Signing-key challenge has expired"}, 410)
        if int(record.get("attempts", 0)) >= MAX_KEY_CHALLENGE_ATTEMPTS:
            return _response({"error": "Signing-key attempt limit reached"}, 429)
        try:
            body = await _request_object(request)
            if set(body) != {"signature"}:
                raise ValueError("Provide only the challenge signature")
            signature = _decode_signature(body.get("signature"))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return _response({"error": str(exc)}, 400)
        try:
            _canonical, derived_key_id, key = canonicalize_public_key(
                record.get("public_key_pem")
            )
            if derived_key_id != record.get("key_id"):
                raise ValueError("Challenge key fingerprint changed")
            key.verify(signature, record["canonical_payload"].encode("utf-8"))
        except (InvalidSignature, ValueError):
            record["attempts"] = int(record.get("attempts", 0)) + 1
            record["last_attempt_at"] = now.isoformat()
            try:
                registry._workspace.save(record, expected=record["revision"])
            except (ValueError, UniqueViolation):
                return _response({"error": "Challenge changed; reload"}, 409)
            return _response({"error": "Signing-key proof is invalid"}, 422)
        domains = _current_domains(registry, session.username)
        if not domains:
            return _response(
                {"error": "Publisher domain verification is no longer current"},
                409,
            )
        if len(_active_key_records(registry, session.username)) >= MAX_ACTIVE_KEYS:
            return _response({"error": "Active signing key limit reached"}, 429)
        current = registry._workspace.get(record["id"])
        if current is None or current.get("revision") != record.get("revision"):
            return _response({"error": "Challenge changed; reload"}, 409)
        key_record = {
            "id": signing_key_record_id(record["key_id"]),
            "owner": session.username,
            "kind": "publisher-signing-key",
            "key_id": record["key_id"],
            "algorithm": KEY_ALGORITHM,
            "public_key_pem": record["public_key_pem"],
            "label": record.get("label", ""),
            "status": "active",
            "verified_domains": list(domains),
            "activated_at": now.isoformat(),
        }
        try:
            saved = registry._workspace.save(key_record)
        except (ValueError, UniqueViolation):
            return _response({"error": "Signing key was enrolled concurrently"}, 409)
        registry._workspace.delete(current)
        return _response({"key": _serialize_key(saved, include_public_key=True)}, 201)

    @registry.custom_route(f"{base}/{{key_id}}", methods=["POST"])
    async def revoke_signing_key(request):
        session, error = _publisher_session(registry, request)
        if error is not None:
            return error
        key_id = request.path_params.get("key_id", "")
        if KEY_ID_PATTERN.fullmatch(key_id) is None:
            return _response({"error": "Signing key not found"}, 404)
        record = registry._workspace.get(signing_key_record_id(key_id))
        if (
            record is None
            or record.get("owner") != session.username
            or record.get("kind") != "publisher-signing-key"
        ):
            return _response({"error": "Signing key not found"}, 404)
        try:
            body = await _request_object(request)
            if set(body) - {"action", "reason"} or body.get("action") != "revoke":
                raise ValueError("Choose the revoke action")
            reason = body.get("reason", "")
            if not isinstance(reason, str) or len(reason) > 1000:
                raise ValueError("Reason must be at most 1000 characters")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return _response({"error": str(exc)}, 400)
        if record.get("status") == "revoked":
            return _response({"key": _serialize_key(record, include_public_key=True)})
        record["status"] = "revoked"
        record["revoked_at"] = datetime.now(UTC).isoformat()
        record["revoked_by"] = session.username
        record["revocation_reason"] = reason.strip()
        try:
            saved = registry._workspace.save(record, expected=record["revision"])
        except (ValueError, UniqueViolation):
            return _response({"error": "Signing key changed; reload"}, 409)
        return _response({"key": _serialize_key(saved, include_public_key=True)})

    @registry.custom_route(
        f"{prefix}/publishers/{{publisher_id}}/signing-keys", methods=["GET"]
    )
    async def public_signing_keys(request):
        publisher_id = request.path_params.get("publisher_id", "")
        owners = {
            publisher_id_from_author(username): username
            for username in registry._registered_publisher_names()
        }
        owner = owners.get(publisher_id)
        if owner is None:
            return _response({"error": "Publisher not found", "status": 404}, 404)
        domains = _current_domains(registry, owner)
        keys = [
            _serialize_key(item, include_public_key=True)
            for item in _active_key_records(registry, owner)
            if _key_current_domains(item, domains)
        ]
        return _response(
            {
                "publisher_id": publisher_id,
                "count": len(keys),
                "keys": keys,
            }
        )


__all__ = [
    "KEY_ALGORITHM",
    "MANIFEST_SIGNATURE_SCHEMA",
    "PublisherAuthorVerification",
    "PublisherManifestSignature",
    "canonical_json",
    "canonicalize_public_key",
    "key_binding_payload",
    "manifest_signature_payload",
    "mount_publisher_signing",
    "parse_publisher_manifest_signature",
    "public_signing_bindings",
    "signing_key_record_id",
    "validate_stored_publisher_identity",
    "verify_publisher_author_signature",
]
