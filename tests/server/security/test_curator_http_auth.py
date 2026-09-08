import base64
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from purecipher.curation import http_auth as auth
from tests.server.security.test_publisher_drafts import login
from tests.server.security.test_purecipher_catalog_query import registry

DISC = {
    "kind": "oauth",
    "upstream": "https://mcp.example/mcp",
    "issuer": "https://issuer.example",
    "authorization_endpoint": "https://issuer.example/authorize",
    "token_endpoint": "https://issuer.example/token",
    "scopes": ["read", "write"],
    "require_iss": True,
}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv(
        "PURECIPHER_CURATOR_OAUTH_PUBLIC_ORIGIN", "https://registry.example"
    )
    monkeypatch.setattr(auth, "validate_outbound_url", lambda _: None)

    async def discover(_):
        return dict(DISC)

    monkeypatch.setattr(auth, "discover", discover)
    app = registry()
    return app


def begin(c):
    r = c.post("/registry/curate/oauth/discover", json={"upstream": DISC["upstream"]})
    assert r.status_code == 200
    ident = r.json()["discovery_id"]
    r = c.post(
        "/registry/curate/oauth/authorize",
        json={"discovery_id": ident, "scopes": ["read"]},
    )
    assert r.status_code == 200
    return parse_qs(urlsplit(r.json()["authorization_url"]).query), ident


def test_oauth_pkce_private_grant_and_endpoint_isolation(setup, monkeypatch):
    seen = []

    async def request(url, **kwargs):
        seen.append(kwargs["data"])
        return (
            200,
            {},
            {
                "access_token": "private-token-marker",
                "token_type": "Bearer",
                "expires_in": 1800,
            },
        )

    monkeypatch.setattr(auth, "request_json", request)
    with TestClient(setup.http_app()) as c:
        login(c)
        q, discovery = begin(c)
        assert q["resource"] == [DISC["upstream"]] and q["scope"] == ["read"]
        assert (
            c.post(
                "/registry/curate/oauth/authorize",
                json={"discovery_id": discovery, "scopes": ["read"]},
            ).status_code
            == 400
        )
        args = {"state": q["state"][0], "code": "test-code", "iss": DISC["issuer"]}
        r = c.get(
            "/registry/curate/oauth/callback", params=args, follow_redirects=False
        )
        key = parse_qs(urlsplit(r.headers["location"]).query)["curator_connection"][0]
        record = setup._workspace.get(key)
        assert "private-token-marker" not in json.dumps(record)
        assert (
            base64.urlsafe_b64encode(
                hashlib.sha256(seen[0]["code_verifier"].encode()).digest()
            )
            .rstrip(b"=")
            .decode()
            == q["code_challenge"][0]
        )
        assert seen[0]["resource"] == DISC["upstream"]
        public = c.get("/registry/curate/oauth/connections/" + key)
        assert public.status_code == 200 and "private-token-marker" not in public.text
        assert auth.inspection_headers(
            setup,
            {"http_connection_id": key},
            SimpleNamespace(username="alice"),
            DISC["upstream"],
        ) == {"Authorization": "Bearer private-token-marker"}
        with pytest.raises(ValueError):
            auth.inspection_headers(
                setup,
                {"http_connection_id": key},
                SimpleNamespace(username="alice"),
                "https://other.example/mcp",
            )
        with pytest.raises(ValueError):
            auth.inspection_headers(
                setup,
                {"http_connection_id": key},
                SimpleNamespace(username="bob"),
                DISC["upstream"],
            )
        assert (
            "failed"
            in c.get(
                "/registry/curate/oauth/callback", params=args, follow_redirects=False
            ).headers["location"]
        )
        assert len(seen) == 1
        login(c, "bob")
        assert c.get("/registry/curate/oauth/connections/" + key).status_code == 404
        assert c.delete("/registry/curate/oauth/connections/" + key).status_code == 404
        login(c)
        assert c.delete("/registry/curate/oauth/connections/" + key).status_code == 200
        assert c.get("/registry/curate/oauth/connections/" + key).status_code == 404


@pytest.mark.parametrize("failure", ["issuer", "denied", "expired", "owner"])
def test_callback_rejects_before_token_exchange(setup, monkeypatch, failure):
    async def forbidden(*a, **kw):
        pytest.fail("Token endpoint must not be called")

    monkeypatch.setattr(auth, "request_json", forbidden)
    with TestClient(setup.http_app()) as c:
        login(c)
        q, _ = begin(c)
        args = {"state": q["state"][0], "code": "code", "iss": DISC["issuer"]}
        if failure == "issuer":
            args["iss"] = "https://evil.example"
        if failure == "denied":
            args["error"] = "access_denied"
        if failure == "owner":
            login(c, "bob")
        if failure == "expired":
            monkeypatch.setattr(auth.time, "time", lambda: 9999999999)
        assert (
            "failed"
            in c.get(
                "/registry/curate/oauth/callback", params=args, follow_redirects=False
            ).headers["location"]
        )


