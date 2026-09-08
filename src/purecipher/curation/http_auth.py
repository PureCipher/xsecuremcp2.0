"""Private, short-lived HTTP inspection authorization; never listing credentials."""

import base64
import hashlib
import json
import os
import re
import secrets
import time
from urllib.parse import quote, urlencode, urlsplit

import httpx
from starlette.responses import JSONResponse, RedirectResponse

from purecipher.auth import RegistryRole
from purecipher.outbound_security import (
    PinnedDNSAsyncTransport,
    read_response_body_limited,
    validate_outbound_url,
)
from purecipher.product_connections import cipher

KIND = "curator_http_auth"


def checked_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Invalid HTTPS endpoint")
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.netloc
        or p.username
        or p.password
        or p.fragment
        or p.query
    ):
        raise ValueError(
            "Use an HTTPS endpoint without credentials, query parameters, or fragments"
        )
    validate_outbound_url(value)
    return value


def public_origin():
    value = os.environ.get("PURECIPHER_CURATOR_OAUTH_PUBLIC_ORIGIN", "")
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.netloc
        or p.path not in ("", "/")
        or p.query
        or p.fragment
        or p.username
    ):
        raise ValueError("Administrator must configure the curator OAuth public origin")
    return value.rstrip("/")


def client_metadata():
    origin = public_origin()
    return {
        "client_id": origin + "/api/curate/oauth/client.json",
        "client_name": "PureCipher Registry inspection",
        "redirect_uris": [origin + "/api/curate/oauth/callback"],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


async def request_json(
    url, *, method="GET", data=None, json_body=None, headers=None, probe=False
):
    checked_url(url)
    async with httpx.AsyncClient(
        transport=PinnedDNSAsyncTransport(), timeout=15, trust_env=False
    ) as client:
        async with client.stream(
            method,
            url,
            data=data,
            json=json_body,
            follow_redirects=False,
            headers={"Accept": "application/json", **(headers or {})},
        ) as response:
            raw = (
                b"{}"
                if probe
                else await read_response_body_limited(response, max_bytes=262144)
            )
            status, headers = response.status_code, dict(response.headers)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        body = {}
    return status, headers, body if isinstance(body, dict) else {}


async def discover(upstream):
    upstream = checked_url(upstream)
    status, headers, _ = await request_json(upstream, probe=True)
    challenge = headers.get("www-authenticate", "")
    match = re.search(r'resource_metadata="([^"]+)"', challenge, re.I)
    p = urlsplit(upstream)
    candidates = (
        [match.group(1)]
        if match
        else [
            f"{p.scheme}://{p.netloc}/.well-known/oauth-protected-resource{p.path}",
            f"{p.scheme}://{p.netloc}/.well-known/oauth-protected-resource",
        ]
    )
    resource = None
    for candidate in dict.fromkeys(candidates):
        code, _, doc = await request_json(candidate)
        if code == 200 and isinstance(doc, dict) and doc.get("authorization_servers"):
            resource = doc
            break
    if resource is None:
        return {
            "kind": "manual" if status in (401, 403) else "unconfirmed",
            "upstream": upstream,
            "message": "Authentication required; no OAuth metadata found."
            if status in (401, 403)
            else "No OAuth metadata found. Try discovery without credentials, or choose the authentication documented by the server.",
        }
    canonical = checked_url(resource.get("resource"))
    # A canonical alias is shown for confirmation before a token is requested or used.
    servers = resource.get("authorization_servers")
    if not isinstance(servers, list) or not servers:
        raise ValueError("Missing authorization server")
    issuer = checked_url(servers[0])
    p = urlsplit(issuer)
    origin = f"{p.scheme}://{p.netloc}"
    metadata = None
    for endpoint in [
        origin + "/.well-known/oauth-authorization-server" + p.path,
        origin + "/.well-known/openid-configuration" + p.path,
        issuer + "/.well-known/openid-configuration",
    ]:
        code, _, doc = await request_json(endpoint)
        if code == 200 and isinstance(doc, dict) and doc.get("issuer") == issuer:
            metadata = doc
            break
    if not metadata or "S256" not in metadata.get(
        "code_challenge_methods_supported", []
    ):
        raise ValueError("Authorization server must advertise PKCE S256")
    auth = checked_url(metadata.get("authorization_endpoint"))
    token = checked_url(metadata.get("token_endpoint"))
    scopes = resource.get("scopes_supported", [])
    if (
        not isinstance(scopes, list)
        or len(scopes) > 100
        or any(
            not isinstance(s, str) or len(s) > 200 or re.search(r"\s", s)
            for s in scopes
        )
    ):
        raise ValueError("Invalid advertised scopes")
    return {
        "kind": "oauth",
        "upstream": canonical,
        "issuer": issuer,
        "authorization_endpoint": auth,
        "token_endpoint": token,
        "scopes": scopes,
        "registration_methods": (
            ["cimd"] if metadata.get("client_id_metadata_document_supported") else []
        )
        + (["dynamic"] if metadata.get("registration_endpoint") else [])
        + ["preregistered"],
        "registration_endpoint": checked_url(metadata["registration_endpoint"])
        if metadata.get("registration_endpoint")
        else None,
        "token_auth_methods": metadata.get(
            "token_endpoint_auth_methods_supported", ["client_secret_basic"]
        ),
        "require_iss": metadata.get("authorization_response_iss_parameter_supported")
        is True,
    }


def secret_text(value, limit=4096):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise ValueError("Invalid credential")
    return value


async def registration(payload, body):
    """Register only against validated, discovered issuer metadata, after user choice."""
    methods = payload.get("registration_methods", ["cimd"])
    method = body.get("registration_method") or methods[0]
    if method not in methods:
        raise ValueError("Unsupported client registration method")
    metadata = client_metadata()
    if method == "cimd":
        return {"client_id": metadata["client_id"], "token_auth_method": "none"}
    if method == "preregistered":
        auth_method = body.get("token_auth_method", "none")
        if auth_method not in (
            "none",
            "client_secret_basic",
            "client_secret_post",
            "private_key_jwt",
        ) or auth_method not in payload.get("token_auth_methods", ["none"]):
            raise ValueError("Unsupported token endpoint authentication")
        result = {
            "client_id": secret_text(body.get("client_id")),
            "token_auth_method": auth_method,
        }
        if auth_method == "private_key_jwt":
            key = body.get("client_private_key")
            algorithm = body.get("client_algorithm", "RS256")
            if (
                not isinstance(key, str)
                or len(key) > 32768
                or algorithm not in ("RS256", "ES256")
            ):
                raise ValueError("Provide an RSA or P-256 private signing key")
            result.update(
                client_private_key=key,
                client_algorithm=algorithm,
                client_key_id=secret_text(body["client_key_id"])
                if body.get("client_key_id")
                else None,
            )
            token_credentials({**result, "token_endpoint": payload["token_endpoint"]})
        elif auth_method != "none":
            result["client_secret"] = secret_text(body.get("client_secret"))
        return result
    request = {k: v for k, v in metadata.items() if k != "client_id"}
    headers = {}
    if body.get("registration_token"):
        headers["Authorization"] = "Bearer " + secret_text(body["registration_token"])
    status, _, result = await request_json(
        payload["registration_endpoint"],
        method="POST",
        json_body=request,
        headers=headers,
    )
    if (
        status not in (200, 201)
        or result.get("token_endpoint_auth_method", "client_secret_basic") != "none"
        or result.get("redirect_uris") != metadata["redirect_uris"]
    ):
        raise ValueError("Registration response does not match requested public client")
    return {
        "client_id": secret_text(result.get("client_id")),
        "token_auth_method": "none",
    }


def token_credentials(payload):
    data = {"client_id": payload["client_id"]}
    headers = {}
    method = payload.get("token_auth_method", "none")
    if method == "client_secret_post":
        data["client_secret"] = payload["client_secret"]
    elif method == "client_secret_basic":
        raw = (
            quote(payload["client_id"], safe="")
            + ":"
            + quote(payload["client_secret"], safe="")
        )
        headers["Authorization"] = "Basic " + base64.b64encode(raw.encode()).decode()
    elif method == "private_key_jwt":
        import jwt

        now = int(time.time())
        data["client_assertion_type"] = (
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        )
        try:
            data["client_assertion"] = jwt.encode(
                {
                    "iss": payload["client_id"],
                    "sub": payload["client_id"],
                    "aud": payload["token_endpoint"],
                    "iat": now,
                    "exp": now + 60,
                    "jti": secrets.token_urlsafe(24),
                },
                payload["client_private_key"],
                algorithm=payload["client_algorithm"],
                headers={"kid": payload["client_key_id"]}
                if payload.get("client_key_id")
                else None,
            )
        except Exception:
            raise ValueError("Invalid OAuth client signing key") from None
    return data, headers


def owned(registry, key, owner):
    item = registry._workspace.get(key) if isinstance(key, str) else None
    if (
        not item
        or item.get("kind") != KIND
        or item.get("owner") != owner
        or item.get("expires_at", 0) <= time.time()
    ):
        raise ValueError(
            "Inspection authorization expired or belongs to another account. Reconnect."
        )
    return item


def inspection_headers(registry, body, session, upstream):
    connection = body.get("http_connection_id")
    manual = body.get("http_auth")
    if connection and manual:
        raise ValueError("Choose one HTTP authentication method")
    if not connection and not manual:
        return None
    checked_url(upstream)
    if not session:
        raise ValueError("Sign in before authorizing inspection")
    if connection:
        item = owned(registry, connection, session.username)
        payload = json.loads(cipher(registry).decrypt(item["encrypted"].encode()))
        if (
            payload.get("owner") != session.username
            or payload.get("id") != item["id"]
            or payload.get("upstream") != upstream
            or payload.get("stage") != "connected"
        ):
            raise ValueError("Authorization does not match this endpoint")
        if payload.get("access_expires_at", item["expires_at"]) <= time.time():
            raise ValueError(
                "Inspection access token expired. Renew authorization or reconnect."
            )
        return {"Authorization": "Bearer " + payload["access_token"]}
    if not isinstance(manual, dict):
        raise ValueError("Invalid HTTP credentials")
    kind = manual.get("kind")
    result = {}
    if kind == "bearer":
        result["Authorization"] = "Bearer " + secret_text(manual.get("value"))
    elif kind == "basic":
        username = secret_text(manual.get("username"))
        if ":" in username:
            raise ValueError("Basic authentication username cannot contain a colon")
        raw = username + ":" + secret_text(manual.get("value"))
        result["Authorization"] = "Basic " + base64.b64encode(raw.encode()).decode()
    elif kind == "api_key":
        result[header_name(manual.get("header"))] = secret_text(manual.get("value"))
    elif kind not in ("headers", "mtls", "aws_sigv4"):
        raise ValueError("Unknown authentication method")
    extra = manual.get("headers", [])
    if not isinstance(extra, list) or len(extra) > 8:
        raise ValueError("Use at most eight custom headers")
    for entry in extra:
        if not isinstance(entry, dict):
            raise ValueError("Invalid custom header")
        name = header_name(entry.get("name"))
        if name.lower() in {h.lower() for h in result}:
            raise ValueError("Duplicate credential header")
        result[name] = secret_text(entry.get("value"))
    if kind == "headers" and not result:
        raise ValueError("Add at least one private header")
    return result


def header_name(name):
    from purecipher.openapi_gateway import _BLOCKED_REQUEST_HEADERS

    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name)
        or name.lower() in _BLOCKED_REQUEST_HEADERS
        or name.lower()
        in {
            "host",
            "cookie",
            "authorization",
            "connection",
            "content-length",
            "content-type",
            "transfer-encoding",
            "origin",
            "referer",
            "forwarded",
        }
        or name.lower().startswith(
            ("proxy-", "sec-", "x-forwarded-", "x-http-", "x-method-", "x-amz-")
        )
    ):
        raise ValueError("Use the credential header documented by the server")
    return name


