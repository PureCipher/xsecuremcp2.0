"""Owner-authenticated upstream MCP connections with explicit tool approval."""

import json
import re
import uuid
from urllib.parse import urlsplit

import httpx2
from jsonschema import validators
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry

from fastmcp.server.security.outbound import (
    OutboundRequestError,
    async_secure_outbound_request,
)

PRODUCTS = {
    "ast-grep",
    "clickhouse",
    "desktop-commander",
    "docker-hub",
    "duckduckgo",
    "filesystem",
    "git",
    "kubernetes",
    "markitdown",
    "mongodb",
    "nodejs-sandbox",
    "obsidian",
    "playwright",
    "puppeteer",
    "redis",
    "youtube-transcripts",
}


def settings(values):
    endpoint = values.get("MCP_ENDPOINT", "")
    parsed = urlsplit(endpoint)
    token = values.get("MCP_ACCESS_TOKEN", "")
    allowed = {
        x.strip() for x in values.get("MCP_ALLOWED_TOOLS", "").splitlines() if x.strip()
    }
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Use a public HTTPS MCP endpoint without credentials or query parameters"
        )
    if not token or any(c in token for c in "\r\n"):
        raise ValueError("Enter the access token for your MCP endpoint")
    if (
        not allowed
        or len(allowed) > 100
        or any(not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", x) for x in allowed)
    ):
        raise ValueError("Approve 1–100 upstream tool names, one per line")
    return (
        endpoint,
        {
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        allowed,
    )


def decode(response, request_id):
    if response.status_code != 200:
        raise ValueError(
            "Upstream MCP request failed; check endpoint, token and permissions"
        )
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        messages = []
        for event in response.content.decode().replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(
                line[5:].lstrip()
                for line in event.splitlines()
                if line.startswith("data:")
            )
            if data:
                messages.append(json.loads(data))
    else:
        messages = [json.loads(response.content)]
    result = next(
        (m for m in messages if isinstance(m, dict) and m.get("id") == request_id), None
    )
    if (
        not result
        or result.get("jsonrpc") != "2.0"
        or "error" in result
        or not isinstance(result.get("result"), dict)
    ):
        raise ValueError("Upstream did not return a valid MCP result")
    return result["result"]


class Session:
    def __init__(self, values):
        self.endpoint, self.headers, self.allowed = settings(values)

    async def rpc(self, method, params=None):
        request_id = uuid.uuid4().hex
        response = await async_secure_outbound_request(
            self.endpoint,
            method="POST",
            content=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
            ).encode(),
            headers=self.headers,
            timeout=20,
            max_response_bytes=2 * 1024 * 1024,
        )
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            if len(session_id) > 512 or any(
                ord(c) < 33 or ord(c) > 126 for c in session_id
            ):
                raise ValueError("Invalid upstream session identifier")
            self.headers["Mcp-Session-Id"] = session_id
        result = decode(response, request_id)
        if method == "tools/call" and result.get("isError"):
            raise ValueError(
                "Upstream tool reported an error; check its inputs and permissions"
            )
        return result

    async def __aenter__(self):
        result = await self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "PureCipherConsumerConnector", "version": "1.0"},
            },
        )
        version = result.get("protocolVersion", "")
        if not isinstance(version, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", version
        ):
            raise ValueError("Invalid upstream protocol version")
        self.headers["MCP-Protocol-Version"] = version
        response = await async_secure_outbound_request(
            self.endpoint,
            method="POST",
            content=b'{"jsonrpc":"2.0","method":"notifications/initialized"}',
            headers=self.headers,
            timeout=20,
        )
        if response.status_code not in {200, 202, 204}:
            raise ValueError("Upstream initialization failed")
        return self

    async def __aexit__(self, *args):
        if "Mcp-Session-Id" in self.headers:
            try:
                await async_secure_outbound_request(
                    self.endpoint,
                    method="DELETE",
                    content=b"",
                    headers=self.headers,
                    timeout=5,
                )
            except (ValueError, TimeoutError, OutboundRequestError, httpx2.HTTPError):
                pass  # Session cleanup must not hide the operation's result.

    async def tools(self):
        tools, cursor = {}, None
        for _ in range(20):
            response = await self.rpc(
                "tools/list", {"cursor": cursor} if cursor else {}
            )
            entries = response.get("tools", [])
            if not isinstance(entries, list) or len(entries) > 500:
                raise ValueError("Upstream tool catalog is too large")
            for item in entries:
                if not isinstance(item, dict):
                    raise ValueError("Invalid upstream tool descriptor")
                if item.get("name") in self.allowed:
                    schema = item.get("inputSchema")
                    if not isinstance(schema, dict) or len(json.dumps(schema)) > 32000:
                        raise ValueError("Invalid or oversized upstream schema")

                    def check(value, depth=0):
                        if depth > 30:
                            raise ValueError("Upstream schema is too deeply nested")
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if k in {"$ref", "$dynamicRef"} and (
                                    not isinstance(v, str) or not v.startswith("#")
                                ):
                                    raise ValueError(
                                        "External schema references are not allowed"
                                    )
                                check(v, depth + 1)
                        elif isinstance(value, list):
                            for v in value:
                                check(v, depth + 1)

                    check(schema)
                    try:
                        validators.validator_for(schema).check_schema(schema)
                    except SchemaError:
                        raise ValueError(
                            "Upstream returned an invalid input schema"
                        ) from None
                    tools[item["name"]] = {
                        "name": item["name"],
                        "description": str(item.get("description", ""))[:4000],
                        "inputSchema": schema,
                    }
            if len(json.dumps(tools)) > 256000:
                raise ValueError(
                    "Approved tool definitions exceed the connection limit"
                )
            cursor = response.get("nextCursor")
            if not cursor:
                break
            if not isinstance(cursor, str) or len(cursor) > 4000:
                raise ValueError("Invalid upstream cursor")
        else:
            raise ValueError("Upstream catalog pagination exceeded its limit")
        if set(tools) != self.allowed:
            raise ValueError(
                "One or more approved tool names are absent from the upstream"
            )
        return tools


