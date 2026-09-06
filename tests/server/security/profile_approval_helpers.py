"""Explicit test-owner consent and test-administrator approval through HTTP."""

import asyncio

from fastmcp.server.security.contracts.schema import (
    ContractNegotiationRequest,
    ContractTerm,
)
from purecipher.auth import RegistryRole


def approve_profile(app, client, profile, grant_controls=True):
    owner = profile["owner"]
    if grant_controls:
        for client_id in profile["client_ids"]:
            actor = app._client_store.get_client(client_id)
            names = sorted(
                {name for selected in profile["servers"] for name in selected["tools"]}
            )
            asyncio.run(
                app._broker_or_none().negotiate(
                    ContractNegotiationRequest(
                        agent_id=actor.slug,
                        proposed_terms=[
                            ContractTerm(
                                description="Fixture profile access",
                                constraint={
                                    "allowed_actions": ["call_tool"],
                                    "allowed_resources": names,
                                },
                            )
                        ],
                    )
                )
            )
            app._consent_graph_or_none().grant(
                app._required_context().config.consent.resource_owner,
                actor.slug,
                {"execute"},
                granted_by="fixture-approver",
            )
    app._account_security.create_account(
        username="fixture-approver",
        password="fixture-password",
        display_name="Test administrator",
        role=RegistryRole.ADMIN,
    )
    path = "/registry/workspace/profiles/" + profile["id"] + "/governance"

    def action(name, **extra):
        data = client.get(path).json()
        response = client.post(
            path,
            json={
                "action": name,
                "profile_revision": data["profile_revision"],
                "approval_revision": (data["approval"] or {}).get("revision"),
                **extra,
            },
        )
        assert response.status_code == 200, response.text

    action("request")
    action("consent", confirmed=True)
    assert (
        client.post(
            "/registry/login",
            json={"username": "fixture-approver", "password": "fixture-password"},
        ).status_code
        == 200
    )
    action("approve", days=1)
    assert (
        client.post(
            "/registry/login", json={"username": owner, "password": "fixture-password"}
        ).status_code
        == 200
    )
    response = client.put(
        "/registry/workspace/profiles/" + profile["id"],
        json={**profile, "status": "active"},
    )
    assert response.status_code == 200, response.text
    return response.json()