def inspection_transport(body, session, upstream):
    manual = body.get("http_auth")
    if not isinstance(manual, dict) or manual.get("kind") not in ("mtls", "aws_sigv4"):
        return None
    if not session:
        raise ValueError("Sign in before authorizing inspection")
    checked_url(upstream)
    kind = manual["kind"]
    if kind == "mtls":
        cert, key = manual.get("certificate"), manual.get("private_key")
        if (
            not isinstance(cert, str)
            or not isinstance(key, str)
            or len(cert) > 65536
            or len(key) > 32768
        ):
            raise ValueError("Provide PEM certificate and private key")
        if "-----BEGIN CERTIFICATE-----" not in cert or "PRIVATE KEY-----" not in key:
            raise ValueError("Provide PEM certificate and private key")
        return {
            "kind": kind,
            "certificate": cert,
            "private_key": key,
            "key_password": manual.get("key_password") or None,
        }
    region, service = manual.get("region", ""), manual.get("service", "")
    if (
        not isinstance(region, str)
        or not isinstance(service, str)
        or not re.fullmatch(r"[a-z0-9-]{1,64}", region)
        or not re.fullmatch(r"[a-z0-9-]{1,64}", service)
    ):
        raise ValueError("Provide the AWS region and signing service")
    return {
        "kind": kind,
        "region": region,
        "service": service,
        "access_key": secret_text(manual.get("access_key")),
        "secret_key": secret_text(manual.get("secret_key")),
        "session_token": secret_text(manual["session_token"])
        if manual.get("session_token")
        else None,
    }


