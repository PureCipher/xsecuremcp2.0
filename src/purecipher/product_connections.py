"""Private consumer credentials, encrypted at rest and bound to profile ownership."""

import base64
import hashlib
import hmac
import json
import math
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from starlette.responses import JSONResponse

from purecipher.product_schemas import PRODUCT_SCHEMAS


def cipher(registry):
    key = registry._signing_secret_bytes
    if not key:
        raise ValueError("Credential storage is not configured")
    return Fernet(
        base64.urlsafe_b64encode(
            hmac.new(
                key, b"purecipher-consumer-connections-v1", hashlib.sha256
            ).digest()
        )
    )


def decrypt(registry, item):
    data = json.loads(cipher(registry).decrypt(item["encrypted"].encode()))
    if (data["owner"], data["id"], data["product"]) != (
        item["owner"],
        item["id"],
        item["product"],
    ):
        raise ValueError("Connection identity mismatch")
    return data["values"]


def view(registry, item):
    values = decrypt(registry, item)
    schema = PRODUCT_SCHEMAS[item["product"]]
    secrets = {f["key"] for f in schema["fields"] if f["type"] == "secret"}
    missing = [
        f["label"]
        for f in schema["fields"]
        if f["required"] and not values.get(f["key"])
    ]
    from purecipher.consumer_oauth import configured
    from purecipher.consumer_runtime import GOOGLE, runtime_ready

    ready = runtime_ready(registry, item)
    supported = item["product"] in getattr(registry, "_consumer_products", set())
    return {
        "id": item["id"],
        "product": item["product"],
        "name": item["name"],
        "revision": item["revision"],
        "updated_at": item["updated_at"],
        "values": {k: v for k, v in values.items() if k not in secrets},
        "secret_fields": [k for k in secrets if values.get(k)],
        "missing": missing,
        "status": "connected"
        if ready
        else "authorization_pending"
        if schema["kind"] == "oauth"
        else "settings_incomplete"
        if missing
        else "settings_saved",
        "runtime_ready": ready,
        "runtime_supported": supported,
        "can_authorize": supported and item["product"] in GOOGLE and configured(),
        "can_verify": supported and item["product"] == "brave-search",
    }


def validate_values(schema, raw):
    if not isinstance(raw, dict):
        raise ValueError("Settings must be an object")
    fields = {f["key"]: f for f in schema["fields"]}
    if set(raw) - set(fields):
        raise ValueError("Unsupported settings for this product")
    for key, value in raw.items():
        f = fields[key]
        if not isinstance(value, str) or len(value) > 8000 or "\x00" in value:
            raise ValueError(f"Invalid value for {f['label']}")
        if not value:
            continue
        if f["type"] == "number":
            try:
                if key == "param:port" and (
                    not value.isdigit() or not 1 <= int(value) <= 65535
                ):
                    raise ValueError()
                if not math.isfinite(float(value)):
                    raise ValueError()
            except ValueError:
                raise ValueError(f"{f['label']} must be a finite number") from None
        if f["type"] == "boolean" and value not in {"true", "false"}:
            raise ValueError(f"Choose yes or no for {f['label']}")
        if f["type"] == "select" and value not in f["options"]:
            raise ValueError(f"Choose a supported value for {f['label']}")
        if f["type"] != "secret" and re.match(r"^[a-z]+://", value):
            url = urlsplit(value)
            if url.username or url.password or url.query or url.fragment:
                raise ValueError(
                    f"Do not include credentials or query parameters in {f['label']}"
                )
    return raw