def test_scopes_and_authentication_required(setup):
    with TestClient(setup.http_app()) as c:
        assert (
            c.post(
                "/registry/curate/oauth/discover", json={"upstream": DISC["upstream"]}
            ).status_code
            == 400
        )
        login(c)
        d = c.post(
            "/registry/curate/oauth/discover", json={"upstream": DISC["upstream"]}
        ).json()
        assert (
            c.post(
                "/registry/curate/oauth/authorize",
                json={"discovery_id": d["discovery_id"], "scopes": ["admin"]},
            ).status_code
            == 400
        )


def test_manual_headers_are_private_and_constrained(setup):
    user = SimpleNamespace(username="alice")
    for header in [
        "Host",
        "Cookie",
        "Authorization",
        "Proxy-Authorization",
        "X-Forwarded-Host",
        "Content-Length",
        "X-Api-Key\r\nOther",
    ]:
        with pytest.raises(ValueError):
            auth.inspection_headers(
                setup,
                {"http_auth": {"kind": "api_key", "header": header, "value": "secret"}},
                user,
                DISC["upstream"],
            )
    with pytest.raises(ValueError):
        auth.inspection_headers(
            setup,
            {"http_auth": {"kind": "bearer", "value": "bad\r\nheader"}},
            user,
            DISC["upstream"],
        )
    assert auth.inspection_headers(
        setup,
        {"http_auth": {"kind": "api_key", "header": "xi-api-key", "value": "test-key"}},
        user,
        DISC["upstream"],
    ) == {"xi-api-key": "test-key"}
    assert auth.inspection_headers(setup, {}, user, DISC["upstream"]) is None


@pytest.mark.asyncio
async def test_discovery_checks_metadata_and_pkce(monkeypatch):
    monkeypatch.setattr(auth, "validate_outbound_url", lambda _: None)

    async def response(url, **kwargs):
        if url == DISC["upstream"]:
            return (
                401,
                {
                    "www-authenticate": 'Bearer resource_metadata="https://mcp.example/metadata"'
                },
                {},
            )
        if url.endswith("/metadata"):
            return (
                200,
                {},
                {
                    "resource": DISC["upstream"],
                    "authorization_servers": [DISC["issuer"]],
                    "scopes_supported": ["read"],
                },
            )
        return (
            200,
            {},
            {
                "issuer": DISC["issuer"],
                "authorization_endpoint": DISC["authorization_endpoint"],
                "token_endpoint": DISC["token_endpoint"],
                "code_challenge_methods_supported": ["S256"],
                "client_id_metadata_document_supported": True,
            },
        )

    monkeypatch.setattr(auth, "request_json", response)
    result = await auth.discover(DISC["upstream"])
    assert result["kind"] == "oauth" and result["scopes"] == ["read"]
    with pytest.raises(ValueError):
        await auth.discover("https://secret@example.com/mcp")


@pytest.mark.asyncio
async def test_authenticated_inspector_passes_header_without_exposing_it(monkeypatch):
    from fastmcp.server.security.gateway.tool_marketplace import (
        UpstreamChannel,
        UpstreamRef,
    )
    from purecipher.curation.introspector import HTTPIntrospector, IntrospectionError

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def list_tools(self):
            return [
                SimpleNamespace(
                    name="list_voices",
                    description="Read voices",
                    inputSchema={"type": "object"},
                )
            ]

        async def list_resources(self):
            return []

        async def list_prompts(self):
            return []

    seen = []

    def factory(url, headers):
        seen.append((url, headers))
        return Client()

    ref = UpstreamRef(
        channel=UpstreamChannel.HTTP, identifier="https://mcp.example/mcp"
    )
    result = await HTTPIntrospector(client_factory=factory).introspect(
        ref, headers={"Authorization": "Bearer private-token"}
    )
    assert seen == [(ref.identifier, {"Authorization": "Bearer private-token"})]
    assert "private-token" not in json.dumps(result.to_dict())

    def broken(url, headers):
        raise RuntimeError("private-token")

    with pytest.raises(IntrospectionError) as exc:
        await HTTPIntrospector(client_factory=broken).introspect(
            ref, headers={"Authorization": "Bearer private-token"}
        )
    assert "private-token" not in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["none", "client_secret_basic", "client_secret_post"]
)
async def test_preregistered_clients_and_secret_placement(monkeypatch, method):
    monkeypatch.setenv(
        "PURECIPHER_CURATOR_OAUTH_PUBLIC_ORIGIN", "https://registry.example"
    )
    payload = {
        **DISC,
        "registration_methods": ["preregistered"],
        "token_auth_methods": [method],
    }
    result = await auth.registration(
        payload,
        {
            "registration_method": "preregistered",
            "client_id": "client:id",
            "client_secret": "secret",
            "token_auth_method": method,
        },
    )
    data, headers = auth.token_credentials(result)
    assert data["client_id"] == "client:id"
    assert (data.get("client_secret") == "secret") == (method == "client_secret_post")
    assert bool(headers) == (method == "client_secret_basic")
    if headers:
        assert (
            base64.b64decode(headers["Authorization"].split()[1])
            == b"client%3Aid:secret"
        )


