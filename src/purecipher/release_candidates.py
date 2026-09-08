"""Immutable update submissions, atomically stored with their published listing."""

import copy
import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone

from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole

_LOCK = threading.RLock()


def fingerprint(snapshot):
    fields = (
        "tool_name",
        "version",
        "manifest",
        "attestation",
        "metadata",
        "status",
        "author",
        "source_url",
        "display_name",
        "description",
        "categories",
        "tags",
        "hosting_mode",
        "attestation_kind",
    )
    return hashlib.sha256(
        json.dumps(
            {k: snapshot.get(k) for k in fields}, sort_keys=True, default=str
        ).encode()
    ).hexdigest()


def load(mp, listing_id):
    if mp._backend:
        raw = mp._backend.load_tool_marketplace(mp._marketplace_id)["listings"].get(
            listing_id
        )
        if raw is None:
            raise ValueError("Listing not found")
        return copy.deepcopy(raw)
    item = mp.get(listing_id)
    if not item:
        raise ValueError("Listing not found")
    return copy.deepcopy(mp._serialize_listing_for_storage(item))


def save(mp, before, after):
    """Persist before exposing changes; PostgreSQL uses compare-and-swap."""
    backend = mp._backend
    if backend and hasattr(backend, "_dsn"):
        from psycopg.types.json import Jsonb

        from purecipher.pgdb import connection

        with connection(backend._dsn) as conn:
            result = conn.execute(
                "UPDATE tool_listings SET data=%s, updated_at=%s WHERE namespace=%s AND item_id=%s AND data=%s",
                (
                    Jsonb(after),
                    datetime.now(timezone.utc).timestamp(),
                    mp._marketplace_id,
                    before["listing_id"],
                    Jsonb(before),
                ),
            )
            if result.rowcount != 1:
                raise ValueError("Listing changed; reload before retrying")
    elif backend:
        backend.save_tool_listing(mp._marketplace_id, before["listing_id"], after)
    item = mp._deserialize_listing(after, reviews=mp.get(before["listing_id"]).reviews)
    mp._listings[item.listing_id] = item
    return item


def stage(
    registry,
    listing,
    manifest,
    preflight,
    *,
    display_name,
    description,
    categories,
    homepage_url,
    source_url,
    tool_license,
    tags,
    metadata,
    changelog,
):
    with _LOCK:
        mp = registry._marketplace()
        before = load(mp, listing.listing_id)
        if before["status"] != "published":
            raise ValueError(
                "The published listing changed; reload before creating an update"
            )
        if manifest.author != before["author"]:
            raise ValueError("Only the original publisher may submit a release")
        if (
            before.get("attestation_kind", "author") != "author"
            or before.get("hosting_mode", "catalog") != "catalog"
        ):
            raise ValueError(
                "This registration method requires its specialized update workflow"
            )

        def version(v):
            if not re.fullmatch(
                r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", v
            ):
                raise ValueError("Release versions must use major.minor.patch")
            return tuple(map(int, v.split(".")))

        if version(manifest.version) <= version(before["version"]):
            raise ValueError("Use a version newer than the published version")
        if (
            not isinstance(changelog, str)
            or not changelog.strip()
            or len(changelog) > 4000
        ):
            raise ValueError("Provide release notes between 1 and 4000 characters")
        records = before.get("release_records", [])
        if any(x["status"] == "pending_review" for x in records):
            raise ValueError(
                "A release is already in review; withdraw it before submitting another"
            )
        snapshot = copy.deepcopy(before)
        for key in (
            "release_records",
            "publisher_setup",
            "moderation_log",
            "version_history",
        ):
            snapshot.pop(key, None)
        snapshot.update(
            version=manifest.version,
            manifest=manifest.to_dict(),
            attestation=preflight.attestation.to_dict(),
            display_name=display_name or before["display_name"],
            description=description or manifest.description,
            categories=sorted(x.value for x in categories)
            if categories is not None
            else before.get("categories", []),
            homepage_url=homepage_url or before.get("homepage_url", ""),
            source_url=source_url or before.get("source_url", ""),
            license=tool_license or before.get("license", ""),
            tags=sorted(tags or manifest.tags),
            metadata=copy.deepcopy(
                metadata if metadata is not None else before.get("metadata", {})
            ),
        )
        record = {
            "id": str(uuid.uuid4()),
            "status": "pending_review",
            "version": manifest.version,
            "base_version": before["version"],
            "base_digest": fingerprint(before),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "submitted_by": manifest.author,
            "notes": changelog.strip(),
            "snapshot": snapshot,
            "validation": preflight.report.to_dict(),
            "history": [],
        }
        record["snapshot_digest"] = fingerprint(snapshot)
        after = copy.deepcopy(before)
        after["release_records"] = [*records, record]
        save(mp, before, after)
        return record


