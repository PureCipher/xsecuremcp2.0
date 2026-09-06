"""Google consumer OAuth with owner-bound, single-use state and encrypted grants."""

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
from starlette.responses import JSONResponse, RedirectResponse

from purecipher.product_connections import cipher, view
from purecipher.product_schemas import PRODUCT_SCHEMAS


def app_config():
    client_id = os.environ.get("PURECIPHER_GOOGLE_CLIENT_ID", "")
    secret_file = os.environ.get("PURECIPHER_GOOGLE_CLIENT_SECRET_FILE")
    secret = (
        Path(secret_file).read_text().strip()
        if secret_file
        else os.environ.get("PURECIPHER_GOOGLE_CLIENT_SECRET", "")
    )
    redirect = os.environ.get("PURECIPHER_CONSUMER_OAUTH_REDIRECT_URI", "")
    parsed = urlsplit(redirect)
    if (
        not client_id
        or not secret
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The publisher Google OAuth application is not configured yet")
    return client_id, secret, redirect


def configured():
    try:
        app_config()
        return True
    except (ValueError, OSError):
        return False


def load_grant(registry, item):
    raw = item.get("oauth_encrypted")
    if not raw:
        return None
    data = json.loads(cipher(registry).decrypt(raw.encode()))
    if (data["owner"], data["id"], data["product"]) != (
        item["owner"],
        item["id"],
        item["product"],
    ):
        raise ValueError("OAuth grant identity mismatch")
    return data["grant"]


def store_grant(registry, item, grant):
    payload = {
        "owner": item["owner"],
        "id": item["id"],
        "product": item["product"],
        "grant": grant,
    }
    return registry._workspace.save(
        {
            **item,
            "oauth_encrypted": cipher(registry)
            .encrypt(json.dumps(payload).encode())
            .decode(),
        },
        item["revision"],
    )


async def token_request(data):
    client_id, secret, _ = app_config()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={**data, "client_id": client_id, "client_secret": secret},
            )
        if response.status_code != 200:
            raise ValueError("Google authorization failed; reconnect your account")
        body = response.json()
        if (
            not isinstance(body.get("access_token"), str)
            or not body["access_token"]
            or body.get("token_type", "").lower() != "bearer"
        ):
            raise ValueError("Google returned an invalid grant")
        expires = int(body.get("expires_in", 0))
        if not 30 <= expires <= 86400:
            raise ValueError("Google returned an invalid expiration")
        return {**body, "expires_at": time.time() + expires}
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Google authorization is unavailable; try again") from None


async def access_token(registry, item):
    grant = load_grant(registry, item)
    if not grant:
        raise ValueError("Authorize your Google account first")
    if grant["expires_at"] > time.time() + 30:
        return grant["access_token"]
    if not grant.get("refresh_token"):
        raise ValueError("Google authorization expired; reconnect your account")
    refreshed = await token_request(
        {"grant_type": "refresh_token", "refresh_token": grant["refresh_token"]}
    )
    required = set(PRODUCT_SCHEMAS[item["product"]]["scopes"])
    if not required.issubset(set(refreshed.get("scope", grant["scope"]).split())):
        raise ValueError("Google did not grant the required permissions")
    merged = {**grant, **refreshed}
    store_grant(registry, item, merged)
    return merged["access_token"]


