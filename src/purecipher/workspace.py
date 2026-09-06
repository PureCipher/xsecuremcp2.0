"""Private end-user profiles and client bindings, persisted in PostgreSQL."""

from __future__ import annotations

import copy
import json
import re
import time
import uuid

from starlette.responses import JSONResponse

from purecipher.auth import RegistryRole
from purecipher.pgdb import connection, is_postgres_dsn
from purecipher.publishers import publisher_id_from_author


class WorkspaceStore:
    def __init__(self, dsn=None):
        self.dsn = dsn
        self.memory = {}

    def get(self, key):
        if not is_postgres_dsn(self.dsn):
            return copy.deepcopy(self.memory.get(key))
        with connection(self.dsn) as conn:
            row = conn.execute(
                "SELECT payload FROM purecipher_workspace WHERE id=%s", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, owner, kind="profile"):
        if not is_postgres_dsn(self.dsn):
            return [
                copy.deepcopy(v)
                for v in self.memory.values()
                if v["owner"] == owner and v["kind"] == kind
            ]
        with connection(self.dsn) as conn:
            rows = conn.execute(
                "SELECT payload FROM purecipher_workspace WHERE owner=%s AND kind=%s ORDER BY id",
                (owner, kind),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, item, expected=None):
        item = copy.deepcopy(item)
        item["revision"] = (expected or 0) + 1
        if not is_postgres_dsn(self.dsn):
            old = self.memory.get(item["id"])
            if (old is None) != (expected is None) or (
                old and old["revision"] != expected
            ):
                raise ValueError("Profile changed; reload before saving")
            self.memory[item["id"]] = item
            return item
        with connection(self.dsn) as conn:
            if expected is None:
                conn.execute(
                    "INSERT INTO purecipher_workspace (id,owner,kind,revision,payload) VALUES (%s,%s,%s,%s,%s)",
                    (
                        item["id"],
                        item["owner"],
                        item["kind"],
                        item["revision"],
                        json.dumps(item),
                    ),
                )
            else:
                cur = conn.execute(
                    "UPDATE purecipher_workspace SET revision=%s,payload=%s WHERE id=%s AND owner=%s AND revision=%s",
                    (
                        item["revision"],
                        json.dumps(item),
                        item["id"],
                        item["owner"],
                        expected,
                    ),
                )
                if cur.rowcount != 1:
                    raise ValueError("Profile changed; reload before saving")
        return item

    def delete(self, item):
        if not is_postgres_dsn(self.dsn):
            self.memory.pop(item["id"], None)
        else:
            with connection(self.dsn) as conn:
                conn.execute(
                    "DELETE FROM purecipher_workspace WHERE id=%s AND owner=%s",
                    (item["id"], item["owner"]),
                )


def inspected_tools(listing):
    if listing is None:
        return set()
    introspection = (listing.metadata or {}).get("introspection")
    names = introspection.get("tool_names") if isinstance(introspection, dict) else None
    return (
        {name for name in names if isinstance(name, str) and name}
        if isinstance(names, list)
        else set()
    )


def profile_blockers(registry, profile):
    blockers = []
    if not profile["client_ids"]:
        blockers.append("Select at least one registered client")
    if not profile["servers"]:
        blockers.append("Select at least one server and tool")
    for client_id in profile["client_ids"]:
        client = registry._client_store.get_client(client_id)
        binding = registry._workspace.get(client_id)
        if (
            not client
            or client.status != "active"
            or not binding
            or binding["owner"] != profile["owner"]
        ):
            blockers.append(
                "A selected client is unavailable or belongs to another account"
            )
    for selected in profile["servers"]:
        from purecipher.product_connections import connection_blocker

        reason = connection_blocker(registry, profile["owner"], selected)
        if reason:
            blockers.append(reason)
        listing = registry._marketplace().get(selected["listing_id"])
        if not listing or registry._get_public_listing(listing.tool_name) is None:
            blockers.append("A selected server is not published and verified")
            continue
        metadata = listing.metadata or {}
        runtime_verified = False
        if selected.get("connection_id") and not reason:
            from purecipher.consumer_runtime import runtime_ready

            connected = registry._workspace.get(selected["connection_id"])
            runtime_verified = bool(connected and runtime_ready(registry, connected))
        if metadata.get("deployment_ready") is False or (
            metadata.get("live_tested") is False and not runtime_verified
        ):
            blockers.append(
                f"{listing.display_name}: deployment or live validation is pending"
            )
        observed = inspected_tools(listing)
        if not selected["tools"] or not set(selected["tools"]).issubset(observed):
            blockers.append(f"{listing.display_name}: select inspected tools")
    return list(dict.fromkeys(blockers))