def decide(registry, listing_id, candidate_id, action, actor, reason):
    with _LOCK:
        mp = registry._marketplace()
        before = load(mp, listing_id)
        after = copy.deepcopy(before)
        record = next(
            (x for x in after.get("release_records", []) if x["id"] == candidate_id),
            None,
        )
        if not record or record["status"] != "pending_review":
            raise ValueError("This release is no longer awaiting review")
        if action not in ("approve", "reject", "request_changes", "withdraw"):
            raise ValueError("Unknown release decision")
        if action == "approve":
            if (
                fingerprint(before) != record["base_digest"]
                or before["status"] != "published"
            ):
                raise ValueError(
                    "The published release changed; submit a fresh candidate"
                )
            if fingerprint(record["snapshot"]) != record["snapshot_digest"]:
                raise ValueError("Candidate integrity check failed")
            old = copy.deepcopy(before)
            for key in ("release_records", "publisher_setup"):
                old.pop(key, None)
            record["previous_release"] = old
            after.update(copy.deepcopy(record["snapshot"]))
            after["version_history"] = [
                *before.get("version_history", []),
                {
                    "version": record["version"],
                    "manifest_digest": record["snapshot"]["attestation"].get(
                        "manifest_digest", ""
                    ),
                    "attestation_id": record["snapshot"]["attestation"].get(
                        "attestation_id", ""
                    ),
                    "changelog": record["notes"],
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "yanked": False,
                    "yank_reason": "",
                },
            ]
        record["status"] = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "changes_requested",
            "withdraw": "withdrawn",
        }[action]
        record["history"].append(
            {
                "action": action,
                "actor": actor,
                "reason": reason,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        after["updated_at"] = datetime.now(timezone.utc).isoformat()
        return save(mp, before, after)


def mount(registry, prefix):
    @registry.custom_route(f"{prefix}/releases", methods=["GET"])
    @registry.custom_route(f"{prefix}/releases/{{listing_id}}", methods=["GET", "POST"])
    async def route(request):
        session = registry._session_from_request(request)

        def response(data, status=200):
            return JSONResponse(
                data, status_code=status, headers={"Cache-Control": "no-store"}
            )

        if not session:
            return response({"error": "Sign in required"}, 401)
        reviewer = session.role in {RegistryRole.ADMIN, RegistryRole.REVIEWER}
        if not reviewer and session.role != RegistryRole.PUBLISHER:
            return response({"error": "Publishing access required"}, 403)
        mp = registry._marketplace()
        key = request.path_params.get("listing_id")
        listing = mp.get(key) if key else None
        if key and (
            not listing or (not reviewer and listing.author != session.username)
        ):
            return response({"error": "Listing not found"}, 404)
        try:
            if request.method == "POST":
                raw = await request.body()
                if len(raw) > 10000:
                    raise ValueError("Decision too large")
                body = json.loads(raw)
                if not isinstance(body, dict):
                    raise ValueError("Provide a decision object")
                action = body.get("action")
                reason = body.get("reason", "")
                if not isinstance(reason, str) or len(reason) > 4000:
                    raise ValueError("Provide a reason up to 4000 characters")
                if action == "withdraw":
                    if listing.author != session.username:
                        return response(
                            {"error": "Only the publisher can withdraw"}, 403
                        )
                elif not reviewer or listing.author == session.username:
                    return response(
                        {"error": "An independent reviewer must make this decision"},
                        403,
                    )
                if action in ("reject", "request_changes") and not reason.strip():
                    raise ValueError("Explain the changes or rejection")
                decide(
                    registry,
                    key,
                    body.get("candidate_id"),
                    action,
                    session.username,
                    reason.strip(),
                )
            items = []
            for item in [mp.get(key)] if key else mp.get_all_listings():
                if not reviewer and item.author != session.username:
                    continue
                raw = load(mp, item.listing_id)
                for record in raw.get("release_records", []):
                    items.append(
                        {
                            **record,
                            "listing_id": item.listing_id,
                            "tool_name": item.tool_name,
                            "display_name": item.display_name,
                            "published_version": raw["version"],
                            "can_review": reviewer and item.author != session.username,
                            "can_withdraw": item.author == session.username,
                        }
                    )
            return response({"releases": items})
        except (ValueError, TypeError, KeyError) as exc:
            return response({"error": str(exc)}, 400)
