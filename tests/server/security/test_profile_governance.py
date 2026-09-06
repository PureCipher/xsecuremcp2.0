"""Profile grants cannot be reused across scope, owner, or revision boundaries."""

from types import SimpleNamespace

from starlette.testclient import TestClient

from purecipher.auth import RegistryRole
from purecipher.profile_governance import blockers, fingerprint
from tests.server.security.test_purecipher_catalog_query import registry
from tests.server.security.test_workspace_profiles import login


def fixture():
    app = registry()
    app._account_security.create_account(
        username="approver",
        password="fixture-password",
        role=RegistryRole.ADMIN,
        display_name="Approver",
    )
    profile = app._workspace.save(
        {
            "id": "test-profile",
            "kind": "profile",
            "owner": "alice",
            "name": "Research",
            "purpose": "Read selected tools",
            "status": "inactive",
            "client_ids": ["client-1"],
            "servers": [{"listing_id": "listing-1", "tools": ["read"]}],
        }
    )
    return app, profile


def post(c, profile, action, **extra):
    path = f"/registry/workspace/profiles/{profile['id']}/governance"
    current = c.get(path).json()
    return c.post(
        path,
        json={
            "action": action,
            "profile_revision": current["profile_revision"],
            "approval_revision": (current["approval"] or {}).get("revision"),
            **extra,
        },
    )


def test_owner_admin_separation_and_stale_revision():
    app, profile = fixture()
    with TestClient(app.http_app()) as c:
        path = f"/registry/workspace/profiles/{profile['id']}/governance"
        assert c.get(path).status_code == 401
        login(c, "bob")
        assert c.get(path).status_code == 404
        login(c)
        assert post(c, profile, "request").status_code == 200
        assert post(c, profile, "approve").status_code == 403
        assert post(c, profile, "consent", confirmed=False).status_code == 400
        assert post(c, profile, "consent", confirmed=True).status_code == 200
        assert (
            c.post(
                path,
                json={
                    "action": "revoke",
                    "profile_revision": 1,
                    "approval_revision": 1,
                },
            ).status_code
            == 400
        )
        login(c, "approver")
        assert post(c, profile, "consent", confirmed=True).status_code == 403
        assert c.get("/registry/admin/profile-governance").json()["requests"]
        login(c)
        assert post(c, profile, "revoke").status_code == 200
        assert blockers(app, profile)
        assert c.get("/registry/admin/profile-governance").status_code == 403


def test_bound_contract_selection_live_revocation_and_scope_invalidation(monkeypatch):
    from purecipher.profile_governance import bindings

    app, profile = fixture()
    client = SimpleNamespace(slug="client-agent")
    bad = SimpleNamespace(
        contract_id="a", agent_id="client-agent", terms=[], is_valid=lambda: True
    )
    good = SimpleNamespace(
        contract_id="b", agent_id="client-agent", terms=[], is_valid=lambda: True
    )
    broker = SimpleNamespace(
        get_active_contracts_for_agent=lambda agent: [bad, good],
        get_contract=lambda key: good if key == "b" else bad,
    )
    monkeypatch.setattr(app._client_store, "get_client", lambda key: client)
    monkeypatch.setattr(app, "_broker_or_none", lambda: broker)
    monkeypatch.setattr(
        "purecipher.profile_governance.ContractValidationMiddleware._check_term_constraint",
        lambda self, item, action, name: "denied" if item.contract_id == "a" else None,
    )
    graph = app._consent_graph_or_none()
    graph.grant("server", "client-agent", {"execute"}, granted_by="approver")
    assert bindings(app, profile)[0]["contract_id"] == "b"
    with TestClient(app.http_app()) as c:
        login(c)
        assert post(c, profile, "request").status_code == 200
        assert post(c, profile, "consent", confirmed=True).status_code == 200
        login(c, "approver")
        assert post(c, profile, "approve", days=1).status_code == 200
        assert blockers(app, profile) == []
        assert blockers(app, {**profile, "id": "other-profile"})
        assert blockers(app, {**profile, "purpose": "Different purpose"})
        assert blockers(
            app,
            {**profile, "servers": [{"listing_id": "listing-1", "tools": ["write"]}]},
        )
        assert blockers(app, {**profile, "status": "active"}) == []
        good.is_valid = lambda: False
        assert "contract" in " ".join(blockers(app, profile))
        good.is_valid = lambda: True
        grant = app._workspace.get("governance-" + profile["id"])
        grant["expires_at"] = 0
        app._workspace.save(grant, grant["revision"])
        assert "expired" in " ".join(blockers(app, profile))


def test_fingerprint_includes_per_client_restrictions_and_connection():
    _, profile = fixture()
    for selection in [
        {
            "listing_id": "listing-1",
            "tools": ["read"],
            "client_tools": {"client-1": []},
        },
        {"listing_id": "listing-1", "tools": ["read"], "connection_id": "new-account"},
    ]:
        assert fingerprint(profile) != fingerprint({**profile, "servers": [selection]})


def test_profile_approval_persists_in_postgres(registry_dsn):
    from purecipher.workspace import WorkspaceStore

    app, profile = fixture()
    app._workspace = WorkspaceStore(registry_dsn)
    app._workspace.save({key: value for key, value in profile.items() if key != "revision"})
    with TestClient(app.http_app()) as client:
        login(client)
        assert post(client, profile, "request").status_code == 200
        assert post(client, profile, "consent", confirmed=True).status_code == 200
        before = app._workspace.get("governance-" + profile["id"])
        reopened = WorkspaceStore(registry_dsn)
        assert reopened.get(before["id"]) == before
        assert reopened.list_kind("profile_governance") == [before]
        assert before["owner_consented"] is True
        assert before["history"][-1]["action"] == "consent"
        app._workspace = reopened
        assert post(client, profile, "revoke").status_code == 200
        assert WorkspaceStore(registry_dsn).get(before["id"])["status"] == "revoked"