@pytest.mark.asyncio
async def test_dynamic_registration_rejects_redirect_substitution(monkeypatch):
    monkeypatch.setenv(
        "PURECIPHER_CURATOR_OAUTH_PUBLIC_ORIGIN", "https://registry.example"
    )
    seen = []
    swapped = False

    async def register(url, **kwargs):
        seen.append((url, kwargs))
        return (
            201,
            {},
            {
                "client_id": "registered",
                "token_endpoint_auth_method": "none",
                "redirect_uris": ["https://evil.example/callback"]
                if swapped
                else kwargs["json_body"]["redirect_uris"],
            },
        )

    monkeypatch.setattr(auth, "request_json", register)
    payload = {
        "registration_methods": ["dynamic"],
        "registration_endpoint": "https://issuer.example/register",
    }
    result = await auth.registration(
        payload, {"registration_method": "dynamic", "registration_token": "private"}
    )
    assert result == {"client_id": "registered", "token_auth_method": "none"}
    assert seen[0][1]["headers"] == {"Authorization": "Bearer private"}
    swapped = True
    with pytest.raises(ValueError):
        await auth.registration(payload, {"registration_method": "dynamic"})


def test_basic_and_combined_headers(setup):
    body = {
        "http_auth": {
            "kind": "basic",
            "username": "alice",
            "value": "private",
            "headers": [{"name": "X-Tenant-Key", "value": "tenant"}],
        }
    }
    headers = auth.inspection_headers(
        setup, body, SimpleNamespace(username="alice"), DISC["upstream"]
    )
    assert headers == {
        "Authorization": "Basic YWxpY2U6cHJpdmF0ZQ==",
        "X-Tenant-Key": "tenant",
    }
    body["http_auth"]["headers"].append({"name": "Host", "value": "evil.example"})
    with pytest.raises(ValueError):
        auth.inspection_headers(
            setup, body, SimpleNamespace(username="alice"), DISC["upstream"]
        )


def test_refresh_rotation_and_expired_access(setup, monkeypatch):
    requests = []

    async def exchange(url, **kwargs):
        requests.append(kwargs["data"])
        return (
            200,
            {},
            {
                "access_token": "new-access" if len(requests) > 1 else "first-access",
                "refresh_token": "new-refresh"
                if len(requests) > 1
                else "first-refresh",
                "expires_in": 60,
                "token_type": "Bearer",
            },
        )

    monkeypatch.setattr(auth, "request_json", exchange)
    with TestClient(setup.http_app()) as c:
        login(c)
        q, _ = begin(c)
        r = c.get(
            "/registry/curate/oauth/callback",
            params={"state": q["state"][0], "code": "code", "iss": DISC["issuer"]},
            follow_redirects=False,
        )
        key = parse_qs(urlsplit(r.headers["location"]).query)["curator_connection"][0]
        now = auth.time.time()
        monkeypatch.setattr(auth.time, "time", lambda: now + 70)
        with pytest.raises(ValueError, match="expired"):
            auth.inspection_headers(
                setup,
                {"http_connection_id": key},
                SimpleNamespace(username="alice"),
                DISC["upstream"],
            )
        login(c, "bob")
        assert (
            c.post(
                "/registry/curate/oauth/refresh", json={"connection_id": key}
            ).status_code
            == 400
        )
        assert len(requests) == 1
        login(c)
        r = c.post("/registry/curate/oauth/refresh", json={"connection_id": key})
        assert r.status_code == 200
        assert requests[-1]["refresh_token"] == "first-refresh"
        assert (
            auth.inspection_headers(
                setup,
                {"http_connection_id": key},
                SimpleNamespace(username="alice"),
                DISC["upstream"],
            )["Authorization"]
            == "Bearer new-access"
        )
        assert "new-refresh" not in json.dumps(setup._workspace.get(key))
        assert (
            c.post(
                "/registry/curate/oauth/refresh", json={"connection_id": key}
            ).status_code
            == 200
        )
        assert requests[-1]["refresh_token"] == "new-refresh"