def allowed_profile_tools(registry, profile_id, client):
    profile = registry._workspace.get(profile_id)
    binding = registry._workspace.get(client.client_id)
    if (
        not profile
        or profile.get("kind") != "profile"
        or not binding
        or profile["owner"] != binding["owner"]
        or client.client_id not in profile["client_ids"]
        or profile["status"] != "active"
        or client.status != "active"
    ):
        raise ValueError("Profile is inactive or this client is not assigned")
    account = registry._account_security._get_account(profile["owner"])
    if (
        not account
        or account.get("disabled_at") is not None
        or profile_blockers(registry, profile)
    ):
        raise ValueError("Profile is not ready or its owner is disabled")
    allowed = set()
    for selected in profile["servers"]:
        allowed.update(selected["tools"])
    # A name exposed by multiple listings cannot safely identify one permission.
    for name in allowed:
        owners = [
            item
            for item in registry._marketplace().search(limit=10000)
            if name in inspected_tools(item)
        ]
        if len(owners) != 1:
            raise ValueError("Ambiguous tool name; server tool names must be unique")
    return allowed


def mount_workspace(registry, prefix):
    def owned(request, key):
        session = registry._session_from_request(request)
        item = registry._workspace.get(key)
        if session is None or item is None or item["owner"] != session.username:
            return None
        return item

    @registry.custom_route(f"{prefix}/register", methods=["POST"])
    async def register(request):
        ip = request.client.host if request.client else "unknown"
        locked, _ = registry._login_lockout.is_locked("workspace-registration", ip)
        if locked:
            return JSONResponse(
                {"error": "Too many registration attempts; try later"}, status_code=429
            )
        registry._login_lockout.register_failure("workspace-registration", ip)
        try:
            body = await request.json()
            username, password = body.get("username", ""), body.get("password", "")
            if (
                not isinstance(username, str)
                or not re.fullmatch(r"[a-z][a-z0-9-]{2,39}", username)
                or not isinstance(password, str)
                or not 12 <= len(password) <= 256
            ):
                raise ValueError(
                    "Use a 3–40 character lowercase username and a password of 12–256 characters"
                )
            if not registry.auth_enabled:
                raise ValueError(
                    "Account registration requires authentication to be enabled"
                )
            if publisher_id_from_author(username) != username or any(
                publisher_id_from_author(account["username"]) == username
                for account in registry._account_security.list_accounts()
            ):
                raise ValueError("That username is unavailable")
            result = registry._account_security.create_account(
                username=username,
                password=password,
                role=RegistryRole.VIEWER,
                source="self-registration",
                display_name=str(body.get("display_name") or username)[:100],
            )
            if result is None:
                raise ValueError("That username is unavailable")
            registry._user_preferences.set(
                username, {"workspace": {"defaultLandingPage": "/registry/profiles"}}
            )
            return JSONResponse({"created": True}, status_code=201)
        except (ValueError, TypeError, AttributeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @registry.custom_route(f"{prefix}/workspace", methods=["GET"])
    async def workspace(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Sign in required"}, status_code=401)
        profiles = registry._workspace.list(session.username)
        for profile in profiles:
            profile["blockers"] = profile_blockers(registry, profile)
        clients = []
        for binding in registry._workspace.list(session.username, "client"):
            client = registry._client_store.get_client(binding["id"])
            if client:
                clients.append(client.to_dict())
        catalog = registry.list_verified_tools(limit=10000)["tools"]
        servers = [
            {
                "listing_id": x["listing_id"],
                "tool_name": x["tool_name"],
                "display_name": x.get("display_name"),
                "tools": sorted(
                    inspected_tools(registry._marketplace().get(x["listing_id"]))
                ),
            }
            for x in catalog
        ]
        return JSONResponse(
            {"profiles": profiles, "clients": clients, "servers": servers}
        )

    @registry.custom_route(f"{prefix}/workspace/clients", methods=["POST"])
    async def create_client(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Sign in required"}, status_code=401)
        try:
            body = await request.json()
            name = str(body.get("display_name") or "").strip()
            if not 1 <= len(name) <= 100:
                raise ValueError("Client name must be 1–100 characters")
            if len(registry._workspace.list(session.username, "client")) >= 100:
                raise ValueError("Client limit reached")
            # Reserve an immutable owner binding before creating the identity.
            client = registry._client_store.create_client(
                display_name=name,
                slug="client-" + uuid.uuid4().hex[:16],
                owner_publisher_id=publisher_id_from_author(session.username),
                metadata={"application": str(body.get("application") or "Other")[:80]},
            )
            registry._workspace.save(
                {"id": client.client_id, "owner": session.username, "kind": "client"}
            )
            token, secret = registry._client_store.issue_token(
                client_id=client.client_id,
                name="Initial token",
                created_by=session.username,
            )
            return JSONResponse(
                {"client": client.to_dict(), "token": secret}, status_code=201
            )
        except (ValueError, TypeError, AttributeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @registry.custom_route(f"{prefix}/workspace/profiles", methods=["POST"])
    @registry.custom_route(
        f"{prefix}/workspace/profiles/{{profile_id}}", methods=["PUT", "DELETE"]
    )
    async def save_profile(request):
        session = registry._session_from_request(request)
        if session is None:
            return JSONResponse({"error": "Sign in required"}, status_code=401)
        key = request.path_params.get("profile_id")
        previous = owned(request, key) if key else None
        if key and (not previous or previous["kind"] != "profile"):
            return JSONResponse({"error": "Profile not found"}, status_code=404)
        if request.method == "DELETE":
            registry._workspace.delete(previous)
            return JSONResponse({"deleted": True})
        try:
            body = await request.json()
            name = str(body.get("name") or "").strip()
            clients, servers = body.get("client_ids", []), body.get("servers", [])
            if (
                not name
                or len(name) > 100
                or not isinstance(clients, list)
                or not isinstance(servers, list)
                or len(clients) > 100
                or len(servers) > 100
            ):
                raise ValueError(
                    "Provide a name and valid selections (maximum 100 each)"
                )
            for client_id in clients:
                binding = owned(request, client_id)
                if not binding or binding["kind"] != "client":
                    raise ValueError("Select clients registered in your workspace")
            selected_servers = []
            for selected in servers:
                listing = registry._marketplace().get(selected.get("listing_id", ""))
                if (
                    not listing
                    or registry._get_public_listing(listing.tool_name) is None
                ):
                    raise ValueError("Select published, verified servers")
                tools = selected.get("tools", [])
                if (
                    not isinstance(tools, list)
                    or not all(isinstance(x, str) for x in tools)
                    or not set(tools).issubset(inspected_tools(listing))
                ):
                    raise ValueError("Select inspected tools from this server")
                entry = {"listing_id": listing.listing_id, "tools": sorted(set(tools))}
                connection_id = selected.get("connection_id")
                if connection_id:
                    connection = owned(request, connection_id)
                    if (
                        not connection
                        or connection.get("kind") != "product_connection"
                        or listing.author != "purecipher"
                        or listing.tool_name != "purecipher-" + connection["product"]
                    ):
                        raise ValueError("Select your own connection for this product")
                    entry["connection_id"] = connection_id
                selected_servers.append(entry)
            status = body.get("status", "inactive")
            if status not in {"active", "inactive"}:
                raise ValueError("Invalid profile status")
            if previous and body.get("revision") != previous["revision"]:
                raise ValueError("Profile changed; reload before saving")
            profile = {
                "id": key or str(uuid.uuid4()),
                "kind": "profile",
                "owner": session.username,
                "name": name,
                "status": status,
                "client_ids": sorted(set(clients)),
                "servers": selected_servers,
                "updated_at": time.time(),
            }
            if status == "active":
                blockers = profile_blockers(registry, profile)
                if blockers:
                    raise ValueError("; ".join(blockers))
            if not previous and len(registry._workspace.list(session.username)) >= 100:
                raise ValueError("Profile limit reached")
            return JSONResponse(
                registry._workspace.save(
                    profile, previous["revision"] if previous else None
                )
            )
        except (ValueError, TypeError, AttributeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
