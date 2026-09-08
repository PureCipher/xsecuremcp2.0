"""Per-account read state for the role-scoped notification feed."""

from datetime import datetime, timezone

from starlette.responses import JSONResponse

from purecipher.pgdb import connection, is_postgres_dsn


def category(kind):
    k = kind.lower()
    if any(v in k for v in ("policy", "proposal", "promotion")):
        return "policyChanges"
    if any(v in k for v in ("security", "health", "revocation", "alert")):
        return "securityAlerts"
    if any(v in k for v in ("pending_review", "review_queue")):
        return "reviewQueue"
    if any(v in k for v in ("listing", "moderation", "publish")):
        return "publishUpdates"
    return "other"


def mount(registry, prefix):
    feed = registry._notification_feed
    if not hasattr(registry, "_inbox_reads"):
        registry._inbox_reads = {}
    sql_category = """CASE WHEN lower(n.event_kind) ~ '(policy|proposal|promotion)' THEN 'policyChanges'
        WHEN lower(n.event_kind) ~ '(security|health|revocation|alert)' THEN 'securityAlerts'
        WHEN lower(n.event_kind) ~ '(pending_review|review_queue)' THEN 'reviewQueue'
        WHEN lower(n.event_kind) ~ '(listing|moderation|publish)' THEN 'publishUpdates' ELSE 'other' END"""

    @registry.custom_route(f"{prefix}/notifications", methods=["GET", "POST"])
    async def notifications(request):
        session = registry._session_from_request(request)

        def response(data, status=200):
            return JSONResponse(
                data, status_code=status, headers={"Cache-Control": "no-store"}
            )

        if registry.auth_enabled and not session:
            return response({"error": "Authentication required."}, 401)
        username = session.username if session else "__local__"
        role = session.role.value if session else None
        prefs = registry._user_preferences.get(username).get("notifications", {})
        enabled = [
            v
            for v in (
                "policyChanges",
                "securityAlerts",
                "reviewQueue",
                "publishUpdates",
                "other",
            )
            if prefs.get(v, True)
        ]
        try:
            limit = max(1, min(100, int(request.query_params.get("limit", "40"))))
        except ValueError:
            limit = 40
        body = {}
        if request.method == "POST":
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise ValueError()
                key = "through_id" if body.get("all") is True else "id"
                if type(body.get(key)) is not int or body[key] < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                return response(
                    {"error": "Provide an item id or a snapshot through_id"}, 400
                )
        if is_postgres_dsn(feed._db_path):
            where = (
                "(%s OR n.audiences_json::jsonb = '[]'::jsonb OR n.audiences_json::jsonb ? %s) AND ("
                + sql_category
                + ") = ANY(%s)"
            )
            args = (not registry.auth_enabled, role or "viewer", enabled)
            with connection(feed._db_path) as conn:
                if request.method == "POST":
                    predicate = "n.id <= %s" if body.get("all") is True else "n.id = %s"
                    conn.execute(
                        "INSERT INTO purecipher_notification_reads (username,notification_id) SELECT %s,n.id FROM purecipher_registry_notifications n WHERE "
                        + where
                        + " AND "
                        + predicate
                        + " ON CONFLICT DO NOTHING",
                        (username, *args, body[key]),
                    )
                total = conn.execute(
                    "SELECT count(*) FILTER (WHERE r.notification_id IS NULL), COALESCE(max(n.id),0) FROM purecipher_registry_notifications n LEFT JOIN purecipher_notification_reads r ON r.notification_id=n.id AND r.username=%s WHERE "
                    + where,
                    (username, *args),
                ).fetchone()
                rows = conn.execute(
                    "SELECT n.id,n.created_at,n.event_kind,n.title,n.body,n.link_path,(r.notification_id IS NOT NULL) FROM purecipher_registry_notifications n LEFT JOIN purecipher_notification_reads r ON r.notification_id=n.id AND r.username=%s WHERE "
                    + where
                    + " ORDER BY n.id DESC LIMIT %s",
                    (username, *args, limit),
                ).fetchall()
            items = [
                dict(
                    id=r[0],
                    created_at=datetime.fromtimestamp(
                        r[1], tz=timezone.utc
                    ).isoformat(),
                    event_kind=r[2],
                    title=r[3],
                    body=r[4],
                    link_path=r[5],
                    read=r[6],
                )
                for r in rows
            ]
            return response(
                {"items": items, "unread_count": total[0], "through_id": total[1]}
            )
        items = [
            x
            for x in feed.list_recent(
                auth_enabled=registry.auth_enabled, role=role, limit=200
            )
            if category(x["event_kind"]) in enabled
        ]
        reads = registry._inbox_reads.setdefault(username, set())
        if request.method == "POST":
            reads.update(
                x["id"]
                for x in items
                if x["id"] <= body[key]
                if body.get("all") is True or x["id"] == body[key]
            )
        return response(
            {
                "items": [{**x, "read": x["id"] in reads} for x in items[:limit]],
                "unread_count": sum(x["id"] not in reads for x in items),
                "through_id": max((x["id"] for x in items), default=0),
            }
        )