@pytest.mark.asyncio
async def test_real_mcp_transport_and_sigv4(monkeypatch):
    import httpx

    from fastmcp.server.security.gateway.tool_marketplace import (
        UpstreamChannel,
        UpstreamRef,
    )
    from purecipher.curation.introspector import HTTPIntrospector
    from purecipher.outbound_security import PinnedDNSAsyncTransport

    seen = []

    async def respond(self, request):
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(405, request=request)
        if request.method == "DELETE":
            return httpx.Response(200, request=request)
        payload = json.loads(await request.aread())
        method = payload["method"]
        if "id" not in payload:
            return httpx.Response(202, request=request)
        result = {"tools": [], "resources": [], "prompts": []}
        if method == "initialize":
            result = {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "test", "version": "1"},
            }
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": payload["id"], "result": result},
            request=request,
        )

    monkeypatch.setattr(PinnedDNSAsyncTransport, "handle_async_request", respond)
    ref = UpstreamRef(
        channel=UpstreamChannel.HTTP, identifier="https://mcp.example/mcp"
    )
    result = await HTTPIntrospector().introspect(
        ref,
        headers={"X-Key": "private"},
        transport_options={
            "kind": "aws_sigv4",
            "region": "us-east-1",
            "service": "execute-api",
            "access_key": "test-key",
            "secret_key": "test-secret",
        },
    )
    assert result is not None
    assert seen and all(
        r.headers["Authorization"].startswith("AWS4-HMAC-SHA256 ") for r in seen
    )
    assert all("test-secret" not in str(r.headers) for r in seen)
    assert len({r.headers["Authorization"] for r in seen}) > 1


@pytest.mark.asyncio
async def test_transport_blocks_credential_redirect(monkeypatch):
    from purecipher.curation.http_transport import client_factory
    from purecipher.outbound_security import PinnedDNSAsyncTransport

    async def forbidden(*a, **kw):
        pytest.fail("Must reject the different origin before networking")

    monkeypatch.setattr(PinnedDNSAsyncTransport, "handle_async_request", forbidden)
    async with client_factory("https://mcp.example/mcp")() as c:
        with pytest.raises(ValueError, match="destination"):
            await c.get(
                "https://other.example/mcp", headers={"Authorization": "Bearer private"}
            )


def test_mtls_loads_matching_private_key_and_removes_temporary_files(monkeypatch):
    import datetime
    import ssl

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from purecipher.curation.http_transport import client_factory

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "inspection")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    keypem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    paths = []
    original = ssl.SSLContext.load_cert_chain

    def load(self, certfile, keyfile, password=None):
        paths.extend([certfile, keyfile])
        assert keyfile.stat().st_mode & 0o777 == 0o600
        return original(self, certfile, keyfile, password)

    monkeypatch.setattr(ssl.SSLContext, "load_cert_chain", load)
    client_factory(
        "https://mcp.example/mcp",
        {"kind": "mtls", "certificate": pem, "private_key": keypem},
    )
    assert paths and all(not p.exists() for p in paths)
    with pytest.raises(ssl.SSLError):
        client_factory(
            "https://mcp.example/mcp",
            {"kind": "mtls", "certificate": pem, "private_key": "not-a-key"},
        )


@pytest.mark.asyncio
async def test_private_key_client_assertion_is_signed_and_short_lived(monkeypatch):
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    monkeypatch.setenv(
        "PURECIPHER_CURATOR_OAUTH_PUBLIC_ORIGIN", "https://registry.example"
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    payload = {
        **DISC,
        "registration_methods": ["preregistered"],
        "token_auth_methods": ["private_key_jwt"],
    }
    client = await auth.registration(
        payload,
        {
            "registration_method": "preregistered",
            "client_id": "registered-client",
            "token_auth_method": "private_key_jwt",
            "client_private_key": pem,
            "client_algorithm": "RS256",
            "client_key_id": "key-1",
        },
    )
    data, headers = auth.token_credentials(
        {**client, "token_endpoint": DISC["token_endpoint"]}
    )
    decoded = jwt.decode(
        data["client_assertion"],
        key.public_key(),
        algorithms=["RS256"],
        audience=DISC["token_endpoint"],
    )
    assert decoded["iss"] == decoded["sub"] == "registered-client"
    assert decoded["exp"] - decoded["iat"] == 60
    assert decoded["jti"] and not headers
    assert "PRIVATE KEY" not in json.dumps(data)
    with pytest.raises(ValueError):
        await auth.registration(
            payload,
            {
                "registration_method": "preregistered",
                "client_id": "registered-client",
                "token_auth_method": "private_key_jwt",
                "client_private_key": "invalid",
                "client_algorithm": "RS256",
            },
        )
