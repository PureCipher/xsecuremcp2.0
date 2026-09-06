"""Publisher identity is public independently of unpublished server submissions."""

from starlette.testclient import TestClient

from fastmcp.server.security.gateway.tool_marketplace import PublishStatus
from purecipher import PureCipherRegistry
from purecipher.auth import RegistryRole


def test_registered_publisher_profile_does_not_expose_drafts_or_account_details():
    registry = PureCipherRegistry(signing_secret="publisher-profile-test-secret")
    for username, role in [
        ("purecipher", RegistryRole.PUBLISHER),
        ("admin", RegistryRole.ADMIN),
        ("reader", RegistryRole.VIEWER),
        ("disabled", RegistryRole.PUBLISHER),
    ]:
        registry._account_security.create_account(
            username=username,
            password="fixture-password",
            role=role,
            display_name="PureCipher" if username == "purecipher" else username,
        )
    registry._account_security.update_account(username="disabled", disabled=True)
    registry._marketplace().publish(
        "private-google-draft",
        author="purecipher",
        status=PublishStatus.DRAFT,
        tags={"private-tag"},
        metadata={"private": "hidden"},
    )
    with TestClient(registry.http_app()) as client:
        directory = client.get("/registry/publishers")
        assert directory.status_code == 200
        assert directory.json()["count"] == 1
        summary = directory.json()["publishers"][0]
        assert summary["publisher_id"] == "purecipher"
        assert summary["display_name"] == "PureCipher"
        assert summary["listing_count"] == 0
        assert summary["average_trust"] is None
        profile = client.get("/registry/publishers/purecipher")
        assert profile.status_code == 200
        assert profile.json()["listings"] == []
        assert profile.json()["tags"] == []
        assert profile.json()["latest_activity"] == ""
        for private in [
            "private-google-draft",
            "private-tag",
            "password",
            "disabled_at",
            "fixture-password",
        ]:
            assert private not in profile.text
        assert client.get("/registry/publishers/unknown").status_code == 404


def test_published_listing_merges_with_registered_publisher():
    registry = PureCipherRegistry(signing_secret="publisher-profile-test-secret")
    registry._account_security.create_account(
        username="purecipher",
        password="fixture-password",
        role=RegistryRole.PUBLISHER,
        display_name="PureCipher",
    )
    registry._marketplace().publish("public-tool", author="purecipher")
    directory = registry.list_publishers()
    assert directory["count"] == 1
    assert directory["publishers"][0]["display_name"] == "PureCipher"
    assert directory["publishers"][0]["listing_count"] == 1
    profile = registry.get_publisher_profile("purecipher")
    assert [listing["tool_name"] for listing in profile["listings"]] == ["public-tool"]
