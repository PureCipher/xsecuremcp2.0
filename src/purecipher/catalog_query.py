"""Search and paginate an already-authorized listing projection.

Callers must select the public or owner-visible dataset first. Facets are built
only from that dataset, so neither filters nor counts reveal another owner's drafts.
"""

import math
import unicodedata
from collections import Counter
from datetime import datetime

from starlette.datastructures import QueryParams

from fastmcp.server.security.certification.attestation import CertificationLevel
from fastmcp.server.security.gateway.tool_marketplace import PublishStatus, ToolCategory

SORTS = {
    "default",
    "oldest",
    "popularity",
    "relevance",
    "name_asc",
    "name_desc",
    "newest",
    "updated",
    "status",
    "publisher",
    "tools",
    "installs",
    "clients",
    "rating",
    "certification",
}


def label(value: str) -> str:
    return value.replace("_", " ").title()


def normalize(value) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", str(value or "").casefold())
        if not unicodedata.combining(c)
    ).replace("_", " ")


def values(params: QueryParams, key: str) -> set[str]:
    return {
        v.strip() for raw in params.getlist(key) for v in raw.split(",") if v.strip()
    }


def numeric(value) -> float:
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else 0
    except (ValueError, TypeError):
        return 0


def timestamp(value) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0


def browse_catalog(
    payload: dict, params: QueryParams, *, default_sort: str = "name_asc"
) -> dict:
    sort = params.get("sort", default_sort)
    if sort not in SORTS:
        raise ValueError("Unknown sort order")
    try:
        limit, offset = int(params.get("limit", "50")), int(params.get("offset", "0"))
    except ValueError:
        raise ValueError("Limit and offset must be integers") from None
    if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000:
        raise ValueError("Limit must be 1–200 and offset must be 0–1000000")
    categories, statuses, tags = (
        values(params, "category"),
        values(params, "status"),
        values(params, "tag"),
    )
    if categories - {c.value for c in ToolCategory}:
        raise ValueError("Unknown category")
    if statuses - {s.value for s in PublishStatus}:
        raise ValueError("Unknown listing status")
    configurations = values(params, "configuration")
    trusts = values(params, "trust")
    server_types = values(params, "server_type")
    if configurations - {"secrets", "none", "oauth"}:
        raise ValueError("Unknown configuration filter")
    if trusts - {"known"}:
        raise ValueError("Unknown trust tier")
    if server_types - {"remote"}:
        raise ValueError("Unknown server type")
    query = normalize(params.get("q", "")).strip()
    if len(query) > 300:
        raise ValueError("Search query must be at most 300 characters")
    author = params.get("author")
    listings = payload.get("tools", [])
    category_counts = Counter(
        c for item in listings for c in set(item.get("categories") or [])
    )
    status_counts = Counter(item.get("status", "unknown") for item in listings)
    facets = {
        "categories": [
            {"value": c, "label": label(c), "count": n}
            for c, n in sorted(category_counts.items())
        ],
        "statuses": [
            {"value": s, "label": label(s), "count": n}
            for s, n in sorted(status_counts.items())
        ],
    }
    results = []
    for item in listings:
        metadata = item.get("metadata") or {}
        declared = metadata.get("configuration")
        if configurations and (
            not isinstance(declared, list) or not configurations.intersection(declared)
        ):
            continue
        if trusts and item.get("known_publisher") is not True:
            continue
        if server_types and metadata.get("server_type") not in server_types:
            continue
        if categories and not categories.intersection(item.get("categories") or []):
            continue
        if statuses and item.get("status") not in statuses:
            continue
        if tags and not tags.intersection(item.get("tags") or []):
            continue
        if author and item.get("author") != author:
            continue
        haystack = normalize(
            " ".join(
                str(item.get(k) or "")
                for k in (
                    "tool_name",
                    "display_name",
                    "description",
                    "author",
                    "publisher_id",
                    "tags",
                    "categories",
                )
            )
        )
        if not all(term in haystack for term in query.split()):
            continue
        results.append(item)
    if sort != "relevance":
        # A stable tie break keeps pages deterministic even when metrics are equal.
        results.sort(
            key=lambda item: (
                normalize(item.get("display_name") or item["tool_name"]),
                item["tool_name"],
            )
        )
    if sort == "name_desc":
        results.reverse()
    elif sort in {"newest", "oldest", "updated"}:
        results.sort(
            key=lambda i: timestamp(
                i.get("updated_at" if sort == "updated" else "created_at")
            ),
            reverse=sort != "oldest",
        )
    elif sort == "publisher":
        results.sort(key=lambda i: normalize(i.get("publisher_id") or i.get("author")))
    elif sort == "status":
        order = {
            "rejected": 0,
            "suspended": 1,
            "withdrawn": 2,
            "draft": 3,
            "pending_review": 4,
            "published": 5,
        }
        results.sort(key=lambda i: order.get(i.get("status"), 9))
    elif sort == "tools":
        results.sort(
            key=lambda i: (
                numeric(i.get("tool_count"))
                or len(
                    i.get("tools_observed")
                    or (i.get("metadata") or {}).get("tools")
                    or []
                )
            ),
            reverse=True,
        )
    elif sort in {"installs", "popularity", "clients", "rating"}:
        key = {
            "installs": "install_count",
            "popularity": "install_count",
            "clients": "connected_clients",
            "rating": "average_rating",
        }[sort]
        results.sort(key=lambda i: numeric(i.get(key)), reverse=True)
    elif sort == "certification":
        levels = {level.value: n for n, level in enumerate(CertificationLevel)}
        results.sort(
            key=lambda i: levels.get(i.get("certification_level"), -1), reverse=True
        )
    page = results[offset : offset + limit]
    return {
        **payload,
        "tools": page,
        "count": len(page),
        "total": len(results),
        "unfiltered_count": len(listings),
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "facets": facets,
    }
