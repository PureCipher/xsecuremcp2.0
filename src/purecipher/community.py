"""User feedback, independent of security certification and trust attestations."""

import threading

from starlette.responses import JSONResponse

from fastmcp.server.security.gateway.tool_marketplace import ReviewRating, ToolReview

_LOCK = threading.RLock()


def refresh(registry):
    mp = registry._marketplace()
    if mp._backend:
        saved = mp._backend.load_tool_marketplace(mp._marketplace_id).get("reviews", {})
        for item in mp.get_all_listings():
            latest = {}
            for raw in saved.get(item.listing_id, []):
                latest[raw["reviewer_id"]] = mp._deserialize_review(raw)
            item.reviews = list(latest.values())
    return mp


def client_counts(registry):
    """Count unique active client bindings, never expose identities or credentials."""
    counts = {}
    for profile in registry._workspace.list_kind("profile"):
        if profile.get("status") != "active":
            continue
        for server in profile.get("servers", []):
            bucket = counts.setdefault(server["listing_id"], set())
            for cid in profile.get("client_ids", []):
                client = registry._client_store.get_client(cid)
                if (
                    client
                    and client.status == "active"
                    and server.get("client_tools", {}).get(cid, server.get("tools", []))
                ):
                    bucket.add(cid)
    return {key: len(value) for key, value in counts.items()}


def mount(registry, prefix):
    @registry.custom_route(
        f"{prefix}/tools/{{tool_name}}/ratings", methods=["GET", "PUT"]
    )
    async def route(request):
        session = registry._session_from_request(request)
        listing = registry._get_public_listing(request.path_params["tool_name"])

        def response(data, status=200):
            return JSONResponse(
                data, status_code=status, headers={"Cache-Control": "no-store"}
            )

        if listing is None:
            return response({"error": "Published server not found"}, 404)
        try:
            with _LOCK:
                mp = refresh(registry)
                if request.method == "PUT":
                    if not session:
                        return response({"error": "Sign in to rate this server"}, 401)
                    if session.username == listing.author:
                        return response(
                            {"error": "Publishers cannot rate their own servers"}, 403
                        )
                    if len(await request.body()) > 12000:
                        return response({"error": "Review is too large"}, 400)
                    data = await request.json()
                    if not isinstance(data, dict):
                        raise ValueError("Provide a review object")
                    rating, body = data.get("rating"), data.get("body", "")
                    if type(rating) is not int or not 1 <= rating <= 5:
                        raise ValueError("Choose 1 to 5 stars")
                    if not isinstance(body, str) or len(body) > 2000:
                        raise ValueError("Feedback must be 2000 characters or fewer")
                    review = ToolReview(
                        tool_listing_id=listing.listing_id,
                        reviewer_id=session.username,
                        rating=ReviewRating(rating),
                        body=body.strip(),
                    )
                    # Persist first. Failure must not report success or alter in-memory ratings.
                    if mp._backend:
                        mp._backend.append_tool_review(
                            mp._marketplace_id, listing.listing_id, review.to_dict()
                        )
                    listing.reviews = [
                        r for r in listing.reviews if r.reviewer_id != session.username
                    ] + [review]
                reviews = sorted(
                    listing.reviews, key=lambda r: r.created_at, reverse=True
                )
                mine = next(
                    (
                        r
                        for r in reviews
                        if session and r.reviewer_id == session.username
                    ),
                    None,
                )

                def public(review):
                    account = registry._account_security._get_account(
                        review.reviewer_id
                    )
                    return {
                        "rating": review.rating.value,
                        "body": review.body,
                        "created_at": review.created_at.isoformat(),
                        "name": (account or {}).get("display_name") or "Registry user",
                    }

                return response(
                    {
                        "average_rating": listing.average_rating,
                        "review_count": listing.review_count,
                        "reviews": [public(r) for r in reviews[:100]],
                        "mine": public(mine) if mine else None,
                        "can_rate": bool(
                            session and session.username != listing.author
                        ),
                        "signed_in": bool(session),
                    }
                )
        except (ValueError, TypeError) as exc:
            return response({"error": str(exc)}, 400)
        except Exception:
            return response(
                {"error": "Reviews are temporarily unavailable. Please retry."}, 503
            )
