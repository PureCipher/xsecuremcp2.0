from __future__ import annotations

from purecipher.notification_feed import RegistryNotificationFeed


def test_notification_feed_filters_by_persona(tmp_path) -> None:
    db_path = str(tmp_path / "n.db")
    feed = RegistryNotificationFeed(db_path)
    feed.append(
        event_kind="public",
        title="Catalog",
        body="Everyone",
        audiences=("viewer", "publisher", "reviewer", "admin"),
    )
    feed.append(
        event_kind="governance",
        title="Policy",
        body="Reviewers only",
        audiences=("reviewer", "admin"),
    )

    viewer_items = feed.list_recent(auth_enabled=True, role="viewer", limit=20)
    reviewer_items = feed.list_recent(auth_enabled=True, role="reviewer", limit=20)

    kinds_viewer = {i["event_kind"] for i in viewer_items}
    kinds_reviewer = {i["event_kind"] for i in reviewer_items}

    assert "public" in kinds_viewer
    assert "governance" not in kinds_viewer
    assert "public" in kinds_reviewer
    assert "governance" in kinds_reviewer


def test_notification_feed_open_auth_shows_all(tmp_path) -> None:
    db_path = str(tmp_path / "o.db")
    feed = RegistryNotificationFeed(db_path)
    feed.append(
        event_kind="governance",
        title="Policy",
        body="Secret",
        audiences=("reviewer", "admin"),
    )
    items = feed.list_recent(auth_enabled=False, role=None, limit=10)
    assert len(items) == 1
    assert items[0]["event_kind"] == "governance"