def mount_curator_auth(registry, prefix):
    def owner(request):
        session = registry._session_from_request(request)
        if not session or not registry._has_roles(
            session, {RegistryRole.PUBLISHER, RegistryRole.REVIEWER, RegistryRole.ADMIN}
        ):
            raise ValueError("Publisher or reviewer sign-in required")
        return session.username

    def save_payload(user, payload, ttl=600, key=None, expected=None):
        key = key or secrets.token_urlsafe(24)
        return registry._workspace.save(
            {
                "id": key,
                "kind": KIND,
                "owner": user,
                "expires_at": time.time() + ttl,
                "encrypted": cipher(registry)
                .encrypt(json.dumps({**payload, "owner": user, "id": key}).encode())
                .decode(),
            },
            expected,
        )

    def unpack(item):
        return json.loads(cipher(registry).decrypt(item["encrypted"].encode()))

    def response(body, status=200):
        return JSONResponse(
            body,
            status_code=status,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @registry.custom_route(f"{prefix}/curate/oauth/client.json", methods=["GET"])
    async def metadata(request):
        try:
            return response(client_metadata())
        except ValueError as e:
            return response({"error": str(e)}, 503)

    @registry.custom_route(f"{prefix}/curate/oauth/discover", methods=["POST"])
    async def discovery(request):
        try:
            user = owner(request)
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            # Bound pending records per owner and remove expired credentials.
            items = registry._workspace.list(user, KIND)
            for item in items:
                if item.get("expires_at", 0) < time.time():
                    registry._workspace.delete(item)
            if len([i for i in items if i.get("expires_at", 0) >= time.time()]) >= 20:
                raise ValueError(
                    "Disconnect an existing inspection authorization before adding more"
                )
            result = await discover(body.get("upstream"))
            if result["kind"] == "oauth":
                public_origin()
                item = save_payload(user, {"stage": "discovered", **result})
                result["discovery_id"] = item["id"]
            return response(result)
        except (ValueError, httpx.HTTPError, TypeError):
            return response(
                {
                    "error": "Authentication discovery failed. Check the HTTPS URL and administrator OAuth configuration."
                },
                400,
            )

    @registry.custom_route(f"{prefix}/curate/oauth/authorize", methods=["POST"])
    async def authorize(request):
        try:
            user = owner(request)
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            item = owned(registry, body.get("discovery_id"), user)
            p = unpack(item)
            if p.get("stage") != "discovered":
                raise ValueError("Discovery expired")
            selected = body.get("scopes", [])
            if (
                not isinstance(selected, list)
                or any(not isinstance(s, str) for s in selected)
                or not set(selected).issubset(set(p["scopes"]))
            ):
                raise ValueError("Invalid scopes")
            client = client_metadata()
            registry._workspace.save({**item, "expires_at": 0}, item["revision"])
            registered = await registration(p, body)
            verifier = secrets.token_urlsafe(48)
            state = secrets.token_urlsafe(32)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            pending = {
                **p,
                "stage": "pending",
                "mode": "author" if body.get("mode") == "author" else "curator",
                "scopes": selected,
                "verifier": verifier,
                **registered,
                "redirect_uri": client["redirect_uris"][0],
            }
            # Persist one-time callback state after consuming discovery above.
            save_payload(user, pending, key=hashlib.sha256(state.encode()).hexdigest())
            return response(
                {
                    "authorization_url": p["authorization_endpoint"]
                    + "?"
                    + urlencode(
                        {
                            "client_id": registered["client_id"],
                            "redirect_uri": client["redirect_uris"][0],
                            "response_type": "code",
                            "scope": " ".join(selected),
                            "state": state,
                            "code_challenge": challenge,
                            "code_challenge_method": "S256",
                            "resource": p["upstream"],
                        }
                    )
                }
            )
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            return response(
                {
                    "error": "Authorization could not start. Discover authentication again."
                },
                400,
            )

    @registry.custom_route(f"{prefix}/curate/oauth/callback", methods=["GET"])
    async def callback(request):
        result = "?curator_oauth=failed"
        try:
            user = owner(request)
            state = request.query_params.get("state", "")
            if not state or len(state) > 200:
                raise ValueError("Invalid state")
            item = owned(registry, hashlib.sha256(state.encode()).hexdigest(), user)
            p = unpack(item)
            if p.get("stage") != "pending":
                raise ValueError("Invalid state")
            registry._workspace.save({**item, "expires_at": 0}, item["revision"])
            if request.query_params.get("error"):
                raise ValueError("Denied")
            if (
                p["require_iss"] or request.query_params.get("iss")
            ) and request.query_params.get("iss") != p["issuer"]:
                raise ValueError("Issuer mismatch")
            code = request.query_params.get("code", "")
            if not code or len(code) > 4096:
                raise ValueError("Invalid code")
            client_data, client_headers = token_credentials(p)
            status, _, grant = await request_json(
                p["token_endpoint"],
                method="POST",
                data={
                    "grant_type": "authorization_code",
                    **client_data,
                    "code": code,
                    "code_verifier": p["verifier"],
                    "redirect_uri": p["redirect_uri"],
                    "resource": p["upstream"],
                },
                **({"headers": client_headers} if client_headers else {}),
            )
            token = grant.get("access_token", "")
            expires = int(grant.get("expires_in", 3600))
            if (
                status != 200
                or not isinstance(grant.get("token_type"), str)
                or grant["token_type"].lower() != "bearer"
                or not isinstance(token, str)
                or not token
                or len(token) > 16384
                or any(ord(c) < 33 for c in token)
                or expires < 30
            ):
                raise ValueError("Invalid token response")
            refresh = grant.get("refresh_token")
            if refresh is not None:
                refresh = secret_text(refresh, 16384)
            saved = save_payload(
                user,
                {
                    "stage": "connected",
                    "upstream": p["upstream"],
                    "access_token": token,
                    "access_expires_at": time.time() + min(expires, 3600),
                    "refresh_token": refresh,
                    "token_endpoint": p["token_endpoint"],
                    "client_id": p["client_id"],
                    "token_auth_method": p.get("token_auth_method", "none"),
                    "client_secret": p.get("client_secret"),
                    "client_private_key": p.get("client_private_key"),
                    "client_algorithm": p.get("client_algorithm"),
                    "client_key_id": p.get("client_key_id"),
                },
                ttl=86400 if refresh else min(expires, 3600),
            )
            result = (
                "?curator_connection="
                + saved["id"]
                + "&mode="
                + p.get("mode", "curator")
            )
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            pass
        return RedirectResponse(
            "/registry/onboard" + result,
            status_code=303,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @registry.custom_route(f"{prefix}/curate/oauth/refresh", methods=["POST"])
    async def refresh_connection(request):
        try:
            user = owner(request)
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            item = owned(registry, body.get("connection_id"), user)
            p = unpack(item)
            if p.get("stage") != "connected" or not p.get("refresh_token"):
                raise ValueError("Reconnect to authorize")
            # Consume the refresh token before exchange. A concurrent request cannot reuse it.
            registry._workspace.save({**item, "expires_at": 0}, item["revision"])
            data, headers = token_credentials(p)
            status, _, grant = await request_json(
                p["token_endpoint"],
                method="POST",
                data={
                    **data,
                    "grant_type": "refresh_token",
                    "refresh_token": p["refresh_token"],
                    "resource": p["upstream"],
                },
                **({"headers": headers} if headers else {}),
            )
            token = secret_text(grant.get("access_token"), 16384)
            expires = min(int(grant.get("expires_in", 3600)), 3600)
            if (
                status != 200
                or not isinstance(grant.get("token_type"), str)
                or grant["token_type"].lower() != "bearer"
                or expires < 30
            ):
                raise ValueError("Invalid refreshed authorization")
            p.update(
                access_token=token,
                access_expires_at=time.time() + expires,
                refresh_token=secret_text(
                    grant.get("refresh_token", p["refresh_token"]), 16384
                ),
            )
            save_payload(
                user,
                p,
                ttl=max(1, item["expires_at"] - time.time()),
                key=item["id"],
                expected=item["revision"] + 1,
            )
            return response(
                {"renewed": True, "access_expires_at": p["access_expires_at"]}
            )
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            return response(
                {
                    "error": "Authorization could not be renewed. Reconnect to the provider."
                },
                400,
            )

    @registry.custom_route(
        f"{prefix}/curate/oauth/connections/{{connection_id}}",
        methods=["GET", "DELETE"],
    )
    async def connection(request):
        try:
            user = owner(request)
            item = owned(registry, request.path_params["connection_id"], user)
            p = unpack(item)
            if p.get("stage") != "connected":
                raise ValueError("Not connected")
            if request.method == "DELETE":
                registry._workspace.delete(item)
                return response({"disconnected": True})
            return response(
                {
                    "connection_id": item["id"],
                    "upstream": p["upstream"],
                    "expires_at": item["expires_at"],
                    "access_expires_at": p.get("access_expires_at", item["expires_at"]),
                    "can_refresh": bool(p.get("refresh_token")),
                }
            )
        except (ValueError, KeyError, TypeError):
            return response(
                {"error": "Inspection authorization unavailable; reconnect."}, 404
            )
