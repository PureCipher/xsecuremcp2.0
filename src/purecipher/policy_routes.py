"""Policy route mounting for the PureCipher registry layer."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


def _status_code_from_payload(payload: dict[str, Any]) -> int:
    return payload["status"] if isinstance(payload.get("status"), int) else 200


async def _load_json_body(
    request: Request,
    *,
    default: Any,
) -> Any:
    try:
        return await request.json()
    except Exception:
        return default


def _require_policy_access(
    registry: Any,
    request: Request,
    allowed_roles: set[Any],
) -> tuple[Any | None, JSONResponse | None]:
    session = registry._session_from_request(request)
    if registry.auth_enabled and session is None:
        return (
            None,
            JSONResponse(
                {"error": "Authentication required.", "status": 401},
                status_code=401,
            ),
        )
    if registry.auth_enabled and not registry._has_roles(session, allowed_roles):
        return (
            session,
            JSONResponse(
                {"error": "Reviewer or admin role required.", "status": 403},
                status_code=403,
            ),
        )
    return session, None


def mount_registry_policy_routes(
    registry: Any,
    prefix: str,
    *,
    allowed_roles: set[Any],
) -> None:
    """Mount policy management routes on the PureCipher registry."""

    @registry.custom_route(f"{prefix}/policy", methods=["GET"])
    async def registry_policy(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry.get_policy_management())

    @registry.custom_route(f"{prefix}/policy/schema", methods=["GET"])
    async def registry_policy_schema(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry._policy_api().get_policy_schema())

    @registry.custom_route(f"{prefix}/policy/bundles", methods=["GET"])
    async def registry_policy_bundles(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry.get_policy_bundles())

    @registry.custom_route(
        f"{prefix}/policy/bundles/{{bundle_id}}/stage",
        methods=["POST"],
    )
    async def registry_policy_stage_bundle(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        bundle_id = request.path_params.get("bundle_id", "")
        body = await _load_json_body(request, default={})
        payload = await registry.stage_policy_bundle(
            bundle_id,
            author=session.username if session is not None else "registry-admin",
            description=str(body.get("description", ""))
            if isinstance(body, dict)
            else "",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/environments", methods=["GET"])
    async def registry_policy_environments(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry.get_policy_environments())

    @registry.custom_route(f"{prefix}/policy/analytics", methods=["GET"])
    async def registry_policy_analytics(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry.get_policy_analytics())

    @registry.custom_route(f"{prefix}/policy/export", methods=["GET"])
    async def registry_policy_export(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        raw_version = request.query_params.get("version")
        try:
            version_number = int(raw_version) if raw_version is not None else None
        except ValueError:
            return JSONResponse(
                {"error": "Invalid `version` query parameter.", "status": 400},
                status_code=400,
            )
        payload = registry.export_policy_snapshot(version_number=version_number)
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/import", methods=["POST"])
    async def registry_policy_import(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )
        snapshot = body.get("snapshot", body) if isinstance(body, dict) else body
        description_prefix = (
            str(body.get("description_prefix", "Imported policy snapshot"))
            if isinstance(body, dict)
            else "Imported policy snapshot"
        )
        payload = await registry.import_policy_snapshot(
            snapshot,
            description_prefix=description_prefix,
            author=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/migrations/preview", methods=["POST"])
    async def registry_policy_migration_preview(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )

        payload = registry.preview_policy_migration(
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

    @registry.custom_route(f"{prefix}/policy/versions", methods=["GET"])
    async def registry_policy_versions(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry._policy_api().get_policy_versions())

    @registry.custom_route(f"{prefix}/policy/versions/diff", methods=["GET"])
    async def registry_policy_diff(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        v1 = int(request.query_params.get("v1", "0"))
        v2 = int(request.query_params.get("v2", "0"))
        payload = registry.diff_policy_versions(v1, v2)
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/proposals", methods=["GET"])
    async def registry_policy_proposals(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        return JSONResponse(registry.list_policy_proposals())

    @registry.custom_route(f"{prefix}/policy/proposals", methods=["POST"])
    async def registry_policy_create_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )
        config = body.get("config")
        payload = await registry.create_policy_proposal(
            action=str(body.get("action", "")),
            config=config if isinstance(config, dict) else None,
            target_index=(
                int(body["target_index"])
                if body.get("target_index") is not None
                else None
            ),
            description=str(body.get("description", "")),
            author=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}",
        methods=["GET"],
    )
    async def registry_policy_proposal_detail(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = registry.get_policy_proposal(proposal_id)
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/approve",
        methods=["POST"],
    )
    async def registry_policy_approve_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = registry.approve_policy_proposal(
            proposal_id,
            approver=session.username if session is not None else "registry-admin",
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/assign",
        methods=["POST"],
    )
    async def registry_policy_assign_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        proposal_id = str(request.path_params.get("proposal_id", ""))
        reviewer = str(body.get("reviewer", "")).strip()
        payload = registry.assign_policy_proposal(
            proposal_id,
            reviewer=reviewer,
            actor=session.username if session is not None else "registry-admin",
            note=str(body.get("note", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/simulate",
        methods=["POST"],
    )
    async def registry_policy_simulate_proposal(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        scenarios = body.get("scenarios")
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = await registry.simulate_policy_proposal(
            proposal_id,
            scenarios=scenarios if isinstance(scenarios, list) else None,
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/deploy",
        methods=["POST"],
    )
    async def registry_policy_deploy_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = await registry.deploy_policy_proposal(
            proposal_id,
            actor=session.username if session is not None else "registry-admin",
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/reject",
        methods=["POST"],
    )
    async def registry_policy_reject_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = registry.reject_policy_proposal(
            proposal_id,
            reason=str(body.get("reason", "")),
            actor=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(
        f"{prefix}/policy/proposals/{{proposal_id}}/withdraw",
        methods=["POST"],
    )
    async def registry_policy_withdraw_proposal(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        proposal_id = str(request.path_params.get("proposal_id", ""))
        payload = registry.withdraw_policy_proposal(
            proposal_id,
            actor=session.username if session is not None else "registry-admin",
            note=str(body.get("note", body.get("reason", ""))),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/providers", methods=["POST"])
    async def registry_policy_add_provider(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )
        config = body.get("config")
        if not isinstance(config, dict):
            return JSONResponse(
                {"error": "`config` must be an object", "status": 400},
                status_code=400,
            )
        payload = await registry.add_policy_provider(
            config,
            reason=str(body.get("reason", "")),
            author=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/providers/{{index}}", methods=["PUT"])
    async def registry_policy_update_provider(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )
        config = body.get("config")
        if not isinstance(config, dict):
            return JSONResponse(
                {"error": "`config` must be an object", "status": 400},
                status_code=400,
            )
        index = int(request.path_params.get("index", "0"))
        payload = await registry.update_policy_provider(
            index,
            config,
            reason=str(body.get("reason", "")),
            author=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/providers/{{index}}", methods=["DELETE"])
    async def registry_policy_delete_provider(request: Request) -> JSONResponse:
        session, error_response = _require_policy_access(
            registry, request, allowed_roles
        )
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default={})
        index = int(request.path_params.get("index", "0"))
        payload = await registry.delete_policy_provider(
            index,
            reason=str(body.get("reason", "")),
            author=session.username if session is not None else "registry-admin",
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))

    @registry.custom_route(f"{prefix}/policy/versions/rollback", methods=["POST"])
    async def registry_policy_rollback(request: Request) -> JSONResponse:
        _, error_response = _require_policy_access(registry, request, allowed_roles)
        if error_response is not None:
            return error_response
        body = await _load_json_body(request, default=None)
        if body is None:
            return JSONResponse(
                {"error": "Invalid JSON body", "status": 400},
                status_code=400,
            )
        version_number = int(body.get("version_number", 0))
        payload = await registry.rollback_policy_version(
            version_number,
            reason=str(body.get("reason", "")),
        )
        return JSONResponse(payload, status_code=_status_code_from_payload(payload))
