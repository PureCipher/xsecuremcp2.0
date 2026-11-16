"""External publisher identity proof and public trust-boundary contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus
from purecipher import publisher_identity
from purecipher.auth import RegistryRole
from purecipher.publisher_identity import (
    DomainProofError,
    DomainVerificationMethod,
    challenge_key,
    normalize_domain,
    proof_value,
    verified_publisher_identities,
    verify_domain_proof,
)
from purecipher.workspace import WorkspaceStore
from tests.server.security.test_publisher_drafts import login
from tests.server.security.test_purecipher_catalog_query import registry

BASE = "/registry/workspace/publisher-identity"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "localhost",
        "127.0.0.1",
        "::1",
        "https://example.com",
        "example.com/path",
        "user@example.com",
        "example.com:443",
        "*.example.com",
        ".example.com",
        "example..com",
        "-example.com",
        "example.c",
        None,
    ],
)
def test_domain_normalization_rejects_non_domain_targets(value):
    with pytest.raises(ValueError):
        normalize_domain(value)


def test_domain_normalization_is_canonical_and_idna_safe():
    assert normalize_domain(" Example.COM. ") == "example.com"
    assert normalize_domain("bücher.example") == "xn--bcher-kva.example"


def test_https_proof_resolver_never_uses_private_proxy_allowlists(monkeypatch):
    monkeypatch.setattr(
        publisher_identity.socket,
        "getaddrinfo",
        lambda _host, port: [(2, 1, 6, "", ("127.0.0.1", port))],
    )
    monkeypatch.setenv("PURECIPHER_OPENAPI_ALLOW_PRIVATE_HOSTS", "example.com")
    with pytest.raises(OSError, match="public addresses"):
        publisher_identity._public_address_resolver("example.com", 443)

    monkeypatch.setattr(
        publisher_identity.socket,
        "getaddrinfo",
        lambda _host, port: [(2, 1, 6, "", ("93.184.216.34", port))],
    )
    assert publisher_identity._public_address_resolver("example.com", 443)[0][4] == (
        "93.184.216.34",
        443,
    )


@pytest.mark.asyncio
async def test_proof_verifier_requires_exact_dns_or_https_value():
    token = "pcpv1_fixture"
    expected = proof_value(token)
    dns_names = []

    async def dns_lookup(name):
        dns_names.append(name)
        return ("unrelated=value", expected)

    await verify_domain_proof(
        "example.com",
        DomainVerificationMethod.DNS_TXT,
        token,
        dns_lookup=dns_lookup,
    )
    assert dns_names == ["_purecipher-challenge.example.com"]

    urls = []

    async def https_fetch(url):
        urls.append(url)
        return expected + "\n"

    await verify_domain_proof(
        "example.com",
        DomainVerificationMethod.HTTPS_WELL_KNOWN,
        token,
        https_fetch=https_fetch,
    )
    assert urls == [
        "https://example.com/.well-known/purecipher-verification.txt"
    ]

    async def missing(_name):
        return ("wrong",)

    with pytest.raises(DomainProofError, match="missing or does not match"):
        await verify_domain_proof(
            "example.com",
            DomainVerificationMethod.DNS_TXT,
            token,
            dns_lookup=missing,
        )


def _create_challenge(client, *, domain="example.com", method="dns_txt"):
    response = client.post(
        f"{BASE}/challenges",
        json={"domain": domain, "method": method},
    )
    assert response.status_code == 201, response.text
    return response.json()["challenge"]


def test_domain_proof_becomes_public_without_leaking_challenge(monkeypatch):
    app = registry()
    calls = []

    async def verifier(domain, method, token):
        calls.append((domain, method, token))

    monkeypatch.setattr(app, "_publisher_domain_verifier", verifier)
    with TestClient(app.http_app()) as client:
        assert client.get(BASE).status_code == 401
        assert client.post(f"{BASE}/challenges", json={}).status_code == 401
        login(client)
        challenge = _create_challenge(client, domain="EXAMPLE.com.")
        instructions = challenge["instructions"]
        assert instructions["record_type"] == "TXT"
        assert instructions["record_name"] == "_purecipher-challenge.example.com"
        assert instructions["record_value"].startswith(
            "purecipher-publisher-verification=pcpv1_"
        )
        assert app.get_publisher_profile("alice")["domain_verified"] is False

        verified = client.post(
            f"{BASE}/challenges/{challenge['challenge_id']}/verify"
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["identity"]["domain"] == "example.com"
        assert calls[0][0:2] == (
            "example.com",
            DomainVerificationMethod.DNS_TXT,
        )
        status = client.get(BASE).json()
        assert status["domain_verified"] is True
        assert status["challenges"] == []
        assert status["identities"][0]["status"] == "verified"

        public = client.get("/registry/publishers/alice").json()
        assert public["domain_verified"] is True
        assert public["verified_domains"] == ["example.com"]
        assert public["identity_verified_at"]
        assert "pcpv1_" not in str(public)
        assert "proof_digest" not in public
        html = client.get("/registry/publishers/alice?view=html")
        assert html.status_code == 200
        assert "Domain verified: example.com" in html.text

        stored = app._workspace.list("alice", "publisher-domain-identity")
        assert len(stored) == 1 and stored[0]["proof_digest"]
        assert app._workspace.list("alice", "publisher-domain-challenge") == []


def test_profile_and_listing_metadata_cannot_self_assert_external_identity():
    app = registry()
    app._marketplace().publish(
        "self-asserted-tool",
        author="alice",
        status=PublishStatus.PUBLISHED,
        metadata={
            "domain_verified": True,
            "verified_domains": ["attacker.example"],
        },
    )
    profile = app.get_publisher_profile("alice")
    assert profile["domain_verified"] is False
    assert profile["verified_domains"] == []

    with TestClient(app.http_app()) as client:
        login(client)
        response = client.put(
            "/registry/workspace/publisher-profile",
            json={
                "display_name": "Alice",
                "description": "",
                "website": "https://attacker.example",
                "revision": 0,
                "domain_verified": True,
            },
        )
        assert response.status_code == 400
        assert app.get_publisher_profile("alice")["domain_verified"] is False


def test_verified_domain_is_exclusive_and_admin_can_require_new_proof(monkeypatch):
    app = registry()

    async def verifier(_domain, _method, _token):
        return None

    monkeypatch.setattr(app, "_publisher_domain_verifier", verifier)
    app._account_security.create_account(
        username="identity-admin",
        password="long-fixture-password",
        role=RegistryRole.ADMIN,
        display_name="Identity Admin",
    )
    with TestClient(app.http_app()) as client:
        login(client)
        alice = _create_challenge(client)
        assert (
            client.post(f"{BASE}/challenges/{alice['challenge_id']}/verify").status_code
            == 200
        )

        login(client, "bob")
        bob = _create_challenge(
            client, domain="example.com", method="https_well_known"
        )
        conflict = client.post(f"{BASE}/challenges/{bob['challenge_id']}/verify")
        assert conflict.status_code == 409
        assert "another publisher" in conflict.json()["error"]

        logged_in = client.post(
            "/registry/login",
            json={
                "username": "identity-admin",
                "password": "long-fixture-password",
            },
        )
        assert logged_in.status_code == 200
        revoked = client.post(
            "/registry/admin/publisher-identities/example.com",
            json={"action": "revoke", "reason": "Ownership is disputed"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["identity"]["status"] == "revoked"
        assert app.get_publisher_profile("alice")["domain_verified"] is False

        login(client)
        retry = _create_challenge(
            client, domain="example.com", method="https_well_known"
        )
        blocked = client.post(f"{BASE}/challenges/{retry['challenge_id']}/verify")
        assert blocked.status_code == 409
        assert "revoked by an administrator" in blocked.json()["error"]

        client.post(
            "/registry/login",
            json={
                "username": "identity-admin",
                "password": "long-fixture-password",
            },
        )
        reopened = client.post(
            "/registry/admin/publisher-identities/example.com",
            json={"action": "require_reverification", "reason": "Fresh proof required"},
        )
        assert reopened.status_code == 200
        assert reopened.json()["identity"]["status"] == "reverification_required"

        login(client)
        restored = client.post(f"{BASE}/challenges/{retry['challenge_id']}/verify")
        assert restored.status_code == 200, restored.text
        assert app.get_publisher_profile("alice")["domain_verified"] is True


def test_failed_expired_and_cross_owner_challenges_are_bounded(monkeypatch):
    app = registry()

    async def missing(_domain, _method, _token):
        raise DomainProofError("Proof not found")

    monkeypatch.setattr(app, "_publisher_domain_verifier", missing)
    with TestClient(app.http_app()) as client:
        login(client)
        challenge = _create_challenge(client, domain="missing.example")
        path = f"{BASE}/challenges/{challenge['challenge_id']}"
        for attempt in range(5):
            response = client.post(path + "/verify")
            assert response.status_code == 422, (attempt, response.text)
        assert client.post(path + "/verify").status_code == 429

        login(client, "bob")
        assert client.delete(path).status_code == 404
        login(client)
        assert client.delete(path).json() == {"deleted": True}

        expired = _create_challenge(client, domain="expired.example")
        key = challenge_key(expired["challenge_id"])
        item = app._workspace.get(key)
        item["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        app._workspace.save(item, expected=item["revision"])
        assert client.post(f"{BASE}/challenges/{expired['challenge_id']}/verify").status_code == 410


def test_only_publishers_manage_challenges_and_only_admins_revoke():
    app = registry()
    app._account_security.create_account(
        username="identity-viewer",
        password="long-fixture-password",
        role=RegistryRole.VIEWER,
        display_name="Identity Viewer",
    )
    with TestClient(app.http_app()) as client:
        response = client.post(
            "/registry/login",
            json={
                "username": "identity-viewer",
                "password": "long-fixture-password",
            },
        )
        assert response.status_code == 200
        assert client.get(BASE).status_code == 403
        assert (
            client.post(
                f"{BASE}/challenges",
                json={"domain": "example.com", "method": "dns_txt"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/registry/admin/publisher-identities/example.com",
                json={"action": "revoke"},
            ).status_code
            == 403
        )


def test_public_identity_aggregation_ignores_expired_revoked_and_invalid_records():
    now = datetime.now(UTC)
    base = {
        "kind": "publisher-domain-identity",
        "status": "verified",
        "owner": "alice",
        "domain": "example.com",
        "verified_at": now.isoformat(),
        "verification_expires_at": (now + timedelta(days=1)).isoformat(),
    }
    result = verified_publisher_identities(
        [
            base,
            {**base, "domain": "expired.example", "verification_expires_at": now.isoformat()},
            {**base, "domain": "revoked.example", "status": "revoked"},
            {**base, "domain": 123},
            {**base, "owner": None},
        ],
        now=now,
    )
    assert result == {
        "alice": {
            "domain_verified": True,
            "verified_domains": ["example.com"],
            "identity_verified_at": now.isoformat(),
        }
    }


def test_challenge_and_verified_identity_persist_in_postgres(registry_dsn, monkeypatch):
    app = registry()
    app._workspace = WorkspaceStore(registry_dsn)

    async def verifier(_domain, _method, _token):
        return None

    monkeypatch.setattr(app, "_publisher_domain_verifier", verifier)
    with TestClient(app.http_app()) as client:
        login(client)
        challenge = _create_challenge(client, domain="persistent.example")
        app._workspace = WorkspaceStore(registry_dsn)
        loaded = client.get(BASE).json()["challenges"]
        assert loaded[0]["challenge_id"] == challenge["challenge_id"]
        response = client.post(
            f"{BASE}/challenges/{challenge['challenge_id']}/verify"
        )
        assert response.status_code == 200, response.text
        app._workspace = WorkspaceStore(registry_dsn)
        assert app.get_publisher_profile("alice")["verified_domains"] == [
            "persistent.example"
        ]
