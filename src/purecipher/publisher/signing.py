"""Local Ed25519 signing and registry key enrollment for publishers."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from purecipher.publisher.auth import normalize_base_url, resolve_registry_token
from purecipher.publisher_signing import (
    PublisherManifestSignature,
    canonical_json,
    canonicalize_public_key,
    manifest_signature_payload,
)
from purecipher.registry import _parse_manifest


@dataclass(frozen=True)
class PublisherKeyBindingResult:
    base_url: str
    key: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"base_url": self.base_url, "key": dict(self.key)}


def load_private_signing_key(path: str | Path) -> Ed25519PrivateKey:
    """Load an unencrypted, owner-only Ed25519 PEM private key."""

    key_path = Path(path).expanduser().resolve()
    try:
        stat = key_path.stat()
    except OSError as exc:
        raise ValueError(f"Could not read publisher signing key: {key_path}") from exc
    if os.name != "nt" and stat.st_mode & 0o077:
        raise ValueError(
            "Publisher signing key permissions are too broad; use chmod 600"
        )
    if stat.st_size > 16_384:
        raise ValueError("Publisher signing key file is too large")
    try:
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(
            "Provide an unencrypted Ed25519 private key in PEM format"
        ) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Only Ed25519 publisher signing keys are supported")
    return key


def canonicalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Resolve generated manifest fields once for stable preflight and submit."""

    return _parse_manifest(manifest).to_dict()


def sign_manifest(
    private_key: Ed25519PrivateKey,
    manifest: dict[str, Any],
) -> PublisherManifestSignature:
    """Create the detached signature accepted by PureCipher Registry."""

    parsed = _parse_manifest(manifest)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    _canonical, key_id, _public_key = canonicalize_public_key(public_pem)
    payload = canonical_json(manifest_signature_payload(parsed)).encode("utf-8")
    return PublisherManifestSignature(
        key_id=key_id,
        signature=base64.b64encode(private_key.sign(payload)).decode("ascii"),
    )


def _response_payload(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise ValueError(
            f"Registry request failed with status {response.status_code}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("Registry returned an invalid response")
    if response.status_code >= 400:
        error = payload.get("error")
        raise ValueError(
            str(error)
            if isinstance(error, str) and error
            else f"Registry request failed with status {response.status_code}"
        )
    return payload


def bind_signing_key(
    signing_key_path: str | Path,
    *,
    base_url: str,
    auth_file: str | Path | None = None,
    token: str | None = None,
    label: str = "",
    client: Any | None = None,
) -> PublisherKeyBindingResult:
    """Prove possession and bind a local public key to the publisher account."""

    private_key = load_private_signing_key(signing_key_path)
    normalized_base_url = normalize_base_url(base_url)
    resolved_token = resolve_registry_token(
        base_url=normalized_base_url,
        token=token,
        auth_file=auth_file,
    )
    headers = {"accept": "application/json"}
    if resolved_token:
        headers["authorization"] = f"Bearer {resolved_token}"
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    owns_client = client is None
    http_client = client or httpx.Client(
        base_url=normalized_base_url,
        headers=headers,
        timeout=15.0,
    )
    try:
        challenge_response = http_client.post(
            "/registry/workspace/publisher-identity/keys/challenges",
            json={"public_key_pem": public_pem, "label": label},
            headers=headers,
        )
        challenge_payload = _response_payload(challenge_response)
        challenge = challenge_payload.get("challenge")
        if not isinstance(challenge, dict):
            raise ValueError("Registry returned an invalid key challenge")
        challenge_id = challenge.get("challenge_id")
        canonical_payload = challenge.get("canonical_payload")
        if not isinstance(challenge_id, str) or not isinstance(
            canonical_payload, str
        ):
            raise ValueError("Registry returned an invalid key challenge")
        proof = base64.b64encode(
            private_key.sign(canonical_payload.encode("utf-8"))
        ).decode("ascii")
        completed_response = http_client.post(
            f"/registry/workspace/publisher-identity/keys/challenges/{challenge_id}/complete",
            json={"signature": proof},
            headers=headers,
        )
        completed = _response_payload(completed_response)
    finally:
        if owns_client:
            http_client.close()
    key = completed.get("key")
    if not isinstance(key, dict):
        raise ValueError("Registry returned an invalid signing-key binding")
    return PublisherKeyBindingResult(base_url=normalized_base_url, key=dict(key))


__all__ = [
    "PublisherKeyBindingResult",
    "bind_signing_key",
    "canonicalize_manifest",
    "load_private_signing_key",
    "sign_manifest",
]