def mount_consumer_oauth(registry, prefix):
    def owned(request):
        session = registry._session_from_request(request)
        item = registry._workspace.get(request.path_params["connection_id"])
        return (
            item
            if session
            and item
            and item.get("kind") == "product_connection"
            and item["owner"] == session.username
            else None
        )

    @registry.custom_route(
        f"{prefix}/workspace/connections/{{connection_id}}/authorize", methods=["POST"]
    )
    async def authorize(request):
        from purecipher.consumer_runtime import GOOGLE

        item = owned(request)
        if not item:
            return JSONResponse({"error": "Connection not found"}, status_code=404)
        if item["product"] not in GOOGLE or item["product"] not in getattr(
            registry, "_consumer_products", set()
        ):
            return JSONResponse(
                {"error": "OAuth is not available for this product yet"},
                status_code=409,
            )
        try:
            client_id, _, redirect = app_config()
            for previous in registry._workspace.list(
                item["owner"], "consumer_oauth_state"
            ):
                if previous["expires_at"] < time.time():
                    registry._workspace.delete(previous)
            if (
                len(registry._workspace.list(item["owner"], "consumer_oauth_state"))
                >= 10
            ):
                raise ValueError("Too many pending authorizations; try again later")
            state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
            key = hashlib.sha256(state.encode()).hexdigest()
            registry._workspace.save(
                {
                    "id": key,
                    "kind": "consumer_oauth_state",
                    "owner": item["owner"],
                    "connection_id": item["id"],
                    "connection_revision": item["revision"],
                    "expires_at": time.time() + 600,
                    "used": False,
                    "verifier": cipher(registry).encrypt(verifier.encode()).decode(),
                }
            )
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            return JSONResponse(
                {
                    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?"
                    + urlencode(
                        {
                            "client_id": client_id,
                            "redirect_uri": redirect,
                            "response_type": "code",
                            "scope": " ".join(
                                PRODUCT_SCHEMAS[item["product"]]["scopes"]
                            ),
                            "state": state,
                            "code_challenge": challenge,
                            "code_challenge_method": "S256",
                            "access_type": "offline",
                            "prompt": "consent select_account",
                        }
                    )
                },
                headers={"Cache-Control": "no-store"},
            )
        except (ValueError, OSError):
            return JSONResponse(
                {
                    "error": "Google OAuth is not configured or too many authorizations are pending"
                },
                status_code=503,
            )

    @registry.custom_route(f"{prefix}/workspace/oauth/callback", methods=["GET"])
    async def callback(request):
        try:
            session = registry._session_from_request(request)
            key = hashlib.sha256(
                request.query_params.get("state", "").encode()
            ).hexdigest()
            pending = registry._workspace.get(key)
            if (
                not session
                or not pending
                or pending.get("kind") != "consumer_oauth_state"
                or pending["owner"] != session.username
                or pending["used"]
                or pending["expires_at"] < time.time()
            ):
                raise ValueError("Invalid OAuth state")
            registry._workspace.save({**pending, "used": True}, pending["revision"])
            if request.query_params.get("error"):
                raise ValueError("Authorization declined")
            item = registry._workspace.get(pending["connection_id"])
            if not item or item["revision"] != pending["connection_revision"]:
                raise ValueError("Connection changed")
            code = request.query_params.get("code", "")
            if not code or len(code) > 4096:
                raise ValueError("Missing authorization code")
            _, _, redirect = app_config()
            grant = await token_request(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect,
                    "code_verifier": cipher(registry)
                    .decrypt(pending["verifier"].encode())
                    .decode(),
                }
            )
            required = set(PRODUCT_SCHEMAS[item["product"]]["scopes"])
            grant.setdefault("scope", " ".join(required))
            if not required.issubset(set(grant["scope"].split())):
                raise ValueError("Required Google permissions were not granted")
            store_grant(registry, item, grant)
            return RedirectResponse(
                "/registry/profiles?connections=1&oauth=success",
                status_code=303,
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )
        except (ValueError, TypeError, KeyError, OSError):
            return RedirectResponse(
                "/registry/profiles?connections=1&oauth=failed",
                status_code=303,
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )

    @registry.custom_route(
        f"{prefix}/workspace/connections/{{connection_id}}/disconnect", methods=["POST"]
    )
    async def disconnect(request):
        item = owned(request)
        if not item:
            return JSONResponse({"error": "Connection not found"}, status_code=404)
        item.pop("oauth_encrypted", None)
        item.pop("verified_values", None)
        result = registry._workspace.save(item, item["revision"])
        return JSONResponse(
            view(registry, result), headers={"Cache-Control": "no-store"}
        )

    @registry.custom_route(
        f"{prefix}/workspace/connections/{{connection_id}}/verify", methods=["POST"]
    )
    async def verify(request):
        from purecipher.consumer_runtime import digest, provider_get
        from purecipher.product_connections import decrypt

        item = owned(request)
        if not item:
            return JSONResponse({"error": "Connection not found"}, status_code=404)
        if item["product"] != "brave-search" or item["product"] not in getattr(
            registry, "_consumer_products", set()
        ):
            return JSONResponse(
                {
                    "error": "Credential verification is not available for this product yet"
                },
                status_code=409,
            )
        try:
            values = decrypt(registry, item)
            if not values.get("BRAVE_API_KEY"):
                raise ValueError("Enter your Brave API key first")
            await provider_get(
                "https://api.search.brave.com/res/v1/web/search",
                {"X-Subscription-Token": values["BRAVE_API_KEY"]},
                {"q": "PureCipher", "count": 1},
            )
            result = registry._workspace.save(
                {**item, "verified_values": digest(registry, values)}, item["revision"]
            )
            return JSONResponse(
                view(registry, result), headers={"Cache-Control": "no-store"}
            )
        except (ValueError, KeyError):
            return JSONResponse(
                {
                    "error": "Verification failed; check your Brave key and search API access"
                },
                status_code=400,
            )
