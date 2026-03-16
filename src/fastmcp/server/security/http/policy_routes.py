"""Policy HTTP route mounting for SecureMCP security APIs."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


def _status_code_from_payload(payload: dict[str, Any]) -> int:
    return payload["status"] if isinstance(payload.get("status"), int) else 200


def mount_policy_routes(server: Any, api: Any, prefix: str) -> None:
    """Mount policy-related HTTP routes onto a SecureMCP server."""

    @server.custom_route(f"{prefix}/policy", methods=["GET"])
    async def policy_status_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_status())

    @server.custom_route(f"{prefix}/policy/audit", methods=["GET"])
    async def policy_audit_endpoint(request: Request) -> JSONResponse:
        actor = request.query_params.get("actor")
        resource = request.query_params.get("resource")
        decision = request.query_params.get("decision")
        limit = int(request.query_params.get("limit", "50"))
        return JSONResponse(
            api.get_policy_audit(
                actor_id=actor,
                resource_id=resource,
                decision=decision,
                limit=limit,
            )
        )

    @server.custom_route(f"{prefix}/policy/audit/stats", methods=["GET"])
    async def policy_audit_stats_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_audit_statistics())

    @server.custom_route(f"{prefix}/policy/simulate", methods=["POST"])
    async def policy_simulate_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        scenarios = body.get("scenarios", [])
        result = await api.simulate_policy(scenarios)
        return JSONResponse(result)

    @server.custom_route(f"{prefix}/policy/schema", methods=["GET"])
    async def policy_schema_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_schema())

    @server.custom_route(f"{prefix}/policy/bundles", methods=["GET"])
    async def policy_bundles_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_bundles())

    @server.custom_route(
        f"{prefix}/policy/bundles/{{bundle_id}}/stage", methods=["POST"]
    )
    async def policy_bundle_stage_endpoint(request: Request) -> JSONResponse:
        bundle_id = request.path_params.get("bundle_id", "")
        body = await request.json()
        payload = await api.stage_policy_bundle(
            bundle_id,
            author=str(body.get("author", "api")),
            description=str(body.get("description", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(f"{prefix}/policy/environments", methods=["GET"])
    async def policy_environments_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_environment_profiles())

    @server.custom_route(f"{prefix}/policy/analytics", methods=["GET"])
    async def policy_analytics_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_analytics())

    @server.custom_route(f"{prefix}/policy/export", methods=["GET"])
    async def policy_export_endpoint(request: Request) -> JSONResponse:
        raw_version = request.query_params.get("version")
        try:
            version_number = int(raw_version) if raw_version is not None else None
        except ValueError:
            return JSONResponse(
                {"error": "Invalid `version` query parameter.", "status": 400},
                status_code=400,
            )
        payload = api.export_policy_snapshot(version_number=version_number)
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(f"{prefix}/policy/migrations/preview", methods=["POST"])
    async def policy_migration_preview_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        payload = api.preview_policy_migration(
            source_snapshot=body.get("source_snapshot")
            if isinstance(body.get("source_snapshot"), dict)
            else None,
            source_version_number=(
                int(body["source_version_number"])
                if body.get("source_version_number") is not None
                else None
            ),
            target_version_number=(
                int(body["target_version_number"])
                if body.get("target_version_number") is not None
                else None
            ),
            target_environment=str(body.get("target_environment", "staging")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(f"{prefix}/policy/import", methods=["POST"])
    async def policy_import_endpoint(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        snapshot = body.get("snapshot", body) if isinstance(body, dict) else body
        author = str(body.get("author", "api")) if isinstance(body, dict) else "api"
        description_prefix = (
            str(body.get("description_prefix", "Imported policy snapshot"))
            if isinstance(body, dict)
            else "Imported policy snapshot"
        )
        payload = await api.import_policy_snapshot(
            snapshot,
            author=author,
            description_prefix=description_prefix,
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(f"{prefix}/policy/versions", methods=["GET"])
    async def policy_versions_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_versions())

    @server.custom_route(f"{prefix}/policy/versions/rollback", methods=["POST"])
    async def policy_rollback_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        version_number = body.get("version_number", 0)
        reason = body.get("reason", "")
        return JSONResponse(await api.rollback_policy_version(version_number, reason))

    @server.custom_route(f"{prefix}/policy/versions/diff", methods=["GET"])
    async def policy_diff_endpoint(request: Request) -> JSONResponse:
        v1 = int(request.query_params.get("v1", "0"))
        v2 = int(request.query_params.get("v2", "0"))
        return JSONResponse(api.diff_policy_versions(v1, v2))

    @server.custom_route(f"{prefix}/policy/validate", methods=["POST"])
    async def policy_validate_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        config = body.get("config", {})
        return JSONResponse(api.validate_policy(config))

    @server.custom_route(f"{prefix}/policy/validate/providers", methods=["GET"])
    async def policy_validate_providers_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.validate_providers())

    @server.custom_route(f"{prefix}/policy/metrics", methods=["GET"])
    async def policy_metrics_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_metrics())

    @server.custom_route(f"{prefix}/policy/alerts", methods=["GET"])
    async def policy_alerts_endpoint(request: Request) -> JSONResponse:
        limit = int(request.query_params.get("limit", "50"))
        return JSONResponse(api.get_policy_alerts(limit=limit))

    @server.custom_route(f"{prefix}/policy/governance", methods=["GET"])
    async def policy_governance_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_governance_proposals())

    @server.custom_route(f"{prefix}/policy/governance/{{proposal_id}}", methods=["GET"])
    async def policy_governance_detail_endpoint(request: Request) -> JSONResponse:
        proposal_id = request.path_params.get("proposal_id", "")
        return JSONResponse(api.get_governance_proposal(proposal_id))

    @server.custom_route(f"{prefix}/policy/governance/proposals", methods=["POST"])
    async def policy_governance_create_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        payload = await api.create_governance_proposal(
            action=str(body.get("action", "")),
            config=body.get("config") if isinstance(body.get("config"), dict) else None,
            target_index=(
                int(body["target_index"])
                if body.get("target_index") is not None
                else None
            ),
            description=str(body.get("description", "")),
            author=str(body.get("author", "api")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/approve",
        methods=["POST"],
    )
    async def policy_governance_approve_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        payload = api.approve_governance_proposal(
            proposal_id,
            approver=str(body.get("approver", "api")),
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/assign",
        methods=["POST"],
    )
    async def policy_governance_assign_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        payload = api.assign_governance_proposal(
            proposal_id,
            reviewer=str(body.get("reviewer", "")),
            actor=str(body.get("actor", "api")),
            note=str(body.get("note", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/simulate",
        methods=["POST"],
    )
    async def policy_governance_simulate_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        scenarios = body.get("scenarios")
        payload = await api.simulate_governance_proposal(
            proposal_id,
            scenarios_data=scenarios if isinstance(scenarios, list) else [],
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/deploy",
        methods=["POST"],
    )
    async def policy_governance_deploy_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        payload = await api.deploy_governance_proposal(
            proposal_id,
            actor=str(body.get("actor", "api")),
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/reject",
        methods=["POST"],
    )
    async def policy_governance_reject_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        payload = api.reject_governance_proposal(
            proposal_id,
            reason=str(body.get("reason", "")),
            actor=str(body.get("actor", "api")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @server.custom_route(
        f"{prefix}/policy/governance/{{proposal_id}}/withdraw",
        methods=["POST"],
    )
    async def policy_governance_withdraw_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        proposal_id = request.path_params.get("proposal_id", "")
        payload = api.withdraw_governance_proposal(
            proposal_id,
            actor=str(body.get("actor", "api")),
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))
