import copy

from purecipher.release_candidates import decide
from purecipher.release_diff import compare
from tests.server.security.test_purecipher_registry import _manifest
from tests.server.security.test_release_candidates import setup


def test_inventory_changes_and_security_declarations():
    before = {
        "manifest": {"permissions": ["read"]},
        "metadata": {
            "introspection": {
                "tools": [
                    {"name": "read", "inputSchema": {"type": "object"}},
                    {"name": "old"},
                ]
            }
        },
    }
    after = copy.deepcopy(before)
    after["manifest"]["permissions"].append("write")
    after["metadata"]["introspection"]["tools"] = [
        {"name": "read", "inputSchema": {"type": "string"}},
        {"name": "write"},
    ]
    changes = compare(before, after)
    assert changes["tools"] == {
        "known": True,
        "added": ["write"],
        "removed": ["old"],
        "changed": ["read"],
    }
    assert changes["security_changes"] == ["permissions"]
    assert changes["review_access"]


def test_missing_inventory_does_not_claim_removed_tools():
    assert not compare({}, {"metadata": {"tools": ["new"]}})["tools"]["known"]
    assert compare({"metadata": {"tools": ["read"]}}, {})["tools"]["removed"] == []
    assert not compare(None, {})["available"]
    assert compare(
        {"metadata": {"introspection": {"tool_names": []}}},
        {"metadata": {"tools": ["new"]}},
    )["tools"]["added"] == ["new"]


def test_scoped_inventory_does_not_expand_to_all_observed_tools():
    value = {
        "metadata": {
            "introspection": {
                "tools": [{"name": "private"}, {"name": "public"}],
                "tool_names": ["public"],
            }
        }
    }
    assert compare(value, value)["tools"] == {
        "known": True,
        "added": [],
        "removed": [],
        "changed": [],
    }


def test_baseline_survives_decisions_and_storage_serialization():
    registry, key = setup()
    result = registry.submit_tool(
        _manifest(author="alice", version="1.1.0"), changelog="Release"
    )
    mp = registry._marketplace()
    listing = mp.get(key)
    stored = mp._serialize_listing_for_storage(listing)
    restored = mp._deserialize_listing(stored, reviews=listing.reviews)
    baseline = restored.release_records[0]["base_snapshot"]
    assert baseline["version"] == "1.0.0"
    assert "release_records" not in baseline
    decide(
        registry, key, result.release_candidate["id"], "approve", "reviewer", "Checked"
    )
    assert mp.get(key).release_records[0]["base_snapshot"] == baseline
    assert compare(baseline, mp.get(key).release_records[0]["snapshot"])["fields"][
        0
    ] == {"field": "version", "before": "1.0.0", "after": "1.1.0"}


def test_publisher_summary_is_private_and_tracks_pending_release():
    registry, key = setup()
    result = registry.submit_tool(
        _manifest(author="alice", version="1.1.0"), changelog="Release"
    )
    assert registry.list_author_listings("alice")["tools"][0]["release_summary"] == {
        "version": "1.1.0",
        "status": "pending_review",
    }
    assert "release_summary" not in registry.get_verified_tool("weather-lookup")
    assert registry.list_author_listings("someone-else")["tools"] == []
    decide(
        registry,
        key,
        result.release_candidate["id"],
        "reject",
        "reviewer",
        "Fix schema",
    )
    assert (
        registry.list_author_listings("alice")["tools"][0]["release_summary"]["status"]
        == "rejected"
    )
    assert registry.get_verified_tool("weather-lookup")["version"] == "1.0.0"
