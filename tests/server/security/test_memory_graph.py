import asyncio
import json

import pytest
from starlette.testclient import TestClient

from purecipher.consumer_runtime import _ACCESS
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_workspace_profiles import login


def test_graph_changes_remain_encrypted_and_preserve_relations_on_entity_replace(
    monkeypatch,
):
    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        connection = add(client, "memory")

        async def run():
            tools = {tool.name: tool for tool in await app.list_tools()}
            token = _ACCESS.set(
                {
                    "product": "memory",
                    "owner": "alice",
                    "connection_id": connection["id"],
                    "headers": {},
                }
            )

            async def call(name, arguments=None):
                result = await tools[name].run(arguments or {})
                return json.loads(result.content[0].text)

            try:
                for name in ["Project", "Owner"]:
                    await call(
                        "memory_save_entity",
                        {"name": name, "observations": ["Private observation"]},
                    )
                relation = {
                    "source": "Owner",
                    "target": "Project",
                    "relation_type": "owns",
                }
                result = await call(
                    "memory_create_relations", {"relations": [relation, relation]}
                )
                assert result["relations"] == [relation]
                await call(
                    "memory_save_entity",
                    {"name": "Project", "observations": ["Updated"]},
                )
                await call(
                    "memory_add_observations",
                    {"name": "Project", "observations": ["Updated", "Delivery"]},
                )
                result = await call(
                    "memory_open_entities", {"names": ["Project", "Owner"]}
                )
                assert result["relations"] == [relation]
                assert next(e for e in result["entities"] if e["name"] == "Project")[
                    "observations"
                ] == ["Updated", "Delivery"]
                await call(
                    "memory_delete_observations",
                    {"name": "Project", "observations": ["Delivery"]},
                )
                assert "Delivery" not in str(await call("memory_read_graph"))
                assert "Private observation" not in json.dumps(
                    app._workspace.get(connection["id"])
                )
                result = await call(
                    "memory_delete_relations", {"relations": [relation]}
                )
                assert result == {"deleted": 1}
                await call("memory_create_relations", {"relations": [relation]})
                assert await call("memory_delete_entities", {"names": ["Owner"]}) == {
                    "deleted": 1
                }
                result = await call("memory_read_graph")
                assert result == {
                    "entities": [{"name": "Project", "observations": ["Updated"]}],
                    "relations": [],
                }
                assert (
                    tools["memory_delete_entities"].annotations.destructive_hint is True
                )
            finally:
                _ACCESS.reset(token)

        asyncio.run(run())


def test_memory_rejects_unknown_entities_oversized_changes_and_foreign_connection(
    monkeypatch,
):
    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        connection = add(client, "memory")

        async def run():
            tools = {tool.name: tool for tool in await app.list_tools()}
            token = _ACCESS.set(
                {
                    "product": "memory",
                    "owner": "alice",
                    "connection_id": connection["id"],
                    "headers": {},
                }
            )
            try:
                for name, arguments in [
                    (
                        "memory_add_observations",
                        {"name": "Missing", "observations": ["text"]},
                    ),
                    (
                        "memory_create_relations",
                        {
                            "relations": [
                                {
                                    "source": "Missing",
                                    "target": "Other",
                                    "relation_type": "owns",
                                }
                            ]
                        },
                    ),
                    ("memory_open_entities", {"names": []}),
                    ("memory_delete_entities", {"names": ["a"] * 101}),
                    (
                        "memory_delete_observations",
                        {"name": "a", "observations": ["x" * 4001]},
                    ),
                ]:
                    with pytest.raises(ValueError):
                        await tools[name].run(arguments)
                assert "utility_encrypted" not in app._workspace.get(connection["id"])
                _ACCESS.set(
                    {
                        "product": "memory",
                        "owner": "bob",
                        "connection_id": connection["id"],
                        "headers": {},
                    }
                )
                with pytest.raises(ValueError, match="no longer available"):
                    await tools["memory_read_graph"].run({})
            finally:
                _ACCESS.reset(token)

        asyncio.run(run())
