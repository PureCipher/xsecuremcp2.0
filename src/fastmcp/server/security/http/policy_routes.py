"""Policy HTTP route mounting for SecureMCP security APIs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


def _status_code_from_payload(payload: dict[str, Any]) -> int:
    return payload["status"] if isinstance(payload.get("status"), int) else 200


def mount_policy_routes(
    server: Any,
    api: Any,
    prefix: str,
    *,
    route_decorator: Callable[..., Callable[[Callable], Callable]] | None = None,
) -> None:
    """Mount policy-related HTTP routes onto a SecureMCP server.

    Args:
        server: The FastMCP server instance.
        api: The shared SecurityAPI handle.
        prefix: URL prefix.
        route_decorator: Optional override that wraps each route's
            handler before registration. When provided, used in place of
            ``server.custom_route``. The auth-aware decorator from
            :func:`fastmcp.server.security.http.api.mount_security_routes`
            is plumbed through here so policy endpoints inherit the
            same authentication enforcement as the rest of the API.
    """
    if route_decorator is None:
        # Back-compat: callers that don't pass a decorator get the raw
        # ``server.custom_route``. ``mount_security_routes`` always
        # passes the secured wrapper so the security HTTP API is
        # auth-gated end-to-end.
        def _default(path: str, *, methods: list[str]):
            return server.custom_route(path, methods=methods)

        _route = _default
    else:
        _route = route_decorator

    @_route(f"{prefix}/policy", methods=["GET"])
    async def policy_status_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_status())

    @_route(f"{prefix}/policy/audit", methods=["GET"])
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

    @_route(f"{prefix}/policy/audit/stats", methods=["GET"])
    async def policy_audit_stats_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_audit_statistics())

    @_route(f"{prefix}/policy/simulate", methods=["POST"])
    async def policy_simulate_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        scenarios = body.get("scenarios", [])
        result = await api.simulate_policy(scenarios)
        return JSONResponse(result)

    @_route(f"{prefix}/policy/schema", methods=["GET"])
    async def policy_schema_endpoint(request: Request) -> JSONResponse:
        jurisdiction = request.query_params.get("jurisdiction")
        category = request.query_params.get("category")
        return JSONResponse(
            api.get_policy_schema(jurisdiction=jurisdiction, category=category)
        )

    @_route(f"{prefix}/policy/bundles", methods=["GET"])
    async def policy_bundles_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_bundles())

    @_route(f"{prefix}/policy/packs", methods=["GET"])
    async def policy_packs_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_packs())

    @_route(f"{prefix}/policy/packs", methods=["POST"])
    async def policy_packs_save_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        payload = await api.save_policy_pack(
            title=str(body.get("title", "")),
            summary=str(body.get("summary", "")),
            description=str(body.get("description", "")),
            snapshot=body.get("snapshot") if body.get("snapshot") is not None else None,
            source_version_number=(
                int(body["source_version_number"])
                if body.get("source_version_number") is not None
                else None
            ),
            author=str(body.get("author", "api")),
            pack_id=str(body.get("pack_id")) if body.get("pack_id") else None,
            tags=list(body.get("tags", [])) if isinstance(body.get("tags"), list) else None,
            recommended_environments=(
                list(body.get("recommended_environments", []))
                if isinstance(body.get("recommended_environments"), list)
                else None
            ),
            note=str(body.get("note", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(f"{prefix}/policy/packs/{{pack_id}}", methods=["DELETE"])
    async def policy_packs_delete_endpoint(request: Request) -> JSONResponse:
        pack_id = request.path_params.get("pack_id", "")
        payload = api.delete_policy_pack(str(pack_id))
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(
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

    @_route(f"{prefix}/policy/packs/{{pack_id}}/stage", methods=["POST"])
    async def policy_pack_stage_endpoint(request: Request) -> JSONResponse:
        pack_id = request.path_params.get("pack_id", "")
        body = await request.json()
        payload = await api.stage_policy_pack(
            str(pack_id),
            author=str(body.get("author", "api")),
            description=str(body.get("description", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(f"{prefix}/policy/environments", methods=["GET"])
    async def policy_environments_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_environment_profiles())

    @_route(
        f"{prefix}/policy/environments/{{environment_id}}/capture", methods=["POST"]
    )
    async def policy_environment_capture_endpoint(request: Request) -> JSONResponse:
        environment_id = request.path_params.get("environment_id", "")
        body = await request.json()
        payload = api.capture_policy_environment(
            str(environment_id),
            actor=str(body.get("actor", "api")),
            note=str(body.get("note", "")),
            source_snapshot=(
                body.get("source_snapshot")
                if isinstance(body.get("source_snapshot"), dict)
                else None
            ),
            source_version_number=(
                int(body["source_version_number"])
                if body.get("source_version_number") is not None
                else None
            ),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(f"{prefix}/policy/promotions", methods=["GET"])
    async def policy_promotions_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_promotions())

    @_route(f"{prefix}/policy/promotions", methods=["POST"])
    async def policy_promotions_stage_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        payload = await api.stage_policy_promotion(
            source_environment=str(body.get("source_environment", "")),
            target_environment=str(body.get("target_environment", "")),
            author=str(body.get("author", "api")),
            description=str(body.get("description", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(f"{prefix}/policy/analytics", methods=["GET"])
    async def policy_analytics_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_analytics())

    @_route(f"{prefix}/policy/export", methods=["GET"])
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

    @_route(f"{prefix}/policy/migrations/preview", methods=["POST"])
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

    @_route(f"{prefix}/policy/import", methods=["POST"])
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

    @_route(f"{prefix}/policy/versions", methods=["GET"])
    async def policy_versions_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_versions())

    @_route(f"{prefix}/policy/versions/rollback", methods=["POST"])
    async def policy_rollback_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        version_number = body.get("version_number", 0)
        reason = body.get("reason", "")
        return JSONResponse(await api.rollback_policy_version(version_number, reason))

    @_route(f"{prefix}/policy/versions/diff", methods=["GET"])
    async def policy_diff_endpoint(request: Request) -> JSONResponse:
        v1 = int(request.query_params.get("v1", "0"))
        v2 = int(request.query_params.get("v2", "0"))
        return JSONResponse(api.diff_policy_versions(v1, v2))

    @_route(f"{prefix}/policy/validate", methods=["POST"])
    async def policy_validate_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        config = body.get("config", {})
        return JSONResponse(api.validate_policy(config))

    @_route(f"{prefix}/policy/validate/providers", methods=["GET"])
    async def policy_validate_providers_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.validate_providers())

    @_route(f"{prefix}/policy/metrics", methods=["GET"])
    async def policy_metrics_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_policy_metrics())

    @_route(f"{prefix}/policy/alerts", methods=["GET"])
    async def policy_alerts_endpoint(request: Request) -> JSONResponse:
        limit = int(request.query_params.get("limit", "50"))
        return JSONResponse(api.get_policy_alerts(limit=limit))

    @_route(f"{prefix}/policy/governance", methods=["GET"])
    async def policy_governance_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(api.get_governance_proposals())

    @_route(f"{prefix}/policy/governance/{{proposal_id}}", methods=["GET"])
    async def policy_governance_detail_endpoint(request: Request) -> JSONResponse:
        proposal_id = request.path_params.get("proposal_id", "")
        return JSONResponse(api.get_governance_proposal(proposal_id))

    @_route(f"{prefix}/policy/governance/proposals", methods=["POST"])
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
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @_route(
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

    @_route(
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

    @_route(
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

    @_route(
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

    @_route(
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

    @_route(
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

    @_route(f"{prefix}/policy/plugins", methods=["GET"])
    async def policy_plugins_endpoint(request: Request) -> JSONResponse:
        """List all registered policy type plugins."""
        from fastmcp.server.security.policy.plugin_registry import get_registry

        jurisdiction = request.query_params.get("jurisdiction")
        category = request.query_params.get("category")
        registry = get_registry()
        plugins = registry.dump_plugin_list(
            jurisdiction=jurisdiction, category=category
        )
        return JSONResponse({"plugins": plugins, "count": len(plugins)})
