"""Publisher aggregation helpers for the PureCipher registry."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace

from fastmcp.server.security.gateway.tool_marketplace import (
    PublishStatus,
    ToolListing,
    ToolMarketplace,
)
from purecipher.models import PublisherProfile, PublisherSummary


def publisher_id_from_author(author: str) -> str:
    """Normalize a publisher identity into a stable URL slug."""

    cleaned = re.sub(r"[^a-z0-9]+", "-", author.strip().lower())
    slug = cleaned.strip("-")
    return slug or "unknown"


def list_public_publishers(
    marketplace: ToolMarketplace,
    *,
    trust_lookup: Callable[[ToolListing], float | None],
    listing_serializer: Callable[[ToolListing], dict[str, object]],
    limit: int = 10_000,
    registered_publishers: dict[str, str] | None = None,
) -> list[PublisherProfile]:
    """Include registered publishers; derive public metrics only from published listings."""

    published = marketplace.search(status=PublishStatus.PUBLISHED, limit=limit)
    grouped: dict[str, list[ToolListing]] = defaultdict(list)
    for listing in published:
        grouped[publisher_id_from_author(listing.author)].append(listing)

    profiles: list[PublisherProfile] = []
    for publisher_id, listings in grouped.items():
        display_name = listings[0].author or "Unknown Publisher"
        categories = sorted(
            {category.value for item in listings for category in item.categories}
        )
        tags = sorted({tag for item in listings for tag in item.tags})
        trust_values = [
            score
            for score in (trust_lookup(item) for item in listings)
            if score is not None
        ]
        average_trust = (
            round(sum(trust_values) / len(trust_values), 4) if trust_values else None
        )
        latest_activity = max(item.updated_at.isoformat() for item in listings)
        ordered_listings = sorted(
            listings, key=lambda item: item.updated_at, reverse=True
        )
        summary = PublisherSummary(
            publisher_id=publisher_id,
            display_name=display_name,
            listing_count=len(listings),
            average_trust=average_trust,
            categories=categories,
            tags=tags,
            latest_activity=latest_activity,
        )
        profiles.append(
            PublisherProfile(
                summary=summary,
                listings=[listing_serializer(item) for item in ordered_listings],
            )
        )

    # Accounts contribute only their public identity, never drafts or account metadata.
    by_id = {profile.summary.publisher_id: profile for profile in profiles}
    for username, display_name in (registered_publishers or {}).items():
        publisher_id = publisher_id_from_author(username)
        existing = by_id.get(publisher_id)
        if existing is not None:
            by_id[publisher_id] = replace(
                existing,
                summary=replace(existing.summary, display_name=display_name),
            )
        else:
            by_id[publisher_id] = PublisherProfile(
                summary=PublisherSummary(
                    publisher_id=publisher_id,
                    display_name=display_name,
                    listing_count=0,
                    average_trust=None,
                )
            )
    profiles = list(by_id.values())

    profiles.sort(
        key=lambda profile: (
            -(profile.summary.average_trust or 0.0),
            -profile.summary.listing_count,
            profile.summary.display_name.lower(),
        )
    )
    return profiles


def get_public_publisher_profile(
    marketplace: ToolMarketplace,
    *,
    publisher_id: str,
    trust_lookup: Callable[[ToolListing], float | None],
    listing_serializer: Callable[[ToolListing], dict[str, object]],
    limit: int = 10_000,
    registered_publishers: dict[str, str] | None = None,
) -> PublisherProfile | None:
    """Look up a publisher profile from published listings."""

    for profile in list_public_publishers(
        marketplace,
        trust_lookup=trust_lookup,
        listing_serializer=listing_serializer,
        limit=limit,
        registered_publishers=registered_publishers,
    ):
        if profile.summary.publisher_id == publisher_id:
            return profile
    return None


__all__ = [
    "get_public_publisher_profile",
    "list_public_publishers",
    "publisher_id_from_author",
]
