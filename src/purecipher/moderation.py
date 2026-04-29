"""Moderation queue helpers for the PureCipher registry."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp.server.security.gateway.tool_marketplace import (
    ModerationAction,
    PublishStatus,
    ToolListing,
    ToolMarketplace,
)
from purecipher.models import ReviewQueueItem
from purecipher.publishers import publisher_id_from_author

QUEUE_STATUSES = (
    PublishStatus.PENDING_REVIEW,
    PublishStatus.PUBLISHED,
    PublishStatus.SUSPENDED,
    # Iter 14.11 — show DEREGISTERED listings in the moderation
    # queue (read-only, no actions) so admins can audit historical
    # removals without digging through individual listing pages.
    PublishStatus.DEREGISTERED,
)

ACTION_BY_NAME = {
    "approve": ModerationAction.APPROVE,
    "reject": ModerationAction.REJECT,
    "suspend": ModerationAction.SUSPEND,
    "unsuspend": ModerationAction.UNSUSPEND,
    "request-changes": ModerationAction.REQUEST_CHANGES,
    "request_changes": ModerationAction.REQUEST_CHANGES,
    "deregister": ModerationAction.DEREGISTER,
    "withdraw": ModerationAction.WITHDRAW,
    "resubmit": ModerationAction.RESUBMIT,
}

# Iter 14.11 — ``deregister`` is offered on every status that
# represents a live or recoverable listing (PUBLISHED, SUSPENDED,
# DEPRECATED, PENDING_REVIEW). It's NOT offered on DEREGISTERED itself
# (terminal) or on DRAFT/REJECTED (never made it to the catalog, so
# there's nothing to deregister).
AVAILABLE_ACTIONS = {
    PublishStatus.PENDING_REVIEW: ("approve", "reject", "request-changes", "deregister"),
    PublishStatus.PUBLISHED: ("suspend", "deregister"),
    PublishStatus.SUSPENDED: ("unsuspend", "deregister"),
    PublishStatus.DEPRECATED: ("deregister",),
    PublishStatus.WITHDRAWN: ("resubmit",),
}


def moderation_action_from_name(action_name: str) -> ModerationAction | None:
    """Translate a route-safe action name into a moderation enum."""

    return ACTION_BY_NAME.get(action_name.strip().lower())


def build_review_queue_item(
    listing: ToolListing,
    *,
    trust_lookup: Callable[[ToolListing], float | None],
) -> ReviewQueueItem:
    """Build a moderation queue projection for a listing."""

    return ReviewQueueItem(
        listing_id=listing.listing_id,
        tool_name=listing.tool_name,
        display_name=listing.display_name,
        author=listing.author,
        publisher_id=publisher_id_from_author(listing.author),
        status=listing.status.value,
        certification_level=listing.certification_level.value,
        trust_score=trust_lookup(listing),
        version=listing.version,
        updated_at=listing.updated_at.isoformat(),
        available_actions=list(AVAILABLE_ACTIONS.get(listing.status, ())),
    )


def build_review_queue(
    marketplace: ToolMarketplace,
    *,
    trust_lookup: Callable[[ToolListing], float | None],
    limit_per_status: int = 200,
) -> dict[str, list[ReviewQueueItem]]:
    """Build moderation queue sections from the marketplace."""

    sections: dict[str, list[ReviewQueueItem]] = {}
    for status in QUEUE_STATUSES:
        listings = marketplace.search(status=status, limit=limit_per_status)
        ordered = sorted(listings, key=lambda item: item.updated_at, reverse=True)
        sections[status.value] = [
            build_review_queue_item(item, trust_lookup=trust_lookup) for item in ordered
        ]
    return sections


__all__ = [
    "QUEUE_STATUSES",
    "build_review_queue",
    "build_review_queue_item",
    "moderation_action_from_name",
]
