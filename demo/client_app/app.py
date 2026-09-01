"""PureCipher Agent Client — a UI-based demo client.

Demonstrates an agent application that:
  1. registers itself as a client identity in the Secured MCP Registry,
  2. browses the registry's catalog of proxy-hosted MCP servers,
  3. connects to one through the governance proxy with its issued token,
  4. lists that server's tools and calls them — every call governed
     (allowlist + provenance always on) and recorded in the ledger.

This is a thin Starlette backend (so the browser never has to speak the
MCP streamable-HTTP protocol or fight CORS) with a single-page UI. The
backend uses the real ``fastmcp.Client`` against the registry proxy —
the same client path the rest of the demo narrates.

Run:
    uv run python demo/client_app/app.py
    # then open http://localhost:8800

Env:
    REGISTRY_URL   registry API base (default http://localhost:8000;
                   auto-detects 8001 if 8000 is down)
    CLIENT_APP_PORT  UI port (default 8800)
    ADMIN_USER / ADMIN_PASS  admin creds for live registration
                   (default admin / admin123; ignored if auth disabled)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTRY = os.getenv("REGISTRY_URL", "http://localhost:8000").rstrip("/")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
UI_PORT = int(os.getenv("CLIENT_APP_PORT", "8800"))


# --------------------------------------------------------------------------
# Registry HTTP helpers (server-to-server; the browser never calls these)
# --------------------------------------------------------------------------
def _registry_call(
    method: str,
    base: str,
    path: str,
    body: dict | None = None,
    token: str = "",
) -> tuple[int, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"error": raw[:400]}
    except urllib.error.URLError as exc:
        return 0, {"error": f"cannot reach registry at {base}: {exc.reason}"}


def _resolve_registry() -> str:
    """Return a reachable registry base, auto-detecting the CLI's 8001 default."""
    candidates = [
        DEFAULT_REGISTRY,
        "http://localhost:8001",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://127.0.0.1:8000",
    ]
    seen: set[str] = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        status, _ = _registry_call("GET", base, "/registry/health")
        if status == 200:
            return base
    return DEFAULT_REGISTRY


def _admin_token(base: str, username: str, password: str) -> tuple[str, str | None]:
    """Return (token, error). Empty token + None error means auth is disabled."""
    status, payload = _registry_call(
        "POST", base, "/registry/login", {"username": username, "password": password}
    )
    if status == 200 and payload.get("token"):
        return payload["token"], None
    if "auth is disabled" in str(payload.get("error", "")).lower():
        return "", None  # tokenless; endpoints are open
    return "", str(payload.get("error") or f"login failed (HTTP {status})")


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------
async def api_state(request: Request) -> JSONResponse:
    base = _resolve_registry()
    status, session = _registry_call("GET", base, "/registry/session")
    auth_enabled = bool(session.get("auth_enabled")) if status == 200 else None
    return JSONResponse(
        {
            "registry_url": base,
            "reachable": status == 200,
            "auth_enabled": auth_enabled,
            "console_url": "http://localhost:3000/registry",
        }
    )


async def api_register(request: Request) -> JSONResponse:
    body = await request.json()
    base = _resolve_registry()
    username = body.get("admin_user") or ADMIN_USER
    password = body.get("admin_pass") or ADMIN_PASS
    token, err = _admin_token(base, username, password)
    if err:
        return JSONResponse({"error": err}, status_code=401)

    display = body.get("display_name") or "Agent Client Demo"
    slug = body.get("slug") or "agent-client-demo"
    status, payload = _registry_call(
        "POST",
        base,
        "/registry/clients",
        {
            "display_name": display,
            "slug": slug,
            "description": "UI-based agent app connecting through the PureCipher proxy.",
            "intended_use": "Live demo of governed MCP access.",
            "kind": "agent",
            "issue_initial_token": True,
            "token_name": "agent-client-demo-token",
        },
        token=token,
    )
    if status not in (200, 201):
        return JSONResponse(
            {
                "error": payload.get("error")
                or f"client registration failed (HTTP {status})"
            },
            status_code=400,
        )
    return JSONResponse(
        {
            "slug": slug,
            "display_name": display,
            "secret": payload.get("secret"),
            "client": payload.get("client"),
        }
    )


async def api_servers(request: Request) -> JSONResponse:
    base = _resolve_registry()
    token, _ = _admin_token(base, ADMIN_USER, ADMIN_PASS)
    status, payload = _registry_call("GET", base, "/registry/tools", token=token)
    if status != 200:
        return JSONResponse(
            {"error": payload.get("error") or "could not list servers"}, status_code=502
        )
    servers = []
    for t in payload.get("tools", []) or []:
        servers.append(
            {
                "listing_id": t.get("listing_id"),
                "tool_name": t.get("tool_name"),
                "display_name": t.get("display_name") or t.get("tool_name"),
                "description": t.get("description") or "",
                "hosting_mode": t.get("hosting_mode"),
                "status": t.get("status"),
                "proxy_url": f"{base}/runtime/proxy/{t.get('listing_id')}/mcp"
                if t.get("hosting_mode") == "proxy" and t.get("listing_id")
                else None,
            }
        )
    return JSONResponse(
        {
            "registry_url": base,
            "count": payload.get("count", len(servers)),
            "servers": servers,
        }
    )


