import asyncio
import json

import pytest
from starlette.testclient import TestClient

from purecipher import consumer_runtime
from tests.server.security.test_consumer_runtime import add, enabled
from tests.server.security.test_workspace_profiles import login


def test_memory_is_encrypted_scoped_and_deleted_with_connection(monkeypatch):
    app = enabled(monkeypatch)
    with TestClient(app.http_app()) as client:
        login(client)
        alice = add(client, "memory")
        login(client, "bob")
        bob = add(client, "memory")

        async def run():
            tools = {t.name: t for t in await app.list_tools()}
            context = consumer_runtime._ACCESS.set(
                {
                    "product": "memory",
                    "owner": "alice",
                    "connection_id": alice["id"],
                    "headers": {},
                }
            )
            try:
                await tools["memory_save_entity"].run(
                    {
                        "name": "Private project",
                        "observations": ["Confidential observation"],
                    }
                )
                result = await tools["memory_search"].run({"query": "project"})
                assert "Confidential observation" in str(result)
                stored = app._workspace.get(alice["id"])
                assert "Confidential observation" not in json.dumps(stored)
            finally:
                consumer_runtime._ACCESS.reset(context)
            context = consumer_runtime._ACCESS.set(
                {
                    "product": "memory",
                    "owner": "bob",
                    "connection_id": bob["id"],
                    "headers": {},
                }
            )
            try:
                assert "Confidential observation" not in str(
                    await tools["memory_search"].run({})
                )
            finally:
                consumer_runtime._ACCESS.reset(context)

        asyncio.run(run())
        login(client)
        assert (
            "utility_encrypted"
            not in client.get("/registry/workspace/connections").text
        )
        assert (
            client.delete("/registry/workspace/connections/" + alice["id"]).status_code
            == 200
        )
        assert app._workspace.get(alice["id"]) is None


def test_time_tools_require_context_and_timezone_offset(monkeypatch):
    app = enabled(monkeypatch)

    async def run():
        tools = {t.name: t for t in await app.list_tools()}
        with pytest.raises(ValueError):
            await tools["time_current"].run({})
        context = consumer_runtime._ACCESS.set({"product": "time", "headers": {}})
        try:
            result = await tools["time_convert"].run(
                {"timestamp": "2026-01-01T00:00:00+00:00", "timezone": "Asia/Kolkata"}
            )
            assert "05:30:00" in str(result)
            with pytest.raises(ValueError):
                await tools["time_convert"].run({"timestamp": "2026-01-01T00:00:00"})
        finally:
            consumer_runtime._ACCESS.reset(context)

    asyncio.run(run())


def test_custom_provider_rejects_private_network(monkeypatch):
    from purecipher.consumer_cloud import request

    async def run():
        for url in [
            "http://example.com",
            "https://127.0.0.1",
            "https://169.254.169.254",
            "https://user:secret@example.com",
            "https://example.com?token=secret",
        ]:
            with pytest.raises(ValueError):
                await request(
                    "grafana",
                    "api/search",
                    {"Authorization": "Bearer private"},
                    base=url,
                )

    asyncio.run(run())


def test_aws_never_uses_host_credentials_or_endpoint(monkeypatch):
    import boto3

    from purecipher.consumer_aws import execute

    captured = []

    class Client:
        def get_caller_identity(self):
            return {"Account": "test", "ResponseMetadata": {}}

        def close(self):
            pass

    def client(service, **kwargs):
        captured.append(kwargs)
        return Client()

    monkeypatch.setattr(boto3, "client", client)
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://untrusted.example")
    values = {
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "owner-key",
        "AWS_SECRET_ACCESS_KEY": "owner-secret",
        "AWS_SESSION_TOKEN": "owner-session",
    }
    result = asyncio.run(execute(values, "sts", "get_caller_identity", {}))
    assert result == {"Account": "test"}
    assert captured[0]["aws_access_key_id"] == "owner-key"
    assert captured[0]["aws_session_token"] == "owner-session"
    assert captured[0]["endpoint_url"] == "https://sts.us-east-1.amazonaws.com"
    with pytest.raises(ValueError):
        asyncio.run(execute({}, "sts", "get_caller_identity", {}))
    assert len(captured) == 1
