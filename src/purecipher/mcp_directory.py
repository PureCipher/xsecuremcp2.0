"""Public upstream directory, independent of certified marketplace listings.

Run ``python -m purecipher.mcp_directory sync`` to atomically refresh metadata.
Importing never executes a package, signs an attestation, or changes owned listings.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

SOURCE = "https://registry.modelcontextprotocol.io/v0.1/servers"


def now():
    return datetime.now(timezone.utc).isoformat()


def snapshot_path():
    return Path(os.environ.get("PURECIPHER_DIRECTORY_FILE", ".data/mcp-directory.json"))


def read_snapshot(path=None):
    target = Path(path) if path else snapshot_path()
    if not target.exists():
        return {"servers": [], "synced_at": None, "source": SOURCE}
    stat = target.stat()
    return _read_cached(str(target.resolve()), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=2)
def _read_cached(path, modified, size):
    return json.loads(Path(path).read_text())


def save_snapshot(data, path=None):
    target = Path(path) if path else snapshot_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def plain_https(value):
    try:
        p = urlsplit(value)
        if p.hostname in {"localhost", "metadata.google.internal"} or (
            p.hostname or ""
        ).endswith(".local"):
            return False
        try:
            if not ipaddress.ip_address(p.hostname).is_global:
                return False
        except ValueError:
            pass
        return (
            p.scheme == "https"
            and bool(p.hostname)
            and not (p.username or p.password or p.query or p.fragment or "{" in value)
        )
    except (ValueError, TypeError):
        return False


def normalize(row):
    server = row["server"]
    name = server["name"]
    if not isinstance(name, str) or not name or not server.get("version"):
        raise ValueError("Registry record lacks a name or version")
    official = row.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
    options = []
    for remote in server.get("remotes", []):
        endpoint = remote.get("url", "")
        supported = remote.get("type") in {"streamable-http", "sse"} and plain_https(
            endpoint
        )
        options.append(
            {
                "kind": "remote",
                "transport": remote.get("type"),
                "reference": endpoint,
                "onboard_reference": endpoint if supported else None,
                "configuration": remote.get("headers", []),
                "needs_configuration": any(
                    h.get("isRequired") for h in remote.get("headers", [])
                )
                or not supported,
            }
        )
    for package in server.get("packages", []):
        channel = {"npm": "npm", "pypi": "pypi", "oci": "docker"}.get(
            package.get("registryType")
        )
        identifier, version = package.get("identifier", ""), package.get("version", "")
        # Custom registries must not silently resolve against a different source.
        base = str(package.get("registryBaseUrl") or "").rstrip("/")
        default_registry = (
            not base
            or (channel == "npm" and base == "https://registry.npmjs.org")
            or (
                channel == "pypi"
                and base in {"https://pypi.org", "https://pypi.org/simple"}
            )
        )
        if channel == "docker" and base:
            registry_host = urlsplit(base).hostname or base
            default_registry = identifier.startswith(
                registry_host + "/"
            ) or registry_host in {
                "docker.io",
                "registry.hub.docker.com",
                "registry-1.docker.io",
            }
        expected_hint = {"npm": "npx", "pypi": "uvx", "docker": "docker"}.get(channel)
        # Preserve every option, but don't silently discard launch arguments.
        simple = (
            default_registry
            and package.get("runtimeHint") in {None, expected_hint}
            and bool(channel and identifier)
            and not any(
                package.get(k)
                for k in (
                    "runtimeArguments",
                    "packageArguments",
                    "fileSha256",
                )
            )
            and package.get("transport", {}).get("type") == "stdio"
        )
        reference = None
        if simple:
            reference = f"{channel}:{identifier}"
            if channel != "docker" and version:
                reference += "@" + version
            elif (
                channel == "docker"
                and version
                and "@" not in identifier
                and ":" not in identifier.rsplit("/", 1)[-1]
            ):
                reference += ":" + version
        options.append(
            {
                "kind": "package",
                "transport": package.get("registryType"),
                "reference": identifier,
                "version": version,
                "onboard_reference": reference,
                "configuration": package.get("environmentVariables", []),
                "needs_configuration": any(
                    e.get("isRequired") for e in package.get("environmentVariables", [])
                )
                or not simple,
            }
        )
    return {
        "id": hashlib.sha256(name.encode()).hexdigest()[:24],
        "name": name,
        "title": server.get("title") or name,
        "description": server.get("description", ""),
        "version": server["version"],
        "upstream_status": official.get("status", "active"),
        "repository": server.get("repository", {}).get("url"),
        "website": server.get("websiteUrl"),
        "options": options,
        "published_at": official.get("publishedAt"),
        "updated_at": official.get("updatedAt"),
        "readiness": "not_tested",
        "raw": row,
    }


async def fetch_all(client, cache_dir=None):
    cursor, seen, records = None, set(), {}
    for page in range(10000):
        payload: dict[str, Any] = {}
        params = {"limit": 100, "version": "latest"}
        if cursor:
            params["cursor"] = cursor
        cache = None
        if cache_dir:
            cache = Path(cache_dir) / (
                hashlib.sha256(str(cursor).encode()).hexdigest() + ".json"
            )
        if cache and cache.exists():
            payload = json.loads(cache.read_text())
        else:
            for attempt in range(6):
                try:
                    response = await client.get(SOURCE, params=params)
                    if (
                        response.status_code in {429, 500, 502, 503, 504}
                        and attempt < 5
                    ):
                        await asyncio.sleep(min(2**attempt, 20))
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    break
                except (httpx.TransportError, json.JSONDecodeError):
                    if attempt == 5:
                        raise
                    await asyncio.sleep(min(2**attempt, 20))
            if cache and isinstance(payload.get("servers"), list):
                save_snapshot(payload, cache)
        if not isinstance(payload.get("servers"), list):
            raise ValueError("Registry response does not contain servers")
        for row in payload["servers"]:
            item = normalize(row)
            if (
                item["name"] in records
                and records[item["name"]]["version"] != item["version"]
            ):
                raise ValueError("Registry returned conflicting latest versions")
            records[item["name"]] = item
        cursor = payload.get("metadata", {}).get("nextCursor")
        if page % 10 == 0:
            print(f"Fetched {len(records)} servers", flush=True)
        if not cursor:
            return list(records.values())
        if not isinstance(cursor, str) or cursor in seen:
            raise ValueError("Registry repeated an invalid pagination cursor")
        seen.add(cursor)
    raise ValueError("Pagination safety limit reached; previous snapshot retained")


def compare(servers, baseline, *, baseline_kind):
    """Repository overlap is a candidate, never proof of tool equivalence."""
    names = {s.get("upstream_name") for s in baseline if s.get("upstream_name")}
    refs = {}
    for existing in baseline:
        ref = existing.get("upstream_ref") or {}
        channel, identifier = str(ref.get("channel", "")).lower(), ref.get("identifier")
        if channel and identifier:
            refs.setdefault((channel, identifier), []).append(existing["id"])
    identity_matches = []
    for server in servers:
        matches = set()
        for option in server["options"]:
            channel = (
                "http"
                if option["kind"] == "remote"
                else {"oci": "docker"}.get(option["transport"], option["transport"])
            )
            matches.update(refs.get((channel, option["reference"]), []))
        if matches:
            names.add(server["name"])
            identity_matches.append(
                {"upstream": server["name"], "existing": sorted(matches)}
            )
    candidates = []
    for existing in baseline:
        source = (
            str(existing.get("source") or "").rstrip("/").removesuffix(".git").lower()
        )
        hits = [
            s["name"]
            for s in servers
            if source.startswith("https://github.com/")
            and str(s.get("repository") or "").rstrip("/").removesuffix(".git").lower()
            == source
        ]
        candidates.append({"existing": existing["id"], "repository_candidates": hits})
    return {
        "baseline_kind": baseline_kind,
        "existing_count": len(baseline),
        "upstream_count": len(servers),
        "identity_matches": identity_matches,
        "exact_matches": sorted(s["name"] for s in servers if s["name"] in names),
        "not_matched_by_identity": sorted(
            s["name"] for s in servers if s["name"] not in names
        ),
        "repository_overlap_candidates": candidates,
        "note": "Repository matches do not establish equivalent tools, credentials, or behavior.",
    }


async def probe(
    item: dict[str, Any],
    timeout: float = 12,
    *,
    limiter: asyncio.Semaphore | None = None,
    hosts: dict[str, asyncio.Semaphore] | None = None,
) -> dict[str, Any]:
    """Only protocol discovery. No tool calls, package execution, or credentials."""
    from anyio import fail_after

    from fastmcp import Client
    from fastmcp.client.transports import SSETransport, StreamableHttpTransport
    from purecipher.curation.http_transport import client_factory

    result = {"checked_at": now(), "scope": "initialize_and_tools_list", "attempts": []}
    if item["upstream_status"] != "active":
        return {**result, "status": "upstream_inactive"}
    options = [
        o
        for o in item["options"]
        if o["kind"] == "remote"
        and o["onboard_reference"]
        and not o["needs_configuration"]
    ]
    if not options:
        return {**result, "status": "setup_required"}

    async def discover(option):
        endpoint = option["reference"]
        with fail_after(timeout):
            factory = await asyncio.to_thread(client_factory, endpoint)
            transport = (
                SSETransport
                if option["transport"] == "sse"
                else StreamableHttpTransport
            )
            async with Client(
                transport(endpoint, httpx_client_factory=factory)
            ) as client:
                tools = await client.list_tools()
            return [t.model_dump(mode="json", by_alias=True) for t in tools]

    authorization = False
    host_limits = hosts if hosts is not None else {}
    for option in options:
        try:
            if limiter is not None:
                host = urlsplit(option["reference"]).hostname or ""
                host_limit = host_limits.setdefault(host, asyncio.Semaphore(2))
                async with host_limit:
                    async with limiter:
                        observed = await discover(option)
            else:
                observed = await discover(option)
            return {
                **result,
                "status": "discovery_passed",
                "endpoint": option["reference"],
                "tools": observed,
                "tool_count": len(observed),
            }
        except Exception as exc:
            pending, visited, codes = [exc], set(), set()
            while pending:
                error = pending.pop()
                if id(error) in visited:
                    continue
                visited.add(id(error))
                response = getattr(error, "response", None)
                if response is not None and isinstance(
                    getattr(response, "status_code", None), int
                ):
                    codes.add(response.status_code)
                pending.extend(
                    e
                    for e in (
                        getattr(error, "__cause__", None),
                        getattr(error, "__context__", None),
                    )
                    if e
                )
                pending.extend(getattr(error, "exceptions", ()))
            authorization = authorization or bool(codes & {401, 403})
            result["attempts"].append(
                {
                    "endpoint": option["reference"],
                    "error_type": type(exc).__name__,
                    "http_statuses": sorted(codes),
                }
            )
    return {
        **result,
        "status": "authorization_required" if authorization else "connection_failed",
    }


async def probe_all(snapshot, *, concurrency=8, timeout=12, path=None):
    semaphore = asyncio.Semaphore(concurrency)
    hosts, shared_checks = {}, {}
    completed = 0
    last_save = time.monotonic()

    async def one(item):
        nonlocal completed, last_save
        if item.get("probe"):
            completed += 1
            return
        eligible = [
            o
            for o in item["options"]
            if o["kind"] == "remote"
            and o["onboard_reference"]
            and not o["needs_configuration"]
        ]
        key = json.dumps([item["upstream_status"], eligible], sort_keys=True)
        if key not in shared_checks:
            shared_checks[key] = asyncio.create_task(
                probe(item, timeout, limiter=semaphore, hosts=hosts)
            )
        item["probe"] = await shared_checks[key]
        item["readiness"] = item["probe"]["status"]
        completed += 1
        if completed % 100 == 0:
            print(f"Checked {completed}/{len(snapshot['servers'])}", flush=True)
        if time.monotonic() - last_save > 60:
            save_snapshot(snapshot, path)
            last_save = time.monotonic()

    try:
        await asyncio.gather(*(one(item) for item in snapshot["servers"]))
    finally:
        save_snapshot(snapshot, path)
    snapshot["probe_summary"] = dict(
        Counter(i["readiness"] for i in snapshot["servers"])
    )
    save_snapshot(snapshot, path)
    return snapshot["probe_summary"]


def mount_directory(registry, prefix):
    from starlette.responses import JSONResponse

    @registry.custom_route(f"{prefix}/directory", methods=["GET"])
    async def directory(request):
        try:
            data = await asyncio.to_thread(read_snapshot)
            q = request.query_params.get("q", "").casefold().strip()
            state = request.query_params.get("readiness", "")
            limit = int(request.query_params.get("limit", "24"))
            offset = int(request.query_params.get("offset", "0"))
            if not 1 <= limit <= 200 or not 0 <= offset <= 1000000 or len(q) > 300:
                raise ValueError("Invalid query or pagination")
            rows = [s for s in data["servers"] if s["upstream_status"] != "deleted"]
            total_all = len(rows)
            rows = [
                s
                for s in rows
                if (not state or s["readiness"] == state)
                and all(
                    term
                    in (
                        s["name"] + " " + s["title"] + " " + s["description"]
                    ).casefold()
                    for term in q.split()
                )
            ]
            rows.sort(key=lambda s: s["title"].casefold())
            return JSONResponse(
                {
                    "servers": [
                        {k: v for k, v in s.items() if k not in {"raw", "probe"}}
                        for s in rows[offset : offset + limit]
                    ],
                    "total": len(rows),
                    "unfiltered_count": total_all,
                    "offset": offset,
                    "limit": limit,
                    "synced_at": data.get("synced_at"),
                    "source": SOURCE,
                }
            )
        except (OSError, json.JSONDecodeError):
            return JSONResponse(
                {"error": "Directory snapshot unavailable"}, status_code=503
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @registry.custom_route(f"{prefix}/directory/{{server_id}}", methods=["GET"])
    async def detail(request):
        try:
            data = await asyncio.to_thread(read_snapshot)
        except (OSError, json.JSONDecodeError):
            return JSONResponse(
                {"error": "Directory snapshot unavailable"}, status_code=503
            )
        item = next(
            (
                s
                for s in data["servers"]
                if s["id"] == request.path_params["server_id"]
                and s["upstream_status"] != "deleted"
            ),
            None,
        )
        if item:
            smoke = await asyncio.to_thread(
                read_snapshot, snapshot_path().with_name("mcp-gateway-smoke.json")
            )
            item = {
                **item,
                "runtime_checks": [
                    c
                    for c in smoke.get("checks", [])
                    if c.get("server") == item["name"]
                ],
            }
        return JSONResponse(
            item or {"error": "Server not found"}, status_code=200 if item else 404
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sync", "probe"])
    parser.add_argument("--file", type=Path, default=snapshot_path())
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Recheck failed connections and authorization requirements",
    )
    parser.add_argument(
        "--refresh-probes", action="store_true", help="Recheck every server"
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=12)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 64 or not 1 <= args.timeout <= 60:
        parser.error("Concurrency must be 1–64; timeout must be 1–60 seconds")
    if args.command == "probe":
        data = read_snapshot(args.file)
        for item in data["servers"]:
            if args.refresh_probes or (
                args.retry_failed
                and item.get("readiness")
                in {"connection_failed", "authorization_required"}
            ):
                item.pop("probe", None)
                item["readiness"] = "not_tested"
        print(
            await probe_all(
                data, concurrency=args.concurrency, timeout=args.timeout, path=args.file
            )
        )
        return
    async with httpx.AsyncClient(
        timeout=45, follow_redirects=False, trust_env=False
    ) as client:
        servers = await fetch_all(client, args.file.with_suffix(".pages"))
    old = {i["name"]: i for i in read_snapshot(args.file)["servers"]}
    for item in servers:
        previous = old.get(item["name"])
        if previous and previous["raw"] == item["raw"] and previous.get("probe"):
            item["probe"], item["readiness"] = previous["probe"], previous["readiness"]
    if args.baseline:
        baseline = json.loads(args.baseline.read_text())
        kind = "provided_catalog_export"
    else:
        from purecipher.product_schemas import PRODUCT_SCHEMAS

        baseline = [
            {"id": k, "source": v.get("source")} for k, v in PRODUCT_SCHEMAS.items()
        ]
        kind = "checkout_product_definitions_not_live_catalog"
    data = {
        "source": SOURCE,
        "metadata_license": "CC0-1.0",
        "synced_at": now(),
        "servers": servers,
        "delta": compare(servers, baseline, baseline_kind=kind),
    }
    save_snapshot(data, args.file)
    cache_dir = args.file.with_suffix(".pages")
    for cached in cache_dir.glob("*.json"):
        cached.unlink()
    report = args.file.with_name("mcp-directory-delta.json")
    save_snapshot(data["delta"], report)
    print(
        json.dumps(
            {
                "imported": len(servers),
                "baseline_count": len(baseline),
                "file": str(args.file),
                "delta": str(report),
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