def seal(registry, item, tools):
    from purecipher.product_connections import cipher

    return (
        cipher(registry)
        .encrypt(
            json.dumps(
                {
                    "owner": item["owner"],
                    "id": item["id"],
                    "product": item["product"],
                    "tools": tools,
                }
            ).encode()
        )
        .decode()
    )


def approved_tools(registry, item):
    from purecipher.product_connections import cipher

    if not item.get("bridge_encrypted"):
        return {}
    payload = json.loads(cipher(registry).decrypt(item["bridge_encrypted"].encode()))
    if (payload["owner"], payload["id"], payload["product"]) != (
        item["owner"],
        item["id"],
        item["product"],
    ):
        raise ValueError("Upstream catalog identity mismatch")
    return payload["tools"]


async def verify(values):
    try:
        async with Session(values) as session:
            return await session.tools()
    except (OutboundRequestError, httpx2.HTTPError):
        raise ValueError("Could not connect to the upstream MCP service") from None


def register(registry):
    from purecipher.consumer_runtime import _ACCESS, access

    registry._consumer_products = registry._consumer_products | PRODUCTS

    def one(product):
        prefix = product.replace("-", "_")

        def context():
            access(product)
            ctx = _ACCESS.get()
            if ctx is None:
                raise ValueError("An assigned profile is required")
            return ctx

        async def list_approved_tools() -> dict:
            """List tool names and input schemas explicitly approved for your upstream connection."""
            ctx = context()
            return {
                "tools": list(
                    approved_tools(
                        registry, registry._workspace.get(ctx["connection_id"])
                    ).values()
                )
            }

        async def call_approved_tool(tool_name: str, arguments: dict) -> dict:
            """Call one approved tool on your own upstream MCP service. Effects depend on that tool and may include writes or execution."""
            ctx = context()
            known = approved_tools(
                registry, registry._workspace.get(ctx["connection_id"])
            )
            if tool_name not in known:
                raise ValueError("This upstream tool is not approved")
            schema = known[tool_name]["inputSchema"]
            try:
                validators.validator_for(schema)(schema, registry=Registry()).validate(
                    arguments
                )
            except (ValidationError, RecursionError):
                raise ValueError(
                    "Arguments do not match the approved upstream schema"
                ) from None
            async with Session(ctx["values"]) as session:
                actual = await session.tools()
                if actual != known:
                    raise ValueError(
                        "Upstream tool definitions changed; verify the connection again"
                    )
                from purecipher.consumer_runtime import digest, runtime_ready
                from purecipher.workspace import allowed_profile_tools

                current = registry._workspace.get(ctx["connection_id"])
                if (
                    not current
                    or not runtime_ready(registry, current)
                    or current.get("verified_values") != digest(registry, ctx["values"])
                ):
                    raise ValueError("Connection changed or was disconnected")
                allowed_profile_tools(registry, ctx["profile_id"], ctx["client"])
                return await session.rpc(
                    "tools/call", {"name": tool_name, "arguments": arguments}
                )

        for suffix, fn, read in [
            ("list_approved_tools", list_approved_tools, True),
            ("call_approved_tool", call_approved_tool, False),
        ]:
            name = prefix + "_" + suffix
            registry._consumer_tool_products[name] = product
            registry.tool(
                name=name,
                annotations={
                    "readOnlyHint": read,
                    "destructiveHint": not read,
                    "openWorldHint": True,
                },
            )(fn)

    for product in sorted(PRODUCTS):
        one(product)