def mount_product_connections(registry, prefix):
    @registry.custom_route(f"{prefix}/workspace/connections", methods=["GET", "POST"])
    async def connections(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        try:
            if request.method == "GET":
                return JSONResponse(
                    {
                        "products": list(PRODUCT_SCHEMAS.values()),
                        "connections": [
                            view(registry, x)
                            for x in registry._workspace.list(
                                session.username, "product_connection"
                            )
                        ],
                    },
                    headers={"Cache-Control": "no-store"},
                )
            if (
                len(registry._workspace.list(session.username, "product_connection"))
                >= 100
            ):
                raise ValueError("Connection limit reached")
            body = await bounded_body(request)
            if body.get("product") not in PRODUCT_SCHEMAS:
                raise ValueError("Unknown product")
            item = {
                "id": str(uuid.uuid4()),
                "owner": session.username,
                "kind": "product_connection",
                "product": body["product"],
            }
            saved = save(registry, item, body, {})
            return JSONResponse(
                view(registry, saved),
                status_code=201,
                headers={"Cache-Control": "no-store"},
            )
        except (ValueError, TypeError, KeyError):
            return JSONResponse(
                {
                    "error": "Invalid connection settings. Check the product, name and field values."
                },
                status_code=400,
            )

    @registry.custom_route(
        f"{prefix}/workspace/connections/{{connection_id}}", methods=["PUT", "DELETE"]
    )
    async def connection(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        item = registry._workspace.get(request.path_params["connection_id"])
        if (
            not item
            or item.get("kind") != "product_connection"
            or item["owner"] != session.username
        ):
            return JSONResponse({"error": "Connection not found"}, status_code=404)
        if request.method == "DELETE":
            registry._workspace.delete(item)
            return JSONResponse({"deleted": True})
        try:
            body = await bounded_body(request)
            if (
                body.get("revision") != item["revision"]
                or body.get("product", item["product"]) != item["product"]
            ):
                return JSONResponse(
                    {"error": "Connection changed; reload before saving"},
                    status_code=409,
                )
            saved = save(registry, item, body, decrypt(registry, item))
            return JSONResponse(
                view(registry, saved), headers={"Cache-Control": "no-store"}
            )
        except (ValueError, TypeError, KeyError):
            return JSONResponse(
                {
                    "error": "Unable to save these settings. Reload and check the field values."
                },
                status_code=400,
            )


async def bounded_body(request):
    raw = await request.body()
    if len(raw) > 64000:
        raise ValueError("Connection is too large")
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("Expected an object")
    return body


def save(registry, item, body, values):
    name = body.get("name", "")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Name must be 1–100 characters")
    schema = PRODUCT_SCHEMAS[item["product"]]
    updates = validate_values(schema, body.get("values", {}))
    secrets = {f["key"] for f in schema["fields"] if f["type"] == "secret"}
    clear = body.get("clear_secrets", [])
    if not isinstance(clear, list) or any(
        not isinstance(x, str) or x not in secrets for x in clear
    ):
        raise ValueError("Invalid credential removal")
    for key in clear:
        values.pop(key, None)
    values.update({k: v for k, v in updates.items() if k not in secrets or v})
    payload = {
        "id": item["id"],
        "owner": item["owner"],
        "product": item["product"],
        "values": values,
    }
    return registry._workspace.save(
        {
            **item,
            "name": name.strip(),
            "encrypted": cipher(registry)
            .encrypt(json.dumps(payload).encode())
            .decode(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        expected=item.get("revision"),
    )


def connection_blocker(registry, owner, selected):
    key = selected.get("connection_id")
    if not key:
        listing = registry._marketplace().get(selected["listing_id"])
        if listing and listing.author == "purecipher":
            spec = PRODUCT_SCHEMAS.get(listing.tool_name.removeprefix("purecipher-"))
            if spec and (
                spec["kind"] == "oauth"
                or any(f["type"] == "secret" for f in spec["fields"])
            ):
                return "Select your own product connection; publisher credentials are not shared"
        return None
    item = registry._workspace.get(key)
    listing = registry._marketplace().get(selected["listing_id"])
    if (
        not item
        or item.get("kind") != "product_connection"
        or item["owner"] != owner
        or not listing
        or listing.author != "purecipher"
        or listing.tool_name != "purecipher-" + item["product"]
    ):
        return "The selected product connection is unavailable or does not match this server"
    from purecipher.consumer_runtime import runtime_ready

    if runtime_ready(registry, item):
        return None
    return "Authorize or verify your product connection before activating this profile"
