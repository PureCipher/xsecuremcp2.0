"""Publisher key binding and manifest-author signature contracts."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.testclient import TestClient

from purecipher import ManualReviewMode
from purecipher.publisher_identity import identity_key
from purecipher.publisher_signing import (
    PublisherManifestSignature,
    canonical_json,
    canonicalize_public_key,
    manifest_signature_payload,
    parse_publisher_manifest_signature,
)
from purecipher.release_candidates import decide
from purecipher.workspace import WorkspaceStore
from tests.server.security.test_publisher_drafts import login
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_purecipher_registry import _manifest

IDENTITY = "/registry/workspace/publisher-identity"
KEYS = f"{IDENTITY}/keys"


def _public_pem(private_key: Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )


def _signature(private_key: Ed25519PrivateKey, manifest) -> dict[str, str]:
    payload = canonical_json(manifest_signature_payload(manifest)).encode("utf-8")
    _pem, key_id, _key = canonicalize_public_key(_public_pem(private_key))
    return PublisherManifestSignature(
        key_id=key_id,
        signature=base64.b64encode(private_key.sign(payload)).decode("ascii"),
    ).to_dict()


def _verify_domain(client: TestClient, app, domain: str = "example.com") -> None:
    async def verifier(_domain, _method, _token):
        return None

    app._publisher_domain_verifier = verifier
    challenge_response = client.post(
        f"{IDENTITY}/challenges",
        json={"domain": domain, "method": "dns_txt"},
    )
    assert challenge_response.status_code == 201, challenge_response.text
    challenge_id = challenge_response.json()["challenge"]["challenge_id"]
    response = client.post(f"{IDENTITY}/challenges/{challenge_id}/verify")
    assert response.status_code == 200, response.text


def _bind_key(
    client: TestClient,
    private_key: Ed25519PrivateKey,
    *,
    label: str = "Release signing key",
) -> dict:
    challenge_response = client.post(
        f"{KEYS}/challenges",
        json={"public_key_pem": _public_pem(private_key), "label": label},
    )
    assert challenge_response.status_code == 201, challenge_response.text
    challenge = challenge_response.json()["challenge"]
    proof = base64.b64encode(
        private_key.sign(challenge["canonical_payload"].encode("utf-8"))
    ).decode("ascii")
    completed = client.post(
        f"{KEYS}/challenges/{challenge['challenge_id']}/complete",
        json={"signature": proof},
    )
    assert completed.status_code == 201, completed.text
    return completed.json()["key"]


def test_key_binding_requires_current_domain_and_proof_of_possession():
    app = registry()
    private_key = Ed25519PrivateKey.generate()
    with TestClient(app.http_app()) as client:
        login(client)
        no_domain = client.post(
            f"{KEYS}/challenges",
            json={"public_key_pem": _public_pem(private_key)},
        )
        assert no_domain.status_code == 409
        assert "Verify a publisher domain" in no_domain.json()["error"]

        _verify_domain(client, app)
        challenge_response = client.post(
            f"{KEYS}/challenges",
            json={"public_key_pem": _public_pem(private_key), "label": "Primary"},
        )
        challenge = challenge_response.json()["challenge"]
        assert challenge["algorithm"] == "ed25519"
        assert challenge["payload"]["publisher_id"] == "alice"
        assert challenge["canonical_payload"] == canonical_json(challenge["payload"])

        wrong = Ed25519PrivateKey.generate().sign(
            challenge["canonical_payload"].encode("utf-8")
        )
        rejected = client.post(
            f"{KEYS}/challenges/{challenge['challenge_id']}/complete",
            json={"signature": base64.b64encode(wrong).decode("ascii")},
        )
        assert rejected.status_code == 422
        assert client.get(KEYS).json()["challenges"][0]["attempts"] == 1

        proof = private_key.sign(challenge["canonical_payload"].encode("utf-8"))
        completed = client.post(
            f"{KEYS}/challenges/{challenge['challenge_id']}/complete",
            json={"signature": base64.b64encode(proof).decode("ascii")},
        )
        assert completed.status_code == 201, completed.text
        key = completed.json()["key"]
        assert key["status"] == "active"
        assert key["verified_domains"] == ["example.com"]
        assert client.get(KEYS).json()["signing_required"] is True

        profile = client.get("/registry/publishers/alice").json()
        assert profile["signing_key_bound"] is True
        assert profile["signing_key_ids"] == [key["key_id"]]
        assert "public_key_pem" not in profile
        public_keys = client.get("/registry/publishers/alice/signing-keys").json()
        assert public_keys["count"] == 1
        assert public_keys["keys"][0]["public_key_pem"] == _public_pem(private_key)
        html = client.get("/registry/publishers/alice?view=html")
        assert "Manifest author signing enabled" in html.text


def test_manifest_signature_is_required_verified_and_manifest_bound():
    app = registry()
    private_key = Ed25519PrivateKey.generate()
    manifest = _manifest(author="alice", tool_name="alice-signed-tool")
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app)
        key = _bind_key(client, private_key)

        unsigned = client.post(
            "/registry/preflight", json={"manifest": manifest.to_dict()}
        )
        assert unsigned.status_code == 200
        assert unsigned.json()["ready_for_publish"] is False
        assert unsigned.json()["publisher_identity"]["author_signature_status"] == (
            "signature_required"
        )

        signature = _signature(private_key, manifest)
        preflight = client.post(
            "/registry/preflight",
            json={"manifest": manifest.to_dict(), "publisher_signature": signature},
        )
        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["ready_for_publish"] is True
        identity = preflight.json()["publisher_identity"]
        assert identity["author_signature_verified"] is True
        assert identity["signing_key_id"] == key["key_id"]
        assert identity["verified_domains"] == ["example.com"]

        tampered = _manifest(
            author="alice",
            tool_name="alice-signed-tool",
            description="Changed after signing",
        )
        rejected = client.post(
            "/registry/preflight",
            json={"manifest": tampered.to_dict(), "publisher_signature": signature},
        )
        assert rejected.json()["ready_for_publish"] is False
        assert rejected.json()["publisher_identity"]["author_signature_status"] == (
            "signature_invalid"
        )

        submitted = client.post(
            "/registry/submit",
            json={
                "manifest": manifest.to_dict(),
                "publisher_signature": signature,
                "metadata": {
                    "publisher_identity": {
                        "author_signature_verified": False,
                        "signing_key_id": "attacker-controlled",
                    }
                },
            },
        )
        assert submitted.status_code == 201, submitted.text
        listing = app._marketplace().get_by_name("alice-signed-tool")
        stored_identity = listing.metadata["publisher_identity"]
        assert stored_identity["author_signature_verified"] is True
        assert stored_identity["signing_key_id"] == key["key_id"]
        assert "signature" not in stored_identity
        assert "attacker-controlled" not in submitted.text


def test_key_rotation_revocation_and_domain_expiry_prevent_downgrade():
    app = registry()
    old_key = Ed25519PrivateKey.generate()
    new_key = Ed25519PrivateKey.generate()
    manifest = _manifest(author="alice", tool_name="rotated-signed-tool")
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app)
        old = _bind_key(client, old_key, label="Old")
        new = _bind_key(client, new_key, label="New")

        revoked = client.post(
            f"{KEYS}/{old['key_id']}",
            json={"action": "revoke", "reason": "Rotated"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["key"]["status"] == "revoked"

        old_signature = _signature(old_key, manifest)
        old_result = client.post(
            "/registry/preflight",
            json={"manifest": manifest.to_dict(), "publisher_signature": old_signature},
        ).json()
        assert old_result["ready_for_publish"] is False
        assert old_result["publisher_identity"]["author_signature_status"] == (
            "signing_key_inactive_or_unknown"
        )

        new_signature = _signature(new_key, manifest)
        assert (
            client.post(
                "/registry/preflight",
                json={
                    "manifest": manifest.to_dict(),
                    "publisher_signature": new_signature,
                },
            ).json()["ready_for_publish"]
            is True
        )

        client.post(
            f"{KEYS}/{new['key_id']}",
            json={"action": "revoke", "reason": "Compromised"},
        )
        no_downgrade = client.post(
            "/registry/preflight", json={"manifest": manifest.to_dict()}
        ).json()
        assert no_downgrade["ready_for_publish"] is False
        assert no_downgrade["publisher_identity"]["author_signature_status"] == (
            "no_active_signing_key"
        )

        reuse = client.post(
            f"{KEYS}/challenges",
            json={"public_key_pem": _public_pem(old_key)},
        )
        assert reuse.status_code == 409
        assert "revoked" in reuse.json()["error"]

        replacement = Ed25519PrivateKey.generate()
        active = _bind_key(client, replacement, label="Replacement")
        identity = app._workspace.get(identity_key("example.com"))
        identity["verification_expires_at"] = (
            datetime.now(UTC) - timedelta(seconds=1)
        ).isoformat()
        app._workspace.save(identity, expected=identity["revision"])
        expired = client.post(
            "/registry/preflight",
            json={
                "manifest": manifest.to_dict(),
                "publisher_signature": _signature(replacement, manifest),
            },
        ).json()
        assert expired["ready_for_publish"] is False
        assert expired["publisher_identity"]["author_signature_status"] == (
            "domain_verification_required"
        )
        assert app.get_publisher_profile("alice")["signing_key_bound"] is False
        assert (
            active["key_id"]
            not in app.get_publisher_profile("alice")["signing_key_ids"]
        )


def test_signing_key_cannot_be_reused_by_another_publisher():
    app = registry()
    private_key = Ed25519PrivateKey.generate()
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app, "alice.example")
        _bind_key(client, private_key)

        login(client, "bob")
        _verify_domain(client, app, "bob.example")
        conflict = client.post(
            f"{KEYS}/challenges",
            json={"public_key_pem": _public_pem(private_key)},
        )
        assert conflict.status_code == 409
        assert "already been enrolled" in conflict.json()["error"]


def test_pending_challenges_cannot_bypass_active_key_limit():
    app = registry()
    private_keys = [Ed25519PrivateKey.generate() for _ in range(6)]
    challenges = []
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app)
        for private_key in private_keys:
            response = client.post(
                f"{KEYS}/challenges",
                json={"public_key_pem": _public_pem(private_key)},
            )
            assert response.status_code == 201, response.text
            challenges.append(response.json()["challenge"])

        for private_key, challenge in zip(
            private_keys[:5], challenges[:5], strict=True
        ):
            proof = private_key.sign(challenge["canonical_payload"].encode("utf-8"))
            completed = client.post(
                f"{KEYS}/challenges/{challenge['challenge_id']}/complete",
                json={"signature": base64.b64encode(proof).decode("ascii")},
            )
            assert completed.status_code == 201, completed.text

        final_proof = private_keys[5].sign(
            challenges[5]["canonical_payload"].encode("utf-8")
        )
        limited = client.post(
            f"{KEYS}/challenges/{challenges[5]['challenge_id']}/complete",
            json={"signature": base64.b64encode(final_proof).decode("ascii")},
        )
        assert limited.status_code == 429
        assert limited.json()["error"] == "Active signing key limit reached"
        state = client.get(KEYS).json()
        assert len([key for key in state["keys"] if key["status"] == "active"]) == 5


def test_revoked_key_blocks_delayed_manual_review_approval():
    app = registry()
    app._manual_review_mode = ManualReviewMode.ALL
    private_key = Ed25519PrivateKey.generate()
    manifest = _manifest(author="alice", tool_name="pending-signed-tool")
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app)
        key = _bind_key(client, private_key)
        submitted = client.post(
            "/registry/submit",
            json={
                "manifest": manifest.to_dict(),
                "publisher_signature": _signature(private_key, manifest),
            },
        )
        assert submitted.status_code == 201, submitted.text
        listing = app._marketplace().get_by_name("pending-signed-tool")
        assert listing.status.value == "pending_review"

        client.post(
            f"{KEYS}/{key['key_id']}",
            json={"action": "revoke", "reason": "Compromised before approval"},
        )
        decision = app.moderate_listing(
            listing.listing_id,
            action_name="approve",
            moderator_id="independent-reviewer",
        )
        assert decision["status"] == 400
        assert "no longer active" in decision["error"]
        assert app._marketplace().get(listing.listing_id).status.value == (
            "pending_review"
        )


def test_revoked_key_blocks_staged_release_approval():
    app = registry()
    private_key = Ed25519PrivateKey.generate()
    first = _manifest(author="alice", tool_name="release-signed-tool", version="1.0.0")
    second = _manifest(author="alice", tool_name="release-signed-tool", version="1.1.0")
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app)
        key = _bind_key(client, private_key)
        published = client.post(
            "/registry/submit",
            json={
                "manifest": first.to_dict(),
                "publisher_signature": _signature(private_key, first),
            },
        )
        assert published.status_code == 201, published.text
        staged = client.post(
            "/registry/submit",
            json={
                "manifest": second.to_dict(),
                "publisher_signature": _signature(private_key, second),
                "changelog": "Signed release update",
            },
        )
        assert staged.status_code == 201, staged.text
        candidate_id = staged.json()["release_candidate"]["id"]
        listing = app._marketplace().get_by_name("release-signed-tool")

        client.post(
            f"{KEYS}/{key['key_id']}",
            json={"action": "revoke", "reason": "Compromised before release"},
        )
        with pytest.raises(ValueError, match="no longer active"):
            decide(
                app,
                listing.listing_id,
                candidate_id,
                "approve",
                "independent-reviewer",
                "",
            )
        assert app._marketplace().get(listing.listing_id).version == "1.0.0"


def test_only_ed25519_and_strict_signature_shapes_are_accepted():
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_pem = (
        rsa_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    with pytest.raises(ValueError, match="Only Ed25519"):
        canonicalize_public_key(rsa_pem)

    with pytest.raises(ValueError, match="must contain"):
        parse_publisher_manifest_signature({"key_id": "bad"})
    with pytest.raises(ValueError, match="must be `ed25519`"):
        parse_publisher_manifest_signature(
            {"algorithm": "rsa", "key_id": "pcpk_" + "a" * 43, "signature": "x"}
        )
    with pytest.raises(ValueError, match="exactly 64 bytes"):
        parse_publisher_manifest_signature(
            {
                "algorithm": "ed25519",
                "key_id": "pcpk_" + "a" * 43,
                "signature": base64.b64encode(b"short").decode("ascii"),
            }
        )


def test_key_binding_and_enforcement_persist_in_postgres(registry_dsn):
    app = registry()
    app._workspace = WorkspaceStore(registry_dsn)
    private_key = Ed25519PrivateKey.generate()
    manifest = _manifest(author="alice", tool_name="persistent-signed-tool")
    with TestClient(app.http_app()) as client:
        login(client)
        _verify_domain(client, app, "persistent.example")
        key = _bind_key(client, private_key)
        app._workspace = WorkspaceStore(registry_dsn)
        status = client.get(KEYS).json()
        assert status["signing_required"] is True
        assert status["keys"][0]["key_id"] == key["key_id"]
        valid = client.post(
            "/registry/preflight",
            json={
                "manifest": manifest.to_dict(),
                "publisher_signature": _signature(private_key, manifest),
            },
        )
        assert valid.json()["ready_for_publish"] is True
