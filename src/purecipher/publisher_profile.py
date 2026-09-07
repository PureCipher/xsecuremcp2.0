"""Self-service public publisher details, stored separately from account credentials."""

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from psycopg.errors import UniqueViolation
from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole
from purecipher.publishers import publisher_id_from_author


def profile_key(username):
    return "publisher-profile-" + hashlib.sha256(username.encode()).hexdigest()


def public_fields(body):
    if not isinstance(body, dict) or set(body) - {
        "display_name",
        "description",
        "website",
        "revision",
    }:
        raise ValueError("Only public profile details can be updated.")
    fields = {}
    for name, limit in (
        ("display_name", 120),
        ("description", 2000),
        ("website", 2048),
    ):
        value = body.get(name, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(
                f"{name.replace('_', ' ').capitalize()} must be at most {limit} characters."
            )
        value = value.strip()
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("Profile details contain unsupported characters.")
        fields[name] = value
    if not fields["display_name"]:
        raise ValueError("Enter a public display name.")
    website = fields["website"]
    if website:
        url = urlsplit(website)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or any(char.isspace() for char in website)
            or "\\" in website
        ):
            raise ValueError(
                "Enter a full http:// or https:// website URL without credentials."
            )
        try:
            url.port
        except ValueError as exc:
            raise ValueError("Enter a valid website URL.") from exc
    return fields


def mount_publisher_profile(registry, prefix):
    @registry.custom_route(
        f"{prefix}/workspace/publisher-profile", methods=["GET", "PUT"]
    )
    async def profile(request):
        headers = {"Cache-Control": "no-store"}
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse(
                {"error": "Authentication required"}, status_code=401, headers=headers
            )
        if session.role != RegistryRole.PUBLISHER:
            return JSONResponse(
                {"error": "Publisher account required"},
                status_code=403,
                headers=headers,
            )
        key = profile_key(session.username)
        item = registry._workspace.get(key)
        if item and (
            item["owner"] != session.username or item["kind"] != "publisher-profile"
        ):
            return JSONResponse(
                {"error": "Profile unavailable"}, status_code=409, headers=headers
            )
        identity = {
            "publisher_id": publisher_id_from_author(session.username),
            "username": session.username,
        }
        if request.method == "GET":
            fields = (
                {
                    name: item[name]
                    for name in ("display_name", "description", "website")
                }
                if item
                else {
                    "display_name": session.display_name,
                    "description": "",
                    "website": "",
                }
            )
            return JSONResponse(
                {**identity, **fields, "revision": item["revision"] if item else 0},
                headers=headers,
            )
        try:
            raw = await request.body()
            if len(raw) > 20_000:
                raise ValueError("Profile is too large.")
            body = json.loads(raw)
            fields = public_fields(body)
            revision = body.get("revision")
            if type(revision) is not int or revision < 0:
                raise ValueError("A valid profile revision is required.")
        except (ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400, headers=headers)
        if revision != (item["revision"] if item else 0):
            return JSONResponse(
                {
                    "error": "Your profile changed in another tab. Reload the latest profile before saving."
                },
                status_code=409,
                headers=headers,
            )
        record = {
            **fields,
            "id": key,
            "owner": session.username,
            "kind": "publisher-profile",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            saved = registry._workspace.save(record, expected=revision or None)
        except (ValueError, UniqueViolation):
            return JSONResponse(
                {
                    "error": "Your profile changed in another tab. Reload the latest profile before saving."
                },
                status_code=409,
                headers=headers,
            )
        return JSONResponse(
            {**identity, **fields, "revision": saved["revision"]}, headers=headers
        )
