"""Profile endpoints reuse the existing SecureMCP stack and narrow tool access."""

from __future__ import annotations

from starlette.responses import JSONResponse

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware
from purecipher.workspace import allowed_profile_tools


class ProfileBoundary:
    def __init__(self, app, registry, mcp_path="/mcp", guard_only=False):
        self.guard_only = guard_only
        self.app, self.registry, self.path = app, registry, mcp_path.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        path = scope["path"]
        profile_id = (
            path[len(self.path + "/profiles/") :].strip("/")
            if path.startswith(self.path + "/profiles/")
            else None
        )
        # Strip the internal header on every request. Only the endpoint sets it.
        scope = {
            **scope,
            "headers": [
                (k, v)
                for k, v in scope.get("headers", [])
                if k.lower() != b"x-purecipher-profile"
            ],
        }
        if profile_id and self.guard_only:
            return await self.app(scope, receive, send)
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        resolved = (
            self.registry.authenticate_client_token(token)
            if token.startswith("pcc_")
            else None
        )
        binding = (
            self.registry._workspace.get(resolved[0].client_id) if resolved else None
        )
        if profile_id or (token.startswith("pcc_") and not resolved) or binding:
            try:
                if not profile_id or not resolved:
                    raise ValueError(
                        "Use your assigned profile endpoint with a valid client token"
                    )
                allowed_profile_tools(self.registry, profile_id, resolved[0])
            except ValueError as exc:
                return await JSONResponse(
                    {"error": str(exc)}, status_code=403 if resolved else 401
                )(scope, receive, send)
            # A profile client cannot access unrelated HTTP APIs with its token.
            scope = {
                **scope,
                "path": self.path,
                "raw_path": self.path.encode(),
                "headers": [
                    *scope["headers"],
                    (b"x-purecipher-profile", profile_id.encode()),
                ],
            }
        return await self.app(scope, receive, send)


class ProfileToolAccess(Middleware):
    def __init__(self, registry):
        self.registry = registry

    def allowed(self):
        headers = get_http_headers(include={"authorization"})
        profile_id = headers.get("x-purecipher-profile")
        if not profile_id:
            return None
        token = headers.get("authorization", "")[7:].strip()
        resolved = self.registry.authenticate_client_token(token)
        if not resolved:
            raise ValueError("Client token revoked or client suspended")
        return allowed_profile_tools(self.registry, profile_id, resolved[0])

    async def on_call_tool(self, context, call_next):
        allowed = self.allowed()
        if allowed is not None and context.message.name not in allowed:
            raise ValueError("This tool is not enabled in the profile")
        if context.message.name in getattr(
            self.registry, "_consumer_tool_products", {}
        ):
            from purecipher.consumer_runtime import _ACCESS, resolve_access

            headers = get_http_headers(include={"authorization"})
            resolved = self.registry.authenticate_client_token(
                headers.get("authorization", "")[7:].strip()
            )
            if allowed is None or not resolved:
                raise ValueError(
                    "Consumer tools require an assigned profile and your own connection"
                )
            value = await resolve_access(
                self.registry,
                headers["x-purecipher-profile"],
                resolved[0],
                context.message.name,
            )
            reset = _ACCESS.set(value)
            try:
                return await call_next(context)
            finally:
                _ACCESS.reset(reset)
        return await call_next(context)

    async def on_list_tools(self, context, call_next):
        allowed = self.allowed()
        tools = await call_next(context)
        return (
            tools
            if allowed is None
            else [tool for tool in tools if tool.name in allowed]
        )

    async def on_message(self, context, call_next):
        allowed = self.allowed()
        if allowed is not None and context.method not in {
            "tools/call",
            "tools/list",
            "initialize",
            "ping",
            "notifications/initialized",
            "notifications/cancelled",
        }:
            raise ValueError("Profiles currently permit selected tools only")
        return await call_next(context)
