import copy

import pytest
from starlette.testclient import TestClient

from purecipher import PureCipherRegistry
from purecipher.auth import RegistryRole
from purecipher.release_candidates import decide
from tests.server.security.test_purecipher_catalog_query import (
    registry as auth_registry,
)
from tests.server.security.test_purecipher_registry import _manifest
from tests.server.security.test_workspace_profiles import login


def setup(dsn=None):
    r = PureCipherRegistry(
        signing_secret="test-secret",
        persistence_path=dsn,
        auth_settings=auth_registry()._auth_settings,
    )
    first = r.submit_tool(_manifest(author="alice"))
    assert first.accepted
    return r, first.listing.listing_id


def submit(r, version="1.1.0"):
    return r.submit_tool(
        _manifest(author="alice", version=version),
        changelog="Adds improved weather lookup",
    ).release_candidate


def test_candidate_keeps_public_snapshot_until_approval():
    r, key = setup()
    old = copy.deepcopy(r.get_verified_tool("weather-lookup"))
    candidate = submit(r)
    assert {
        k: v
        for k, v in r.get_verified_tool("weather-lookup").items()
        if k != "trust_score"
    } == {k: v for k, v in old.items() if k != "trust_score"}
    assert r._marketplace().get(key).version == "1.0.0"
    assert "release_records" not in r.get_verified_tool("weather-lookup")
    decide(r, key, candidate["id"], "approve", "reviewer", "Checked")
    assert r._marketplace().get(key).version == "1.1.0"
    assert r.get_verified_tool("weather-lookup")["verification"]["valid"]
    records = r._marketplace().get(key).release_records
    assert records[0]["previous_release"]["version"] == "1.0.0"
    assert records[0]["status"] == "approved"
    with pytest.raises(ValueError):
        decide(r, key, candidate["id"], "approve", "reviewer", "Again")


@pytest.mark.parametrize("action", ["reject", "request_changes", "withdraw"])
def test_nonapproval_does_not_change_published_release(action):
    r, key = setup()
    candidate = submit(r)
    before = copy.deepcopy(r.get_verified_tool("weather-lookup"))
    decide(r, key, candidate["id"], action, "reviewer", "Needs changes")
    # Updating review history must not change the public definition.
    assert r._marketplace().get(key).version == "1.0.0"
    assert r.get_verified_tool("weather-lookup")["manifest"] == before["manifest"]


def test_stale_duplicate_and_persistence_failure_fail_closed(monkeypatch):
    r, key = setup()
    candidate = submit(r)
    with pytest.raises(ValueError):
        submit(r, "1.2.0")
    r._marketplace().update_status(
        key,
        __import__(
            "fastmcp.server.security.gateway.tool_marketplace",
            fromlist=["PublishStatus"],
        ).PublishStatus.SUSPENDED,
    )
    with pytest.raises(ValueError):
        decide(r, key, candidate["id"], "approve", "reviewer", "")
    assert r._marketplace().get(key).version == "1.0.0"
    r, key = setup()
    backend = r._marketplace()._backend
    if backend:
        monkeypatch.setattr(
            backend,
            "save_tool_listing",
            lambda *a: (_ for _ in ()).throw(RuntimeError("storage down")),
        )
        with pytest.raises(RuntimeError):
            submit(r)
        assert not r._marketplace().get(key).release_records


def test_http_roles_owner_and_snapshot_immutability():
    r, key = setup()
    candidate = submit(r)
    r._account_security.create_account(
        username="reviewer",
        password="fixture-password",
        role=RegistryRole.REVIEWER,
        display_name="Reviewer",
    )
    with TestClient(r.http_app()) as c:
        path = "/registry/releases/" + key
        assert c.get(path).status_code == 401
        login(c, "bob")
        assert c.get(path).status_code == 404
        forged = c.post(
            "/registry/submit",
            json={
                "manifest": _manifest(author="alice", version="1.2.0").to_dict(),
                "changelog": "Forged",
            },
        )
        assert forged.status_code == 403
        login(c)
        assert (
            c.post(
                path, json={"candidate_id": candidate["id"], "action": "approve"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                path,
                json={
                    "candidate_id": candidate["id"],
                    "action": "edit",
                    "snapshot": {},
                },
            ).status_code
            == 403
        )
        login(c, "reviewer")
        result = c.post(
            path,
            json={
                "candidate_id": candidate["id"],
                "action": "approve",
                "snapshot": {"version": "9.0.0"},
            },
        )
        assert result.status_code == 200, result.text
        assert r._marketplace().get(key).version == "1.1.0"


def test_postgres_candidate_and_promotion_survive_reload(registry_dsn):
    r, key = setup(registry_dsn)
    candidate = submit(r)
    fresh = PureCipherRegistry(
        signing_secret="test-secret", persistence_path=registry_dsn
    )
    assert fresh._marketplace().get(key).version == "1.0.0"
    assert fresh._marketplace().get(key).release_records[0]["id"] == candidate["id"]
    decide(fresh, key, candidate["id"], "approve", "reviewer", "Checked")
    latest = PureCipherRegistry(
        signing_secret="test-secret", persistence_path=registry_dsn
    )
    assert latest._marketplace().get(key).version == "1.1.0"
    assert (
        latest._marketplace().get(key).release_records[0]["previous_release"]["version"]
        == "1.0.0"
    )


def test_storage_failure_does_not_promote_and_reload_keeps_candidate(monkeypatch):
    from fastmcp.server.security.storage.memory import MemoryBackend

    r, key = setup()
    mp = r._marketplace()
    backend = MemoryBackend()
    mp._backend = backend
    mp._persist_listing(mp.get(key))
    candidate = submit(r)
    mp._load_from_backend()
    assert mp.get(key).version == "1.0.0"
    assert mp.get(key).release_records[0]["id"] == candidate["id"]

    def unavailable(*args):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(backend, "save_tool_listing", unavailable)
    with pytest.raises(RuntimeError):
        decide(r, key, candidate["id"], "approve", "reviewer", "")
    assert mp.get(key).version == "1.0.0"
    assert mp.get(key).release_records[0]["status"] == "pending_review"


def test_candidate_tampering_and_invalid_versions_are_rejected():
    r, key = setup()
    for version in ("1.0.0", "0.9.0", "latest"):
        with pytest.raises(ValueError):
            submit(r, version)
    candidate = submit(r)
    r._marketplace().get(key).release_records[0]["snapshot"]["version"] = "9.0.0"
    with pytest.raises(ValueError):
        decide(r, key, candidate["id"], "approve", "reviewer", "")
    assert r._marketplace().get(key).version == "1.0.0"
