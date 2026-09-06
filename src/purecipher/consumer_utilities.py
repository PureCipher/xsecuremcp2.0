"""Owner-scoped persistent utilities and public reference tools."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

    def tool(product, *, read=True):
        def decorate(fn):
            registry._consumer_tool_products[fn.__name__] = product
            registry.tool(
                annotations={
                    "readOnlyHint": read,
                    "destructiveHint": False,
                    "openWorldHint": product == "wikipedia",
                }
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

    def read_state(item):
        if not item.get("utility_encrypted"):
            return []
        payload = json.loads(
            cipher(registry).decrypt(item["utility_encrypted"].encode())
        )
        if payload["owner"] != item["owner"] or payload["id"] != item["id"]:
            raise ValueError("Utility state identity mismatch")
        return payload["entries"]

    def write_state(item, entries):
        item["utility_encrypted"] = (
            cipher(registry)
            .encrypt(
                json.dumps(
                    {"owner": item["owner"], "id": item["id"], "entries": entries}
                ).encode()
            )
            .decode()
        )
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