async def _mcp_session(proxy_url: str, secret: str):
    """Context-managed fastmcp Client against the registry proxy."""
    from fastmcp import Client
    from fastmcp.client.auth import BearerAuth

    auth = BearerAuth(secret) if secret else None
    return Client(proxy_url, auth=auth)


def _tool_to_dict(tool: Any) -> dict:
    return {
        "name": getattr(tool, "name", None),
        "description": getattr(tool, "description", "") or "",
        "input_schema": getattr(tool, "inputSchema", None)
        or getattr(tool, "input_schema", None)
        or {},
    }


def _result_to_text(result: Any) -> dict:
    """Best-effort flatten of a CallToolResult across fastmcp versions."""
    # Structured data, if present.
    structured = getattr(result, "structured_content", None) or getattr(
        result, "data", None
    )
    text_parts: list[str] = []
    content = getattr(result, "content", None)
    if content is None and isinstance(result, list):
        content = result
    for block in content or []:
        t = getattr(block, "text", None)
        if t is not None:
            text_parts.append(t)
        elif isinstance(block, dict) and "text" in block:
            text_parts.append(block["text"])
    out: dict[str, Any] = {}
    if text_parts:
        out["text"] = "\n".join(text_parts)
    if structured is not None:
        try:
            json.dumps(structured)
            out["structured"] = structured
        except (TypeError, ValueError):
            out["structured"] = str(structured)
    if not out:
        out["text"] = str(result)
    return out


async def api_connect(request: Request) -> JSONResponse:
    body = await request.json()
    proxy_url = body.get("proxy_url")
    secret = body.get("token", "")
    if not proxy_url:
        return JSONResponse({"error": "proxy_url required"}, status_code=400)
    try:
        client = await _mcp_session(proxy_url, secret)
        async with client:
            tools = await client.list_tools()
        return JSONResponse({"tools": [_tool_to_dict(t) for t in tools]})
    except Exception as exc:  # noqa: BLE001 — surface any transport/auth error to the UI
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=502)


async def api_call(request: Request) -> JSONResponse:
    body = await request.json()
    proxy_url = body.get("proxy_url")
    secret = body.get("token", "")
    tool = body.get("tool")
    arguments = body.get("arguments") or {}
    if not proxy_url or not tool:
        return JSONResponse({"error": "proxy_url and tool required"}, status_code=400)
    if not isinstance(arguments, dict):
        return JSONResponse(
            {"error": "arguments must be a JSON object"}, status_code=400
        )
    try:
        client = await _mcp_session(proxy_url, secret)
        async with client:
            result = await client.call_tool(tool, arguments)
        return JSONResponse(
            {"ok": True, "tool": tool, "result": _result_to_text(result)}
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=502
        )


async def api_governance(request: Request) -> JSONResponse:
    slug = request.query_params.get("slug")
    if not slug:
        return JSONResponse({"error": "slug required"}, status_code=400)
    base = _resolve_registry()
    token, _ = _admin_token(base, ADMIN_USER, ADMIN_PASS)
    status, payload = _registry_call(
        "GET", base, f"/registry/clients/{slug}/governance", token=token
    )
    if status != 200:
        return JSONResponse(
            {"error": "governance unavailable", "status": status}, status_code=200
        )
    gov = payload or {}
    ledger = (gov.get("ledger") or {}).get("ledger") or {}
    policy = (gov.get("policy") or {}).get("registry_policy") or {}
    return JSONResponse(
        {
            "ledger_records": ledger.get("record_count"),
            "policy_evaluations": policy.get("evaluation_count"),
            "policy_denies": policy.get("deny_count"),
            "provenance_url": f"{base.replace(':8000', ':3000').replace(':8001', ':3000')}/registry/provenance",
        }
    )


async def index(request: Request) -> FileResponse:
    return FileResponse(HERE / "index.html")


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/state", api_state),
        Route("/api/register", api_register, methods=["POST"]),
        Route("/api/servers", api_servers),
        Route("/api/connect", api_connect, methods=["POST"]),
        Route("/api/call", api_call, methods=["POST"]),
        Route("/api/governance", api_governance),
    ]
)


if __name__ == "__main__":
    print(f"PureCipher Agent Client → http://localhost:{UI_PORT}")
    print(f"Registry (auto-detected at startup): {_resolve_registry()}")
    uvicorn.run(app, host="127.0.0.1", port=UI_PORT, log_level="info")
