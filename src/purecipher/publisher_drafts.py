"""Owner-scoped, encrypted publisher working copies; never catalog listings."""

import json
import uuid
from datetime import datetime, timezone

from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole
from purecipher.product_connections import cipher
from purecipher.product_schemas import PRODUCT_SCHEMAS


def mount_publisher_drafts(registry, prefix):
    def unpack(item):
        payload = json.loads(cipher(registry).decrypt(item["encrypted"].encode()))
        if payload["owner"] != item["owner"] or payload["id"] != item["id"]:
            raise ValueError("Invalid draft identity")
        return {
            **payload,
            "revision": item["revision"],
            "updated_at": item["updated_at"],
        }

    @registry.custom_route(
        f"{prefix}/workspace/publisher-drafts", methods=["GET", "POST"]
    )
    @registry.custom_route(
        f"{prefix}/workspace/publisher-drafts/{{draft_id}}",
        methods=["GET", "PUT", "DELETE"],
    )
    async def drafts(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        if not registry._has_roles(session, {RegistryRole.PUBLISHER}):
            return JSONResponse(
                {"error": "Publisher account required"}, status_code=403
            )
        headers = {"Cache-Control": "no-store"}
        key = request.path_params.get("draft_id")
        item = registry._workspace.get(key) if key else None
        if key and (
            not item
            or item["owner"] != session.username
            or item["kind"] != "publisher-draft"
        ):
            return JSONResponse(
                {"error": "Draft not found"}, status_code=404, headers=headers
            )
        try:
            if request.method == "GET":
                if item:
                    return JSONResponse(unpack(item), headers=headers)
                values = [
                    unpack(value)
                    for value in registry._workspace.list(
                        session.username, "publisher-draft"
                    )
                ]
                return JSONResponse(
                    {
                        "drafts": [
                            {
                                k: v[k]
                                for k in (
                                    "id",
                                    "name",
                                    "revision",
                                    "updated_at",
                                    "source_listing_id",
                                )
                            }
                            for v in values
                        ],
                        "products": list(PRODUCT_SCHEMAS.values()),
                    },
                    headers=headers,
                )
            if request.method == "DELETE":
                registry._workspace.delete(item)
                return JSONResponse({"deleted": True}, headers=headers)
            raw = await request.body()
            if len(raw) > 200_000:
                raise ValueError("Draft exceeds 200 KB")
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("form"), dict):
                raise ValueError("Draft form must be an object")
            name = body.get("name", "Untitled server")
            if not isinstance(name, str) or len(name) > 200:
                raise ValueError("Draft name must be at most 200 characters")
            source = body.get("source_listing_id")
            if source is not None:
                listing = (
                    registry._marketplace().get(source)
                    if isinstance(source, str)
                    else None
                )
                if listing is None or listing.author != session.username:
                    return JSONResponse(
                        {"error": "Source listing not found"},
                        status_code=404,
                        headers=headers,
                    )
            if item and source != unpack(item)["source_listing_id"]:
                raise ValueError("Draft source cannot change")
            if item and body.get("revision") != item["revision"]:
                return JSONResponse(
                    {"error": "Draft changed in another tab. Reload before saving."},
                    status_code=409,
                    headers=headers,
                )
            if (
                not item
                and len(registry._workspace.list(session.username, "publisher-draft"))
                >= 100
            ):
                raise ValueError("You can keep up to 100 working drafts")
            key = key or str(uuid.uuid4())
            payload = {
                "id": key,
                "owner": session.username,
                "name": name.strip() or "Untitled server",
                "form": body["form"],
                "source_listing_id": source,
            }
            record = {
                "id": key,
                "owner": session.username,
                "kind": "publisher-draft",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "encrypted": cipher(registry)
                .encrypt(json.dumps(payload).encode())
                .decode(),
            }
            try:
                saved = registry._workspace.save(
                    record, expected=item["revision"] if item else None
                )
            except ValueError:
                return JSONResponse(
                    {"error": "Draft changed in another tab. Reload before saving."},
                    status_code=409,
                    headers=headers,
                )
            return JSONResponse(
                unpack(saved), status_code=200 if item else 201, headers=headers
            )
        except (ValueError, TypeError):
            return JSONResponse(
                {"error": "Invalid draft. Check its fields and size."},
                status_code=400,
                headers=headers,
            )
