"""Owner-scoped persistent utilities and public reference tools."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field


class MemoryRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=200)
    relation_type: str = Field(min_length=1, max_length=200)


PRODUCTS = {
    "time",
    "memory",
    "sequential-thinking",
    "wikipedia",
    "fetch",
    "aws-documentation",
    "arxiv",
}


def register(registry):
    from purecipher.consumer_runtime import _ACCESS, access, provider_get
    from purecipher.product_connections import cipher

    registry._consumer_products = registry._consumer_products | PRODUCTS

    def tool(product, *, read=True, destructive=False):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = product
            registry.tool(
                annotations={
                    "readOnlyHint": read,
                    "destructiveHint": destructive,
                    "idempotentHint": read,
                    "openWorldHint": product
                    not in {"memory", "time", "sequential-thinking"},
                },
                tags={"risk:low" if read else "risk:high", "resource:" + product},
            )(fn)
            return fn

        return decorate

    def record(product):
        access(product)
        context = _ACCESS.get()
        if not context:
            raise ValueError("An assigned profile is required")
        item = registry._workspace.get(context["connection_id"])
        if not item or item["owner"] != context["owner"]:
            raise ValueError("Connection is no longer available")
        return item

    def read_payload(item):
        if not item.get("utility_encrypted"):
            return {"entries": [], "relations": []}
        payload = json.loads(
            cipher(registry).decrypt(item["utility_encrypted"].encode())
        )
        if payload["owner"] != item["owner"] or payload["id"] != item["id"]:
            raise ValueError("Utility state identity mismatch")
        return payload

    def read_state(item):
        return read_payload(item)["entries"]

    def write_state(item, entries, relations=None):
        previous = read_payload(item)
        if relations is None:
            relations = previous.get("relations", [])
        payload = {
            "owner": item["owner"],
            "id": item["id"],
            "entries": entries,
            "relations": relations,
        }
        encoded = json.dumps(payload)
        if len(encoded.encode()) > 2 * 1024 * 1024:
            raise ValueError("Encrypted utility state exceeds 2 MiB")
        item["utility_encrypted"] = cipher(registry).encrypt(encoded.encode()).decode()
        registry._workspace.save(item, item["revision"])

    @tool("time")
    async def time_current(timezone: str = "UTC") -> dict:
        """Return the current time in an IANA timezone, for example Asia/Kolkata."""
        access("time")
        try:
            return {
                "timezone": timezone,
                "time": datetime.now(ZoneInfo(timezone)).isoformat(),
            }
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("Use a valid IANA timezone") from None

    @tool("time")
    async def time_convert(timestamp: str, timezone: str = "UTC") -> dict:
        """Convert an ISO timestamp containing its UTC offset into an IANA timezone."""
        access("time")
        try:
            value = datetime.fromisoformat(timestamp)
            if value.tzinfo is None:
                raise ValueError("Timestamp needs an offset")
            return {
                "time": value.astimezone(ZoneInfo(timezone)).isoformat(),
                "timezone": timezone,
            }
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError(
                "Provide an ISO timestamp with offset and valid IANA timezone"
            ) from None

    @tool("memory", read=False)
    async def memory_save_entity(name: str, observations: list[str]) -> dict:
        """Save or replace an entity in this connection's encrypted memory; shared only by its assigned profiles."""
        if (
            not name.strip()
            or len(name) > 200
            or len(observations) > 50
            or any(len(x) > 4000 for x in observations)
        ):
            raise ValueError(
                "Use a name up to 200 characters and at most 50 observations of 4000 characters"
            )
        item = record("memory")
        entries = [e for e in read_state(item) if e["name"] != name]
        if len(entries) >= 100:
            raise ValueError("This memory connection supports 100 entities")
        entries.append({"name": name, "observations": observations})
        write_state(item, entries)
        return {"saved": name}

    @tool("memory")
    async def memory_search(query: str = "") -> dict:
        """Search this connection's stored entities and observations."""
        return {
            "entities": [
                e
                for e in read_state(record("memory"))
                if query.casefold() in json.dumps(e).casefold()
            ]
        }

    def names_check(names):
        if not 1 <= len(names) <= 100 or any(
            not name.strip() or len(name) > 200 for name in names
        ):
            raise ValueError("Choose 1–100 entity names, each up to 200 characters")

    def observations_check(observations):
        if not 1 <= len(observations) <= 50 or any(
            not text.strip() or len(text) > 4000 for text in observations
        ):
            raise ValueError(
                "Provide 1–50 nonempty observations, each up to 4000 characters"
            )

    @tool("memory")
    async def memory_read_graph() -> dict:
        """Read all entities and relations in your connection's encrypted knowledge graph."""
        payload = read_payload(record("memory"))
        return {
            "entities": payload["entries"],
            "relations": payload.get("relations", []),
        }

    @tool("memory")
    async def memory_open_entities(names: list[str]) -> dict:
        """Read selected memory entities and relations between those entities."""
        names_check(names)
        payload = read_payload(record("memory"))
        chosen = set(names)
        return {
            "entities": [
                entry for entry in payload["entries"] if entry["name"] in chosen
            ],
            "relations": [
                relation
                for relation in payload.get("relations", [])
                if relation["source"] in chosen and relation["target"] in chosen
            ],
        }

    @tool("memory", read=False)
    async def memory_add_observations(name: str, observations: list[str]) -> dict:
        """Append unique observations to one existing entity in your encrypted memory."""
        names_check([name])
        observations_check(observations)
        item = record("memory")
        entries = read_state(item)
        entry = next((entry for entry in entries if entry["name"] == name), None)
        if entry is None:
            raise ValueError("Save this entity before adding observations")
        merged = list(dict.fromkeys([*entry["observations"], *observations]))
        if len(merged) > 50:
            raise ValueError("An entity supports at most 50 observations")
        entry["observations"] = merged
        write_state(item, entries)
        return {"entity": entry}

    @tool("memory", read=False, destructive=True)
    async def memory_delete_observations(name: str, observations: list[str]) -> dict:
        """Delete exact matching observations from one memory entity; retains the entity and relations."""
        names_check([name])
        observations_check(observations)
        item = record("memory")
        entries = read_state(item)
        entry = next((entry for entry in entries if entry["name"] == name), None)
        if entry is None:
            raise ValueError("Memory entity was not found")
        entry["observations"] = [
            text for text in entry["observations"] if text not in observations
        ]
        write_state(item, entries)
        return {"entity": entry}

    @tool("memory", read=False)
    async def memory_create_relations(relations: list[MemoryRelation]) -> dict:
        """Create directed relations between existing memory entities; duplicate relations are ignored."""
        if not 1 <= len(relations) <= 100:
            raise ValueError("Provide 1–100 relations")
        item = record("memory")
        payload = read_payload(item)
        names = {entry["name"] for entry in payload["entries"]}
        merged = payload.get("relations", [])
        for relation in relations:
            if (
                relation.source not in names
                or relation.target not in names
                or not relation.relation_type.strip()
            ):
                raise ValueError(
                    "Each relation must connect existing entities and have a nonempty type"
                )
            value = relation.model_dump()
            if value not in merged:
                merged.append(value)
        if len(merged) > 500:
            raise ValueError("This connection supports 500 memory relations")
        write_state(item, payload["entries"], merged)
        return {"relations": merged}

    @tool("memory", read=False, destructive=True)
    async def memory_delete_relations(relations: list[MemoryRelation]) -> dict:
        """Delete exact directed relations while retaining their memory entities."""
        if not 1 <= len(relations) <= 100:
            raise ValueError("Provide 1–100 relations")
        item = record("memory")
        payload = read_payload(item)
        removed = [relation.model_dump() for relation in relations]
        current = payload.get("relations", [])
        remaining = [relation for relation in current if relation not in removed]
        write_state(item, payload["entries"], remaining)
        return {"deleted": len(current) - len(remaining)}

    @tool("memory", read=False, destructive=True)
    async def memory_delete_entities(names: list[str]) -> dict:
        """Permanently delete selected memory entities and their incident relations from this connection."""
        names_check(names)
        item = record("memory")
        payload = read_payload(item)
        entries = [entry for entry in payload["entries"] if entry["name"] not in names]
        relations = [
            relation
            for relation in payload.get("relations", [])
            if relation["source"] not in names and relation["target"] not in names
        ]
        write_state(item, entries, relations)
        return {"deleted": len(payload["entries"]) - len(entries)}

    @tool("sequential-thinking", read=False)
    async def sequential_thinking(
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
    ) -> dict:
        """Record a numbered reasoning step. This stores caller-provided thoughts; it does not invoke another model."""
        if (
            not thought.strip()
            or len(thought) > 8000
            or not 1 <= thought_number <= total_thoughts <= 100
        ):
            raise ValueError(
                "Use thought numbers 1–100 and a thought up to 8000 characters"
            )
        item = record("sequential-thinking")
        entries = [] if thought_number == 1 else read_state(item)
        if thought_number != len(entries) + 1:
            raise ValueError("Continue with the next thought number or restart at one")
        entries.append({"thought": thought, "thought_number": thought_number})
        write_state(item, entries)
        return {
            "thought_number": thought_number,
            "total_thoughts": total_thoughts,
            "next_thought_needed": next_thought_needed,
        }

    @tool("wikipedia")
    async def wikipedia_search(query: str, limit: int = 5) -> dict:
        """Search English Wikipedia article summaries."""
        access("wikipedia")
        if not query.strip() or len(query) > 300 or not 1 <= limit <= 20:
            raise ValueError("Provide a query up to 300 characters and a limit of 1–20")
        return await provider_get(
            "https://en.wikipedia.org/w/api.php",
            {"User-Agent": "PureCipherRegistry/1.0 (https://purecipher.com)"},
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "format": "json",
            },
        )

    async def public_text(url):
        from fastmcp.server.security.outbound import async_secure_outbound_request

        result = await async_secure_outbound_request(
            url,
            method="GET",
            content=b"",
            headers={"User-Agent": "PureCipherRegistry/1.0 (https://purecipher.com)"},
            timeout=20,
            max_response_bytes=512 * 1024,
        )
        if result.status_code != 200:
            raise ValueError(
                "The public resource is unavailable; redirects are not followed"
            )
        return result.content.decode("utf-8", errors="replace")

    @tool("fetch")
    async def fetch_public_url(url: str) -> dict:
        """Fetch at most 512 KiB from a public HTTPS URL. Private networks and redirects are blocked."""
        access("fetch")
        return {"url": url, "content": await public_text(url)}

    @tool("aws-documentation")
    async def aws_read_documentation(url: str) -> dict:
        """Read a page from the official AWS documentation site."""
        from urllib.parse import urlsplit

        access("aws-documentation")
        if urlsplit(url).hostname not in {"docs.aws.amazon.com", "docs.amazonaws.com"}:
            raise ValueError("Use an official AWS documentation URL")
        return {"url": url, "content": await public_text(url)}

    @tool("arxiv")
    async def arxiv_search(query: str, limit: int = 5) -> dict:
        """Search arXiv paper titles, authors and abstracts."""
        import xml.etree.ElementTree as ET
        from urllib.parse import urlencode

        access("arxiv")
        if not query.strip() or len(query) > 400 or not 1 <= limit <= 20:
            raise ValueError("Provide a query up to 400 characters and limit 1–20")
        body = await public_text(
            "https://export.arxiv.org/api/query?"
            + urlencode({"search_query": query, "max_results": limit})
        )
        if "<!DOCTYPE" in body or "<!ENTITY" in body:
            raise ValueError("Unexpected XML response")
        document = ET.fromstring(body)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        return {
            "papers": [
                {
                    "id": e.findtext("a:id", namespaces=ns),
                    "title": e.findtext("a:title", namespaces=ns),
                    "summary": e.findtext("a:summary", namespaces=ns),
                    "authors": [
                        a.findtext("a:name", namespaces=ns)
                        for a in e.findall("a:author", ns)
                    ],
                }
                for e in document.findall("a:entry", ns)
            ]
        }
