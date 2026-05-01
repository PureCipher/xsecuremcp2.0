"""Tests for the third-party curation backend (Iteration 2)."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from fastmcp.server.security.certification.manifest import PermissionScope
from fastmcp.server.security.gateway.tool_marketplace import (
    AttestationKind,
    ToolCategory,
    UpstreamChannel,
    UpstreamRef,
)
from purecipher import PureCipherRegistry
from purecipher.curation import (
    HTTPUpstreamFetcher,
    UpstreamResolutionError,
    parse_http_upstream,
)
from purecipher.curation.introspector import (
    CapabilityResource,
    CapabilityTool,
    HTTPIntrospector,
    IntrospectionError,
    IntrospectionResult,
)
from purecipher.curation.manifest_generator import (
    derive_manifest_draft,
    reconcile_curator_selection,
)

TEST_SIGNING_SECRET = "purecipher-curation-test-signing-secret"


# ── Upstream URL parsing ───────────────────────────────────────────


class TestParseHttpUpstream:
    def test_https_url_parses_cleanly(self):
        ref = parse_http_upstream("https://mcp.example.com/sse")
        assert ref.channel == UpstreamChannel.HTTP
        assert ref.identifier == "https://mcp.example.com/sse"
        assert ref.metadata["scheme"] == "https"
        assert ref.metadata["host"] == "mcp.example.com"

    def test_loopback_http_allowed(self):
        ref = parse_http_upstream("http://localhost:8000/mcp")
        assert ref.channel == UpstreamChannel.HTTP
        assert ref.metadata["host"] == "localhost"

    def test_plain_http_remote_rejected(self):
        with pytest.raises(UpstreamResolutionError, match="loopback"):
            parse_http_upstream("http://mcp.example.com/sse")

    def test_unknown_scheme_rejected(self):
        with pytest.raises(UpstreamResolutionError, match="https://"):
            parse_http_upstream("ftp://example.com/mcp")

    def test_empty_input_rejected(self):
        with pytest.raises(UpstreamResolutionError, match="Paste"):
            parse_http_upstream("")

    def test_path_without_host_rejected(self):
        with pytest.raises(UpstreamResolutionError, match="missing a host"):
            parse_http_upstream("https:///just-a-path")

    def test_fragment_stripped_from_canonical_identifier(self):
        ref = parse_http_upstream("https://mcp.example.com/sse#frag")
        assert "frag" not in ref.identifier


class TestHTTPUpstreamFetcher:
    def test_resolve_produces_preview_with_slug(self):
        preview = HTTPUpstreamFetcher().resolve("https://mcp.upstash.com/context7")
        assert preview.upstream_ref.channel == UpstreamChannel.HTTP
        assert preview.suggested_tool_name == "context7"
        assert preview.suggested_display_name == "Context7"
        assert preview.notes == []

    def test_loopback_preview_carries_warning_note(self):
        preview = HTTPUpstreamFetcher().resolve("https://localhost:8080/mcp")
        # ``/mcp`` is a transport marker, so the slug falls back to the
        # host's primary label (``localhost``).
        assert preview.suggested_tool_name == "localhost"
        assert any("loopback" in note.lower() for note in preview.notes)

    def test_invalid_url_surfaces_error(self):
        with pytest.raises(UpstreamResolutionError):
            HTTPUpstreamFetcher().resolve("not-a-url")


# ── Introspector ────────────────────────────────────────────────


class _FakeTool:
    def __init__(self, name: str, description: str = "", schema: dict | None = None):
        self.name = name
        self.description = description
        self.inputSchema = schema or {}


class _FakeClient:
    """Async-context-manager stand-in for ``fastmcp.Client``."""

    def __init__(
        self,
        tools: list[Any] | None = None,
        resources: list[Any] | None = None,
        prompts: list[Any] | None = None,
        connect_error: BaseException | None = None,
    ) -> None:
        self._tools = tools or []
        self._resources = resources or []
        self._prompts = prompts or []
        self._connect_error = connect_error

    async def __aenter__(self):
        if self._connect_error is not None:
            raise self._connect_error
        return self

    async def __aexit__(self, *args):
        return False

    async def list_tools(self):
        return self._tools

    async def list_resources(self):
        return self._resources

    async def list_prompts(self):
        return self._prompts


class TestHTTPIntrospector:
    @pytest.mark.asyncio
    async def test_introspect_captures_tools_and_resources(self):
        fake = _FakeClient(
            tools=[
                _FakeTool(
                    "fetch_url",
                    "Fetch a URL",
                    {"properties": {"url": {"type": "string"}}},
                ),
                _FakeTool(
                    "save_doc",
                    "Save a document",
                    {"properties": {"path": {"type": "string"}}},
                ),
            ]
        )
        introspector = HTTPIntrospector(client_factory=lambda url: fake)
        ref = parse_http_upstream("https://mcp.example.com/sse")

        result = await introspector.introspect(ref)

        assert result.tool_count == 2
        assert result.tools[0].name == "fetch_url"
        assert "url" in result.tools[0].input_schema["properties"]

    @pytest.mark.asyncio
    async def test_introspect_tolerates_missing_resources_and_prompts(self):
        class _ResourceFailingClient(_FakeClient):
            async def list_resources(self):
                raise RuntimeError("resources/list not implemented")

            async def list_prompts(self):
                raise RuntimeError("prompts/list not implemented")

        fake = _ResourceFailingClient(tools=[_FakeTool("ping")])
        introspector = HTTPIntrospector(client_factory=lambda url: fake)
        result = await introspector.introspect(
            parse_http_upstream("https://mcp.example.com/sse")
        )
        assert result.tool_count == 1
        assert result.resource_count == 0
        assert result.prompt_count == 0

    @pytest.mark.asyncio
    async def test_introspect_surfaces_connect_failure(self):
        fake = _FakeClient(connect_error=ConnectionRefusedError("nope"))
        introspector = HTTPIntrospector(client_factory=lambda url: fake)
        with pytest.raises(IntrospectionError, match="Couldn't connect"):
            await introspector.introspect(
                parse_http_upstream("https://mcp.example.com/sse")
            )

    @pytest.mark.asyncio
    async def test_introspect_rejects_non_http_channel(self):
        introspector = HTTPIntrospector()
        bad_ref = UpstreamRef(channel=UpstreamChannel.PYPI, identifier="x")
        with pytest.raises(IntrospectionError, match="HTTP"):
            await introspector.introspect(bad_ref)


# ── Manifest derivation ─────────────────────────────────────────


class TestDeriveManifestDraft:
    def test_network_keyword_implies_network_access(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[CapabilityTool(name="fetch_url", description="Fetch a URL")],
        )
        draft = derive_manifest_draft(intro, suggested_tool_name="x")
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.NETWORK_ACCESS in scopes

    def test_path_argument_implies_filesystem_read(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="describe",  # opaque name
                    description="",
                    input_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                )
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.FILE_SYSTEM_READ in scopes

    def test_resources_imply_read_resource(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[CapabilityTool(name="hello")],
            resources=[CapabilityResource(uri="data://x")],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.READ_RESOURCE in scopes

    def test_no_keywords_yields_default_network_suggestion(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[CapabilityTool(name="opaque", description="")],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.NETWORK_ACCESS in scopes

    def test_observed_tool_names_recorded(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(name="alpha"),
                CapabilityTool(name="beta"),
            ],
        )
        draft = derive_manifest_draft(intro)
        assert sorted(draft.observed_tool_names) == ["alpha", "beta"]


class TestIter14_9Heuristics:
    """Iter 14.9 — tightened permission heuristics.

    The earlier broad keyword sets fired FILE_SYSTEM_*/SUBPROCESS_EXEC
    on REST CRUD verbs (``get``, ``create``, ``update``, ``run``,
    ``command``), which produced absurd suggestions for API-shaped
    MCP servers like Jira / Linear / Slack. Filesystem and subprocess
    scopes now require *structural* evidence — either a fs-noun + verb
    co-occurrence in the name, or a schema arg that names the resource.
    """

    def test_jira_crud_names_do_not_imply_filesystem(self):
        """A Jira-style CRUD surface must NOT suggest filesystem
        read/write. Pre-14.9 every ``jira_get_*`` matched ``get`` →
        FS_READ and every ``jira_create_*`` matched ``create`` →
        FS_WRITE. Post-14.9 the only suggestion is NETWORK_ACCESS."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="jira_get_issue",
                    description="Get a Jira issue by key",
                ),
                CapabilityTool(
                    name="jira_create_issue",
                    description="Create a new Jira issue",
                ),
                CapabilityTool(
                    name="jira_update_issue",
                    description="Update a Jira issue's fields",
                ),
                CapabilityTool(
                    name="jira_search",
                    description="Search Jira issues using JQL",
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.FILE_SYSTEM_READ not in scopes
        assert PermissionScope.FILE_SYSTEM_WRITE not in scopes
        assert PermissionScope.SUBPROCESS_EXEC not in scopes
        # Network access should still fire — Jira's a REST API.
        assert PermissionScope.NETWORK_ACCESS in scopes

    def test_jira_batch_changelogs_does_not_imply_subprocess(self):
        """The Jira tool ``jira_batch_get_changelogs`` previously
        matched ``run`` in its description and fired SUBPROCESS_EXEC.
        With the strict subprocess vocabulary, no false positive."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="jira_batch_get_changelogs",
                    description=(
                        "Run a batch operation to retrieve changelogs "
                        "for multiple issues"
                    ),
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.SUBPROCESS_EXEC not in scopes

    def test_filesystem_mcp_names_still_fire_correctly(self):
        """Real filesystem-MCP names ``read_file``/``write_file``/
        ``list_directory`` continue to fire FS_READ/FS_WRITE. The
        co-occurrence rule (noun + verb) catches them cleanly."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="read_file",
                    description="Read a file's contents",
                ),
                CapabilityTool(
                    name="write_file",
                    description="Write content to a file",
                ),
                CapabilityTool(
                    name="list_directory",
                    description="List directory contents",
                ),
                CapabilityTool(
                    name="delete_file",
                    description="Delete a file",
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.FILE_SYSTEM_READ in scopes
        assert PermissionScope.FILE_SYSTEM_WRITE in scopes

    def test_filesystem_via_schema_arg_still_fires(self):
        """Even with an opaque tool name, a ``path``/``file_path``
        schema argument continues to fire FS_READ. This is the
        primary signal post-Iter 14.9."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="opaque_tool",
                    description="",
                    input_schema={
                        "properties": {"path": {"type": "string"}},
                    },
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.FILE_SYSTEM_READ in scopes

    def test_subprocess_via_schema_arg_still_fires(self):
        """A ``command`` schema arg is the canonical subprocess
        signal — fires SUBPROCESS_EXEC even when the tool name is
        innocuous."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="run_check",
                    description="Run a custom diagnostic",
                    input_schema={
                        "properties": {
                            "command": {"type": "string"},
                            "args": {"type": "array"},
                        },
                    },
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.SUBPROCESS_EXEC in scopes

    def test_subprocess_strict_vocabulary_fires_via_description(self):
        """A tool whose description includes ``shell``/``exec``/
        ``subprocess`` fires SUBPROCESS_EXEC — these are unambiguous
        terms regardless of the tool name."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="run_check",
                    description="Execute a shell command and return output",
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.SUBPROCESS_EXEC in scopes

    def test_run_query_does_not_imply_subprocess(self):
        """``run_query`` with a SQL-shaped schema is NOT subprocess
        execution. Generic ``run`` was dropped from the name keyword
        set in Iter 14.9 precisely to stop this false positive."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(
                    name="run_query",
                    description="Issue a database query",
                    input_schema={"properties": {"sql": {"type": "string"}}},
                ),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.SUBPROCESS_EXEC not in scopes

    def test_slack_read_messages_does_not_imply_filesystem(self):
        """A common Slack-shaped name (``read_messages``, ``write_post``)
        contains a fs-coded verb but no fs noun, so the new helper
        skips filesystem inference. The previous heuristic fired both."""
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(name="read_messages"),
                CapabilityTool(name="write_post"),
            ],
        )
        draft = derive_manifest_draft(intro)
        scopes = {s.scope for s in draft.permission_suggestions}
        assert PermissionScope.FILE_SYSTEM_READ not in scopes
        assert PermissionScope.FILE_SYSTEM_WRITE not in scopes


class TestReconcileCuratorSelection:
    def _draft(self):
        intro = IntrospectionResult(
            upstream_ref=parse_http_upstream("https://x.example/mcp"),
            tools=[
                CapabilityTool(name="fetch_url"),
                CapabilityTool(name="save_doc"),
            ],
        )
        return derive_manifest_draft(intro)

    def test_curator_can_remove_a_suggestion(self):
        draft = self._draft()
        # Pick the network-access suggestion and unselect it.
        updated = reconcile_curator_selection(
            draft,
            [
                {
                    "scope": PermissionScope.NETWORK_ACCESS.value,
                    "selected": False,
                }
            ],
        )
        net = next(
            s
            for s in updated.permission_suggestions
            if s.scope == PermissionScope.NETWORK_ACCESS
        )
        assert net.selected is False

    def test_curator_cannot_add_unobserved_scope(self):
        draft = self._draft()
        # Try to add CROSS_ORIGIN — was never observed.
        updated = reconcile_curator_selection(
            draft,
            [{"scope": PermissionScope.CROSS_ORIGIN.value, "selected": True}],
        )
        scopes = {s.scope for s in updated.permission_suggestions}
        assert PermissionScope.CROSS_ORIGIN not in scopes

    def test_unrelated_selection_entries_ignored(self):
        draft = self._draft()
        updated = reconcile_curator_selection(
            draft,
            [{"scope": "garbage", "selected": True}, "not-a-dict"],
        )
        # Original suggestion list shape unchanged.
        assert len(updated.permission_suggestions) == len(draft.permission_suggestions)

    def test_build_manifest_emits_call_tool_implicitly(self):
        draft = self._draft()
        manifest = draft.build_manifest(
            tool_name="example", author="curator", version="0.1.0"
        )
        assert PermissionScope.CALL_TOOL in manifest.permissions


# ── HTTP routes ────────────────────────────────────────────────


class TestCurateRoutes:
    """End-to-end registry-route tests for /registry/curate/*."""

    def _registry(self, fake_client: _FakeClient):
        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        # Inject the fake introspector so we don't hit the network.
        registry.set_curation_introspector(
            HTTPIntrospector(client_factory=lambda _url: fake_client)
        )
        return registry

    def test_resolve_route_returns_preview(self):
        registry = self._registry(_FakeClient())
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/resolve",
                json={"upstream_url": "https://mcp.upstash.com/context7"},
            )
            assert r.status_code == 200
            preview = r.json()["preview"]
            assert preview["suggested_tool_name"] == "context7"
            assert preview["upstream_ref"]["channel"] == "http"

    def test_resolve_rejects_bad_url(self):
        registry = self._registry(_FakeClient())
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/resolve",
                json={"upstream_url": "ftp://nope.example/mcp"},
            )
            assert r.status_code == 400
            assert "https://" in r.json()["error"]

    def test_introspect_returns_capability_surface(self):
        fake = _FakeClient(
            tools=[
                _FakeTool(
                    "fetch_url",
                    "Fetch a URL",
                    {"properties": {"url": {"type": "string"}}},
                ),
            ]
        )
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={"upstream_url": "https://mcp.example.com/sse"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["introspection"]["tool_count"] == 1
            scopes = {p["scope"] for p in body["draft"]["permission_suggestions"]}
            assert PermissionScope.NETWORK_ACCESS.value in scopes

    def test_introspect_502_when_upstream_unreachable(self):
        fake = _FakeClient(connect_error=ConnectionRefusedError("nope"))
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={"upstream_url": "https://mcp.example.com/sse"},
            )
            assert r.status_code == 502
            assert "Couldn't connect" in r.json()["error"]

    def test_submit_creates_curator_attested_listing(self):
        fake = _FakeClient(
            tools=[
                _FakeTool(
                    "fetch_url",
                    "Fetch a URL",
                    {"properties": {"url": {"type": "string"}}},
                ),
            ]
        )
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream_url": "https://mcp.example.com/sse",
                    "tool_name": "example-mcp",
                    "display_name": "Example MCP",
                    "version": "1.0.0",
                    "selected_permissions": [
                        {
                            "scope": PermissionScope.NETWORK_ACCESS.value,
                            "selected": True,
                        }
                    ],
                },
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["accepted"] is True
            assert body["listing"]["attestation_kind"] == "curator"
            assert (
                body["listing"]["upstream_ref"]["identifier"]
                == "https://mcp.example.com/sse"
            )
            # When auth is disabled, curator_id falls back to "local".
            assert body["listing"]["curator_id"] == "local"

    def test_submit_curator_cannot_smuggle_unobserved_scope(self):
        """Even if the curator sends ``selected: True`` for a scope the
        registry didn't observe, the resulting manifest must not carry
        it. Confirm/remove only — never add."""
        fake = _FakeClient(tools=[_FakeTool("opaque")])
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream_url": "https://mcp.example.com/sse",
                    "tool_name": "opaque-mcp",
                    "version": "1.0.0",
                    "selected_permissions": [
                        {
                            "scope": PermissionScope.SUBPROCESS_EXEC.value,
                            "selected": True,
                        }
                    ],
                },
            )
            assert r.status_code == 201
            permissions = (
                r.json()["listing"]
                # The manifest is embedded in the listing's serialized
                # form via the marketplace; we instead read back the
                # curator listing and inspect its manifest.
            )
            # Use the registry directly to fetch the stored manifest.
            stored = registry._marketplace().get_by_name("opaque-mcp")
            assert stored is not None
            assert PermissionScope.SUBPROCESS_EXEC not in stored.manifest.permissions

    def test_submit_invalid_url_returns_400(self):
        registry = self._registry(_FakeClient())
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={"upstream_url": "ftp://nope/", "tool_name": "x"},
            )
            assert r.status_code == 400


# ── Bug-fix regressions ─────────────────────────────────────────


class TestSSRFDefence:
    """parse_http_upstream must refuse private / link-local /
    cloud-metadata IP literals so the introspector can't be tricked
    into probing internal infrastructure."""

    @pytest.mark.parametrize(
        "url,fragment_in_error",
        [
            ("https://10.0.0.1/admin", "private"),
            ("https://192.168.1.1/admin", "private"),
            ("https://172.16.0.1/admin", "private"),
            ("https://169.254.169.254/latest/meta-data/", "metadata"),
            ("https://metadata.google.internal/", "metadata"),
            ("https://[::1]/mcp", None),  # explicit-loopback IPv6 IS allowed
            ("https://[fe80::1]/mcp", "private"),  # link-local IPv6
        ],
    )
    def test_internal_addresses_rejected(self, url: str, fragment_in_error: str | None):
        if fragment_in_error is None:
            # Loopback IPv6 should pass.
            ref = parse_http_upstream(url)
            assert ref.channel == UpstreamChannel.HTTP
            return
        with pytest.raises(UpstreamResolutionError) as exc_info:
            parse_http_upstream(url)
        assert fragment_in_error in str(exc_info.value).lower()

    def test_public_hostname_accepted(self):
        ref = parse_http_upstream("https://mcp.example.com/sse")
        assert ref.channel == UpstreamChannel.HTTP


class TestSlugQuality:
    """The auto-derived tool_name should pick a brand-y label rather
    than a transport marker. Regression for the smoke test that
    produced ``tool_name=sse`` from ``mcp.context7.com/sse``."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://mcp.context7.com/sse", "context7"),
            ("https://api.example.com/mcp", "example"),
            ("https://mcp.upstash.com/redis-stream", "redis-stream"),
            ("https://example.com/", "example"),
            ("https://mcp.example.com/stream", "example"),
            ("https://mcp.example.com/v1/tools", "tools"),
        ],
    )
    def test_slug_picks_brand_over_transport(self, url: str, expected: str):
        preview = HTTPUpstreamFetcher().resolve(url)
        assert preview.suggested_tool_name == expected


class TestUrlCanonicalization:
    """Same upstream addressed two ways must produce the same identifier
    so dedup works at the marketplace layer."""

    def test_trailing_slash_normalized(self):
        a = parse_http_upstream("https://mcp.example.com/sse").identifier
        b = parse_http_upstream("https://mcp.example.com/sse/").identifier
        assert a == b

    def test_scheme_lowercased(self):
        a = parse_http_upstream("HTTPS://mcp.example.com/sse").identifier
        b = parse_http_upstream("https://mcp.example.com/sse").identifier
        assert a == b


class TestAuthorListingTakeoverPrevention:
    """A curator submitting the same tool_name as an existing
    author-attested listing must NOT silently flip it to curator —
    that would be a takeover."""

    def test_curator_cannot_overwrite_author_listing(self):
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolMarketplace,
            UpstreamChannel,
            UpstreamRef,
        )

        marketplace = ToolMarketplace()
        # Author publishes first.
        marketplace.publish(
            tool_name="markitdown",
            display_name="Markitdown",
            version="1.0.0",
            author="microsoft",
        )
        # Curator tries to onboard the same tool_name — must be refused.
        with pytest.raises(ValueError, match="author-attested"):
            marketplace.publish(
                tool_name="markitdown",
                display_name="Markitdown (curated)",
                version="1.0.0",
                attestation_kind=AttestationKind.CURATOR,
                curator_id="@curator",
                hosting_mode=HostingMode.PROXY,
                upstream_ref=UpstreamRef(
                    channel=UpstreamChannel.HTTP,
                    identifier="https://mcp.example.com/sse",
                ),
            )

    def test_author_can_still_republish_their_own_listing(self):
        """The takeover guard must not break legitimate author
        republishes (version bumps, description edits, etc.)."""
        from fastmcp.server.security.gateway.tool_marketplace import (
            ToolMarketplace,
        )

        marketplace = ToolMarketplace()
        marketplace.publish(tool_name="my-tool", version="1.0.0", author="me")
        listing = marketplace.publish(
            tool_name="my-tool",
            version="1.1.0",
            author="me",
            description="now with new features",
        )
        assert listing.attestation_kind == AttestationKind.AUTHOR
        assert listing.version == "1.1.0"

    def test_curator_can_republish_their_own_curator_listing(self):
        """A curator updating an existing curator-attested listing
        with new permissions / version should still work."""
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolMarketplace,
            UpstreamChannel,
            UpstreamRef,
        )

        marketplace = ToolMarketplace()
        ref = UpstreamRef(
            channel=UpstreamChannel.HTTP,
            identifier="https://x.example/mcp",
        )
        marketplace.publish(
            tool_name="curated",
            version="1.0.0",
            attestation_kind=AttestationKind.CURATOR,
            curator_id="@curator",
            hosting_mode=HostingMode.CATALOG,
            upstream_ref=ref,
        )
        listing = marketplace.publish(
            tool_name="curated",
            version="1.1.0",
            attestation_kind=AttestationKind.CURATOR,
            curator_id="@curator",
            upstream_ref=ref,
        )
        assert listing.attestation_kind == AttestationKind.CURATOR
        assert listing.version == "1.1.0"


# ── Iteration 4: PyPI + npm channels ────────────────────────────


class TestParseUpstreamDispatch:
    def test_parses_https_as_http_channel(self):
        from purecipher.curation import parse_upstream

        ref = parse_upstream("https://mcp.example.com/sse")
        assert ref.channel == UpstreamChannel.HTTP

    def test_parses_pypi_prefix(self):
        from purecipher.curation import parse_upstream

        ref = parse_upstream("pypi:markitdown-mcp@1.2.3")
        assert ref.channel == UpstreamChannel.PYPI
        assert ref.identifier == "markitdown-mcp"
        assert ref.version == "1.2.3"

    def test_parses_npm_prefix(self):
        from purecipher.curation import parse_upstream

        ref = parse_upstream("npm:@modelcontextprotocol/server-everything@0.5.0")
        assert ref.channel == UpstreamChannel.NPM
        assert ref.identifier == "@modelcontextprotocol/server-everything"
        assert ref.version == "0.5.0"

    def test_parses_docker_prefix(self):
        from purecipher.curation import parse_upstream

        ref = parse_upstream("docker:ghcr.io/example/mcp:v1")
        assert ref.channel == UpstreamChannel.DOCKER
        assert ref.identifier == "ghcr.io/example/mcp"
        assert ref.version == "v1"

    def test_unknown_prefix_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_upstream,
        )

        # ``ftp://...`` and ``git+...`` are not in our supported set.
        with pytest.raises(UpstreamResolutionError, match="kind of upstream"):
            parse_upstream("ftp://example.com/mcp")

    def test_bare_package_name_rejected(self):
        """A bare ``markitdown-mcp`` could be PyPI, npm, or a slug —
        require the prefix to be unambiguous."""
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_upstream,
        )

        with pytest.raises(UpstreamResolutionError):
            parse_upstream("markitdown-mcp")


class TestParsePyPIUpstream:
    def test_with_version(self):
        from purecipher.curation import parse_pypi_upstream

        ref = parse_pypi_upstream("pypi:markitdown-mcp@1.2.3")
        assert ref.identifier == "markitdown-mcp"
        assert ref.version == "1.2.3"

    def test_without_version(self):
        from purecipher.curation import parse_pypi_upstream

        ref = parse_pypi_upstream("pypi:markitdown-mcp")
        assert ref.identifier == "markitdown-mcp"
        assert ref.version == ""

    def test_invalid_pkg_name_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_pypi_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid"):
            parse_pypi_upstream("pypi:has spaces")

    def test_empty_after_prefix_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_pypi_upstream,
        )

        with pytest.raises(UpstreamResolutionError):
            parse_pypi_upstream("pypi:")

    def test_missing_prefix_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_pypi_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="pypi:"):
            parse_pypi_upstream("markitdown-mcp")


class TestParseNpmUpstream:
    def test_scoped_with_version(self):
        from purecipher.curation import parse_npm_upstream

        ref = parse_npm_upstream("npm:@scope/pkg@2.0.0")
        assert ref.identifier == "@scope/pkg"
        assert ref.version == "2.0.0"

    def test_unscoped_without_version(self):
        from purecipher.curation import parse_npm_upstream

        ref = parse_npm_upstream("npm:simple-pkg")
        assert ref.identifier == "simple-pkg"
        assert ref.version == ""

    def test_scoped_without_version(self):
        from purecipher.curation import parse_npm_upstream

        ref = parse_npm_upstream("npm:@scope/pkg")
        assert ref.identifier == "@scope/pkg"
        assert ref.version == ""

    def test_invalid_pkg_name_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_npm_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid"):
            parse_npm_upstream("npm:has spaces")


class TestParseDockerUpstream:
    """The ``docker:`` parser must accept the OCI reference grammar
    (image, image:tag, image@digest, registry/path/image, with
    optional port on the registry) and reject obvious garbage."""

    def test_bare_image_no_tag_no_digest(self):
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:nginx")
        assert ref.channel == UpstreamChannel.DOCKER
        assert ref.identifier == "nginx"
        assert ref.version == ""
        assert ref.pinned_hash == ""
        assert ref.metadata.get("registry") == "docker.io"

    def test_image_with_tag(self):
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:nginx:1.27")
        assert ref.identifier == "nginx"
        assert ref.version == "1.27"
        assert ref.pinned_hash == ""

    def test_image_with_digest_only(self):
        from purecipher.curation import parse_docker_upstream

        digest = "sha256:" + "a" * 64
        ref = parse_docker_upstream(f"docker:nginx@{digest}")
        assert ref.identifier == "nginx"
        assert ref.version == ""
        assert ref.pinned_hash == digest

    def test_image_with_tag_and_digest(self):
        from purecipher.curation import parse_docker_upstream

        digest = "sha256:" + "b" * 64
        ref = parse_docker_upstream(f"docker:nginx:1.27@{digest}")
        assert ref.identifier == "nginx"
        assert ref.version == "1.27"
        assert ref.pinned_hash == digest

    def test_namespace_image(self):
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:library/nginx:1.27")
        assert ref.identifier == "library/nginx"
        assert ref.version == "1.27"
        # No registry domain in the first component → defaults to docker.io.
        assert ref.metadata["registry"] == "docker.io"

    def test_custom_registry_image(self):
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:ghcr.io/example/mcp:v1")
        assert ref.identifier == "ghcr.io/example/mcp"
        assert ref.version == "v1"
        assert ref.metadata["registry"] == "ghcr.io"

    def test_custom_registry_with_port(self):
        """A port on the first component (``localhost:5000``) must be
        treated as part of the registry domain, NOT as a tag."""
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:localhost:5000/img:dev")
        assert ref.identifier == "localhost:5000/img"
        assert ref.version == "dev"
        assert ref.metadata["registry"] == "localhost:5000"

    def test_custom_registry_with_port_and_digest(self):
        from purecipher.curation import parse_docker_upstream

        digest = "sha256:" + "c" * 64
        ref = parse_docker_upstream(f"docker:registry.internal:8443/team/mcp@{digest}")
        assert ref.identifier == "registry.internal:8443/team/mcp"
        assert ref.version == ""
        assert ref.pinned_hash == digest

    def test_localhost_without_port(self):
        from purecipher.curation import parse_docker_upstream

        ref = parse_docker_upstream("docker:localhost/img:tag")
        assert ref.identifier == "localhost/img"
        assert ref.metadata["registry"] == "localhost"

    def test_sha512_digest_accepted(self):
        from purecipher.curation import parse_docker_upstream

        digest = "sha512:" + "a" * 128
        ref = parse_docker_upstream(f"docker:nginx@{digest}")
        assert ref.pinned_hash == digest

    def test_missing_prefix_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="docker:"):
            parse_docker_upstream("ghcr.io/example/mcp:v1")

    def test_empty_after_prefix_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Empty"):
            parse_docker_upstream("docker:")

    def test_invalid_image_chars_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker image"):
            parse_docker_upstream("docker:bad image:tag")

    def test_uppercase_image_rejected(self):
        """OCI references are lowercase-only — uppercase is rejected
        so the listing matches what ``docker pull`` would accept."""
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker image"):
            parse_docker_upstream("docker:GHCR.io/X/Y")

    def test_invalid_tag_rejected(self):
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker tag"):
            parse_docker_upstream("docker:nginx:.bad")

    def test_invalid_digest_rejected(self):
        """Bare hashes (no algorithm prefix) and unsupported algorithms
        are rejected."""
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker digest"):
            parse_docker_upstream("docker:nginx@" + "a" * 64)

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker digest"):
            parse_docker_upstream("docker:nginx@md5:" + "a" * 32)

    def test_short_digest_rejected(self):
        """sha256 digests must be exactly 64 hex chars."""
        from purecipher.curation import (
            UpstreamResolutionError,
            parse_docker_upstream,
        )

        with pytest.raises(UpstreamResolutionError, match="Invalid Docker digest"):
            parse_docker_upstream("docker:nginx@sha256:abcd")

    def test_image_ref_for_reconstruction(self):
        """``image_ref_for`` must reconstruct the canonical
        ``image[:tag][@digest]`` form for use with ``docker run``."""
        from purecipher.curation import image_ref_for, parse_docker_upstream

        ref = parse_docker_upstream("docker:ghcr.io/x/y:v1")
        assert image_ref_for(ref) == "ghcr.io/x/y:v1"

        digest = "sha256:" + "f" * 64
        ref = parse_docker_upstream(f"docker:ghcr.io/x/y:v1@{digest}")
        assert image_ref_for(ref) == f"ghcr.io/x/y:v1@{digest}"

        ref = parse_docker_upstream(f"docker:ghcr.io/x/y@{digest}")
        assert image_ref_for(ref) == f"ghcr.io/x/y@{digest}"

        ref = parse_docker_upstream("docker:nginx")
        assert image_ref_for(ref) == "nginx"


class TestDockerUpstreamFetcher:
    """The fetcher is pure-parsing (no network calls). It validates the
    reference, derives a slug, and surfaces curator-facing notes for
    common pitfalls (no digest, ``latest`` tag, custom registry)."""

    def test_resolve_pinned_digest_no_notes_about_pinning(self):
        from purecipher.curation import DockerUpstreamFetcher

        digest = "sha256:" + "1" * 64
        preview = DockerUpstreamFetcher().resolve(
            f"docker:ghcr.io/example/mcp:v1@{digest}"
        )
        assert preview.upstream_ref.channel == UpstreamChannel.DOCKER
        assert preview.upstream_ref.pinned_hash == digest
        assert preview.suggested_tool_name == "mcp"
        # No "no digest was supplied" warning when a digest is present.
        assert not any("No digest" in note for note in preview.notes)

    def test_resolve_no_digest_emits_warning(self):
        from purecipher.curation import DockerUpstreamFetcher

        preview = DockerUpstreamFetcher().resolve("docker:ghcr.io/x/y:v1")
        assert any("No digest" in note for note in preview.notes)

    def test_resolve_latest_tag_emits_warning(self):
        from purecipher.curation import DockerUpstreamFetcher

        preview = DockerUpstreamFetcher().resolve("docker:nginx:latest")
        assert any("'latest' floats" in note for note in preview.notes)

    def test_resolve_custom_registry_emits_warning(self):
        from purecipher.curation import DockerUpstreamFetcher

        preview = DockerUpstreamFetcher().resolve("docker:ghcr.io/x/y:v1")
        assert any("not Docker Hub" in note for note in preview.notes)

    def test_resolve_dockerhub_no_custom_registry_warning(self):
        from purecipher.curation import DockerUpstreamFetcher

        preview = DockerUpstreamFetcher().resolve("docker:nginx:1.27")
        assert not any("not Docker Hub" in note for note in preview.notes)

    def test_resolve_slug_from_leaf_path_component(self):
        from purecipher.curation import DockerUpstreamFetcher

        for raw, expected_slug in (
            ("docker:nginx", "nginx"),
            ("docker:library/nginx", "nginx"),
            ("docker:ghcr.io/example/markitdown-mcp:v1", "markitdown-mcp"),
            ("docker:registry.internal:8443/team/mcp:dev", "mcp"),
        ):
            preview = DockerUpstreamFetcher().resolve(raw)
            assert preview.suggested_tool_name == expected_slug, raw

    def test_resolve_propagates_invalid_input(self):
        from purecipher.curation import (
            DockerUpstreamFetcher,
            UpstreamResolutionError,
        )

        with pytest.raises(UpstreamResolutionError):
            DockerUpstreamFetcher().resolve("docker:bad image:tag")


class _FakeHttpResponse:
    """Stand-in for httpx.Response — exposes the trio of methods our
    fetcher relies on."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        json_payload: Any = None,
    ) -> None:
        self.status_code = status_code
        self._payload = json_payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Any:
        return self._payload


class _FakeHttpClient:
    """Stand-in for httpx.Client supporting context-manager + .get()."""

    def __init__(self, response: _FakeHttpResponse | Exception) -> None:
        self._response = response

    def __enter__(self) -> _FakeHttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def get(self, url: str) -> _FakeHttpResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class TestPyPIUpstreamFetcher:
    def test_resolve_picks_latest_version(self):
        from purecipher.curation import PyPIUpstreamFetcher

        payload = {
            "info": {
                "name": "markitdown-mcp",
                "version": "1.2.3",
                "summary": "Convert files to markdown",
                "license": "MIT",
                "project_url": "https://github.com/microsoft/markitdown",
            },
            "releases": {
                "1.2.3": [
                    {"digests": {"sha256": "a" * 64}},
                    {"digests": {"sha256": "b" * 64}},
                ]
            },
        }
        fetcher = PyPIUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(
                _FakeHttpResponse(json_payload=payload)
            )
        )
        preview = fetcher.resolve("pypi:markitdown-mcp")

        assert preview.upstream_ref.channel == UpstreamChannel.PYPI
        assert preview.upstream_ref.identifier == "markitdown-mcp"
        assert preview.upstream_ref.version == "1.2.3"
        assert preview.upstream_ref.pinned_hash == "sha256:" + ("a" * 64)
        assert (
            preview.upstream_ref.source_url == "https://github.com/microsoft/markitdown"
        )
        assert preview.suggested_tool_name == "markitdown-mcp"
        # Latest-version note explains the auto-pin.
        assert any("latest" in n.lower() for n in preview.notes)

    def test_resolve_404_returns_user_friendly_error(self):
        from purecipher.curation import (
            PyPIUpstreamFetcher,
            UpstreamResolutionError,
        )

        fetcher = PyPIUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(
                _FakeHttpResponse(status_code=404)
            )
        )
        with pytest.raises(UpstreamResolutionError, match="couldn't find"):
            fetcher.resolve("pypi:nonexistent-pkg")

    def test_resolve_network_failure_surfaces_error(self):
        from purecipher.curation import (
            PyPIUpstreamFetcher,
            UpstreamResolutionError,
        )

        fetcher = PyPIUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(ConnectionError("network down"))
        )
        with pytest.raises(UpstreamResolutionError, match="Couldn't reach PyPI"):
            fetcher.resolve("pypi:any-pkg")


class TestNpmUpstreamFetcher:
    def test_resolve_scoped_package(self):
        from purecipher.curation import NpmUpstreamFetcher

        payload = {
            "name": "@modelcontextprotocol/server-everything",
            "description": "Demo MCP server",
            "dist-tags": {"latest": "0.5.0"},
            "versions": {
                "0.5.0": {
                    "name": "@modelcontextprotocol/server-everything",
                    "license": "MIT",
                    "dist": {
                        "integrity": "sha512-abc",
                        "shasum": "abc123",
                    },
                    "repository": {
                        "url": "git+https://github.com/x/y.git",
                    },
                }
            },
        }
        fetcher = NpmUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(
                _FakeHttpResponse(json_payload=payload)
            )
        )
        preview = fetcher.resolve("npm:@modelcontextprotocol/server-everything")

        assert preview.upstream_ref.channel == UpstreamChannel.NPM
        assert (
            preview.upstream_ref.identifier == "@modelcontextprotocol/server-everything"
        )
        assert preview.upstream_ref.version == "0.5.0"
        assert preview.upstream_ref.pinned_hash == "sha512-abc"
        # ``git+`` prefix and ``.git`` suffix are stripped.
        assert preview.upstream_ref.source_url == "https://github.com/x/y"
        # Slug strips the scope.
        assert preview.suggested_tool_name == "server-everything"

    def test_resolve_404(self):
        from purecipher.curation import (
            NpmUpstreamFetcher,
            UpstreamResolutionError,
        )

        fetcher = NpmUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(
                _FakeHttpResponse(status_code=404)
            )
        )
        with pytest.raises(UpstreamResolutionError, match="couldn't find"):
            fetcher.resolve("npm:no-such-pkg")


class TestUpstreamFetcherDispatch:
    """The top-level ``UpstreamFetcher`` should route to the right
    per-channel fetcher based on the parsed channel."""

    def test_dispatches_pypi(self):
        from purecipher.curation import (
            PyPIUpstreamFetcher,
            UpstreamFetcher,
        )

        payload = {
            "info": {"name": "p", "version": "1.0", "summary": "", "license": ""},
            "releases": {"1.0": []},
        }
        pypi = PyPIUpstreamFetcher(
            http_client_factory=lambda: _FakeHttpClient(
                _FakeHttpResponse(json_payload=payload)
            )
        )
        fetcher = UpstreamFetcher(pypi_fetcher=pypi)
        preview = fetcher.resolve("pypi:p@1.0")
        assert preview.upstream_ref.channel == UpstreamChannel.PYPI

    def test_dispatches_http(self):
        from purecipher.curation import UpstreamFetcher

        preview = UpstreamFetcher().resolve("https://mcp.example.com/sse")
        assert preview.upstream_ref.channel == UpstreamChannel.HTTP

    def test_dispatches_docker(self):
        """Docker refs route to the Docker fetcher."""
        from purecipher.curation import UpstreamFetcher

        preview = UpstreamFetcher().resolve("docker:ghcr.io/example/mcp:v1")
        assert preview.upstream_ref.channel == UpstreamChannel.DOCKER
        assert preview.upstream_ref.identifier == "ghcr.io/example/mcp"


class TestStdioIntrospectorDispatch:
    """The stdio introspector should accept PyPI + npm + Docker refs
    and refuse HTTP refs (which are routed to HTTPIntrospector)."""

    def test_rejects_http_channel(self):
        import asyncio

        from purecipher.curation import StdioIntrospector

        introspector = StdioIntrospector()
        ref = parse_http_upstream("https://mcp.example.com/sse")
        with pytest.raises(IntrospectionError, match="PyPI"):
            asyncio.run(introspector.introspect(ref))

    def test_uses_factory_for_pypi(self):
        import asyncio

        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        captured: list = []

        def factory(channel: Any, identifier: str, version: str) -> Any:
            captured.append((channel, identifier, version))
            return _FakeClient(tools=[_FakeTool("hello")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_pypi_upstream("pypi:markitdown-mcp@1.2.3")
        result = asyncio.run(introspector.introspect(ref))

        assert captured == [
            (UpstreamChannel.PYPI, "markitdown-mcp", "1.2.3"),
        ]
        assert result.tool_count == 1

    def test_uses_factory_for_docker(self):
        """Docker refs route through StdioIntrospector and the factory
        receives the channel + image-name + tag tuple."""
        import asyncio

        from purecipher.curation import StdioIntrospector, parse_docker_upstream

        captured: list = []

        def factory(channel: Any, identifier: str, version: str) -> Any:
            captured.append((channel, identifier, version))
            return _FakeClient(tools=[_FakeTool("hello")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_docker_upstream("docker:ghcr.io/example/mcp:v1")
        result = asyncio.run(introspector.introspect(ref))

        assert captured == [
            (UpstreamChannel.DOCKER, "ghcr.io/example/mcp", "v1"),
        ]
        assert result.tool_count == 1

    def test_default_docker_transport_passes_image_ref(self):
        """When no client_factory override is supplied, the default
        ``_build_client`` constructs ``Client(StdioTransport(command=
        'docker', args=[..., image_ref]))``. We don't run the
        subprocess here — just confirm the transport carries the
        expected command + image_ref so the proxy and introspect
        paths are wired identically."""
        from fastmcp.client.transports.stdio import StdioTransport
        from purecipher.curation import StdioIntrospector, parse_docker_upstream

        introspector = StdioIntrospector()
        ref = parse_docker_upstream("docker:ghcr.io/example/mcp:v1@sha256:" + "a" * 64)
        client = introspector._build_client(ref)
        assert isinstance(client.transport, StdioTransport)
        assert client.transport.command == "docker"
        # The full image_ref should be the last arg.
        assert client.transport.args[-1] == (
            "ghcr.io/example/mcp:v1@sha256:" + "a" * 64
        )
        # And the resource flags we set should be in the args list
        # ahead of the image_ref.
        assert "--rm" in client.transport.args
        assert "-i" in client.transport.args
        assert "--memory=512m" in client.transport.args
        assert "--pids-limit=128" in client.transport.args


class TestIntrospectorDispatch:
    """The top-level Introspector picks the right channel."""

    def test_routes_http(self):
        import asyncio

        from purecipher.curation import HTTPIntrospector, Introspector

        http = HTTPIntrospector(
            client_factory=lambda url: _FakeClient(tools=[_FakeTool("a")])
        )
        introspector = Introspector(http_introspector=http)
        result = asyncio.run(
            introspector.introspect(parse_http_upstream("https://x.example/mcp"))
        )
        assert result.tool_count == 1

    def test_routes_pypi(self):
        import asyncio

        from purecipher.curation import (
            Introspector,
            StdioIntrospector,
        )
        from purecipher.curation.upstream import parse_pypi_upstream

        stdio = StdioIntrospector(
            client_factory=lambda *args: _FakeClient(tools=[_FakeTool("xxx")])
        )
        introspector = Introspector(stdio_introspector=stdio)
        result = asyncio.run(introspector.introspect(parse_pypi_upstream("pypi:p@1.0")))
        assert result.tool_count == 1

    def test_routes_docker(self):
        """Docker refs route through the dispatcher to the stdio
        introspector — same path as PyPI/npm."""
        import asyncio

        from purecipher.curation import (
            Introspector,
            StdioIntrospector,
            parse_docker_upstream,
        )

        stdio = StdioIntrospector(
            client_factory=lambda *args: _FakeClient(tools=[_FakeTool("xxx")])
        )
        introspector = Introspector(stdio_introspector=stdio)
        result = asyncio.run(
            introspector.introspect(parse_docker_upstream("docker:ghcr.io/x/y:v1"))
        )
        assert result.tool_count == 1


class TestCurateRoutesMultiChannel:
    """The /curate routes should accept ``upstream`` (new) AND
    ``upstream_url`` (legacy) and dispatch to the right channel."""

    def _registry(
        self,
        *,
        http_intro_tools: list | None = None,
        stdio_intro_tools: list | None = None,
    ):
        from purecipher.curation import (
            HTTPIntrospector,
            Introspector,
            StdioIntrospector,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        http_intro = HTTPIntrospector(
            client_factory=lambda url: _FakeClient(tools=http_intro_tools or []),
        )
        stdio_intro = StdioIntrospector(
            client_factory=lambda *args: _FakeClient(tools=stdio_intro_tools or []),
        )
        registry.set_curation_introspector(
            Introspector(
                http_introspector=http_intro,
                stdio_introspector=stdio_intro,
            )
        )
        return registry

    def test_resolve_accepts_legacy_upstream_url_key(self):
        registry = self._registry()
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/resolve",
                json={"upstream_url": "https://mcp.example.com/sse"},
            )
            assert r.status_code == 200

    def test_resolve_accepts_new_upstream_key(self):
        registry = self._registry()
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/resolve",
                json={"upstream": "https://mcp.example.com/sse"},
            )
            assert r.status_code == 200

    def test_introspect_routes_pypi_through_stdio(self):
        from purecipher.curation import (
            Introspector,
            PyPIUpstreamFetcher,
            StdioIntrospector,
        )

        # Build the registry with a fake httpx for PyPI metadata too.
        pypi_payload = {
            "info": {
                "name": "fake-mcp",
                "version": "1.0.0",
                "summary": "",
                "license": "",
            },
            "releases": {"1.0.0": []},
        }

        class _StubFetcherWiring:
            """Patch UpstreamFetcher with the test pypi fetcher."""

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        stdio_intro = StdioIntrospector(
            client_factory=lambda *args: _FakeClient(
                tools=[_FakeTool("fetch_url", "Fetch a URL")]
            )
        )
        registry.set_curation_introspector(Introspector(stdio_introspector=stdio_intro))
        # Patch the route's UpstreamFetcher constructor so it picks
        # up the fake httpx — done by monkey-patching the class default.
        orig_pypi_init = PyPIUpstreamFetcher.__init__

        def _patched_pypi_init(self, **kwargs):
            kwargs.setdefault(
                "http_client_factory",
                lambda: _FakeHttpClient(_FakeHttpResponse(json_payload=pypi_payload)),
            )
            orig_pypi_init(self, **kwargs)

        PyPIUpstreamFetcher.__init__ = _patched_pypi_init  # type: ignore[assignment]
        try:
            with TestClient(registry.http_app()) as client:
                r = client.post(
                    "/registry/curate/introspect",
                    json={"upstream": "pypi:fake-mcp"},
                )
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["introspection"]["tool_count"] == 1
                assert body["draft"]["upstream_ref"]["channel"] == "pypi"
                assert body["draft"]["upstream_ref"]["version"] == "1.0.0"
        finally:
            PyPIUpstreamFetcher.__init__ = orig_pypi_init  # type: ignore[assignment]


class TestCuratorProxyHosting:
    """Iteration 6: ``hosting_mode: "proxy"`` routes a curator listing
    through a SecureMCP-enforced gateway.

    These tests exercise the *building blocks* — the security-config
    derivation, the proxy server construction, and the listing-lookup
    router. The actual subprocess-based proxy traffic is exercised in
    the broader registry test suite.
    """

    def _curated_listing(
        self,
        *,
        hosting_mode: Any,
        upstream_url: str = "https://mcp.example.com/sse",
        observed_tools: list[str] | None = None,
    ):
        from fastmcp.server.security.certification.manifest import (
            PermissionScope,
            SecurityManifest,
        )
        from fastmcp.server.security.gateway.tool_marketplace import (
            ToolListing,
            UpstreamRef,
        )

        manifest = SecurityManifest(
            tool_name="curated-tool",
            version="1.0.0",
            author="@curator",
            description="Curated for testing",
            permissions={PermissionScope.NETWORK_ACCESS, PermissionScope.CALL_TOOL},
            tags=set(observed_tools or ["fetch", "ping"]) | {"curated"},
        )
        return ToolListing(
            listing_id="lst-curated-001",
            tool_name="curated-tool",
            display_name="Curated Tool",
            version="1.0.0",
            attestation_kind=AttestationKind.CURATOR,
            curator_id="@curator",
            hosting_mode=hosting_mode,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.HTTP,
                identifier=upstream_url,
            ),
            manifest=manifest,
        )

    def test_build_proxy_server_succeeds(self):
        from fastmcp.server.security.gateway.tool_marketplace import HostingMode
        from purecipher.curation import build_curator_proxy_server

        listing = self._curated_listing(hosting_mode=HostingMode.PROXY)
        proxy = build_curator_proxy_server(listing)
        assert proxy is not None
        # Proxy is a SecureMCP instance; security context is attached.
        from securemcp import SecureMCP

        assert isinstance(proxy, SecureMCP)

    def test_build_proxy_refuses_catalog_listing(self):
        from fastmcp.server.security.gateway.tool_marketplace import HostingMode
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        listing = self._curated_listing(hosting_mode=HostingMode.CATALOG)
        with pytest.raises(ProxyHostingError, match="not configured"):
            build_curator_proxy_server(listing)

    def test_build_proxy_refuses_empty_upstream(self):
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        listing = self._curated_listing(
            hosting_mode=HostingMode.PROXY,
            upstream_url="",
        )
        with pytest.raises(ProxyHostingError, match="empty upstream URL"):
            build_curator_proxy_server(listing)

    def test_build_proxy_pypi_uses_uvx_transport_with_version(self):
        """A PyPI-channel listing in proxy mode must construct a Client
        backed by ``UvxStdioTransport`` with the curator-vouched
        identifier and version pinned via ``@<version>``."""
        from fastmcp.client.transports.stdio import UvxStdioTransport
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import build_curator_proxy_server
        from purecipher.curation.proxy_runtime import _build_client_factory

        listing = ToolListing(
            tool_name="pypi-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.PYPI,
                identifier="markitdown-mcp",
                version="1.2.3",
            ),
        )
        # build_curator_proxy_server should succeed end-to-end.
        proxy = build_curator_proxy_server(listing)
        assert proxy is not None

        # And the client factory should produce a uvx-backed Client
        # with the version-pinned spec.
        factory = _build_client_factory(listing)
        client = factory()
        assert isinstance(client.transport, UvxStdioTransport)
        assert client.transport.tool_name == "markitdown-mcp@1.2.3"

    def test_build_proxy_pypi_without_version_drops_at_suffix(self):
        """When the upstream_ref carries no version, the spec passed to
        uvx must be the bare identifier — no stray ``@``."""
        from fastmcp.client.transports.stdio import UvxStdioTransport
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation.proxy_runtime import _build_client_factory

        listing = ToolListing(
            tool_name="pypi-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.PYPI,
                identifier="markitdown-mcp",
                version=None,
            ),
        )
        factory = _build_client_factory(listing)
        client = factory()
        assert isinstance(client.transport, UvxStdioTransport)
        assert client.transport.tool_name == "markitdown-mcp"

    def test_build_proxy_pypi_refuses_empty_identifier(self):
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        listing = ToolListing(
            tool_name="pypi-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.PYPI,
                identifier="",
                version="1.0.0",
            ),
        )
        with pytest.raises(ProxyHostingError, match="empty PyPI"):
            build_curator_proxy_server(listing)

    def test_build_proxy_npm_uses_npx_transport_with_version(self):
        """An npm-channel listing in proxy mode must construct a Client
        backed by ``NpxStdioTransport`` with the curator-vouched
        package and version pinned via ``@<version>``.

        Skipped when ``npx`` isn't installed locally —
        :class:`NpxStdioTransport` validates the launcher at
        construction time so we can't test against a missing binary
        without monkeypatching shutil.which.
        """
        import shutil

        if shutil.which("npx") is None:
            pytest.skip("npx not installed; cannot exercise NpxStdioTransport")

        from fastmcp.client.transports.stdio import NpxStdioTransport
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import build_curator_proxy_server
        from purecipher.curation.proxy_runtime import _build_client_factory

        listing = ToolListing(
            tool_name="npm-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.NPM,
                identifier="@modelcontextprotocol/server-filesystem",
                version="0.6.2",
            ),
        )
        proxy = build_curator_proxy_server(listing)
        assert proxy is not None

        factory = _build_client_factory(listing)
        client = factory()
        assert isinstance(client.transport, NpxStdioTransport)
        assert client.transport.package == (
            "@modelcontextprotocol/server-filesystem@0.6.2"
        )

    def test_build_proxy_npm_surfaces_missing_npx_as_proxy_error(self, monkeypatch):
        """If the registry host doesn't have ``npx`` installed,
        :class:`NpxStdioTransport` raises ``ValueError("Command 'npx'
        not found")``. ``build_curator_proxy_server`` must wrap that as
        a structured :class:`ProxyHostingError` with operator-actionable
        guidance — not let the bare ValueError propagate to the ASGI
        router.
        """
        import fastmcp.client.transports.stdio as stdio_mod
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        # Replace ``NpxStdioTransport`` with a stand-in whose
        # constructor raises the same ValueError the real one raises
        # when ``npx`` is missing on PATH. Using a stand-in (rather
        # than monkeypatching shutil.which) avoids leaving behind a
        # partially constructed StdioTransport whose ``__del__`` would
        # later trip on a missing ``_stop_event`` attribute and dirty
        # the warning state of subsequent tests.
        class _MissingNpxTransport:
            def __init__(self, *args, **kwargs):
                raise ValueError("Command 'npx' not found")

        monkeypatch.setattr(stdio_mod, "NpxStdioTransport", _MissingNpxTransport)

        listing = ToolListing(
            tool_name="npm-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.NPM,
                identifier="@modelcontextprotocol/server-filesystem",
                version="0.6.2",
            ),
        )
        with pytest.raises(ProxyHostingError, match="npx"):
            build_curator_proxy_server(listing)

    def test_build_proxy_npm_refuses_empty_identifier(self):
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        listing = ToolListing(
            tool_name="npm-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.NPM,
                identifier="",
                version="0.6.2",
            ),
        )
        with pytest.raises(ProxyHostingError, match="empty npm"):
            build_curator_proxy_server(listing)

    def test_build_proxy_docker_uses_stdio_transport_with_image_ref(self, monkeypatch):
        """A Docker-channel listing in proxy mode must construct a
        ``Client(StdioTransport(command='docker', args=[...,
        image_ref]))``. The image_ref combines image name + optional
        tag + optional digest via :func:`image_ref_for`. Resource
        flags (``--rm -i --memory=512m --pids-limit=128``) are
        present so each session gets a clean, bounded container."""
        import purecipher.curation.proxy_runtime as proxy_mod
        from fastmcp.client.transports.stdio import StdioTransport
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import build_curator_proxy_server
        from purecipher.curation.proxy_runtime import _build_client_factory

        # Pretend the registry host has docker installed so the
        # eager probe in _build_client_factory passes regardless of
        # the test environment. The test focuses on transport wiring.
        monkeypatch.setattr(proxy_mod.shutil, "which", lambda name: "/usr/bin/docker")

        digest = "sha256:" + "a" * 64
        listing = ToolListing(
            tool_name="docker-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.DOCKER,
                identifier="ghcr.io/example/mcp",
                version="v1",
                pinned_hash=digest,
            ),
        )
        proxy = build_curator_proxy_server(listing)
        assert proxy is not None

        factory = _build_client_factory(listing)
        client = factory()
        assert isinstance(client.transport, StdioTransport)
        assert client.transport.command == "docker"
        # ``run`` is implicit via the StdioTransport invocation pattern
        # — actually the args carry it explicitly because docker is a
        # multi-subcommand CLI. Confirm both the resource flags and
        # the image_ref are present.
        args = client.transport.args
        assert args[-1] == f"ghcr.io/example/mcp:v1@{digest}"
        assert "--rm" in args
        assert "-i" in args
        assert "--memory=512m" in args
        assert "--pids-limit=128" in args

    def test_build_proxy_docker_without_tag_or_digest_passes_bare_image(
        self, monkeypatch
    ):
        """A bare ``docker:nginx`` upstream (no tag, no digest) must
        still produce a working transport — image_ref reconstruction
        falls back to just the image name."""
        import purecipher.curation.proxy_runtime as proxy_mod
        from fastmcp.client.transports.stdio import StdioTransport
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation.proxy_runtime import _build_client_factory

        monkeypatch.setattr(proxy_mod.shutil, "which", lambda name: "/usr/bin/docker")

        listing = ToolListing(
            tool_name="docker-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.DOCKER,
                identifier="nginx",
            ),
        )
        factory = _build_client_factory(listing)
        client = factory()
        assert isinstance(client.transport, StdioTransport)
        assert client.transport.args[-1] == "nginx"

    def test_build_proxy_docker_refuses_empty_identifier(self, monkeypatch):
        import purecipher.curation.proxy_runtime as proxy_mod
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        monkeypatch.setattr(proxy_mod.shutil, "which", lambda name: "/usr/bin/docker")

        listing = ToolListing(
            tool_name="docker-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.DOCKER,
                identifier="",
            ),
        )
        with pytest.raises(ProxyHostingError, match="empty Docker"):
            build_curator_proxy_server(listing)

    def test_build_proxy_docker_surfaces_missing_docker_as_proxy_error(
        self, monkeypatch
    ):
        """If the registry host doesn't have ``docker`` on PATH, the
        eager probe in ``_build_client_factory`` must surface a
        structured :class:`ProxyHostingError` so the curator gets a
        clear "install docker" message instead of a confusing
        FileNotFoundError raised inside the per-session subprocess."""
        import purecipher.curation.proxy_runtime as proxy_mod
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        monkeypatch.setattr(proxy_mod.shutil, "which", lambda name: None)

        listing = ToolListing(
            tool_name="docker-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.DOCKER,
                identifier="ghcr.io/example/mcp",
                version="v1",
            ),
        )
        with pytest.raises(ProxyHostingError, match="docker"):
            build_curator_proxy_server(listing)

    def test_build_proxy_refuses_unsupported_channel(self):
        """Channels we don't have stdio support for (GITHUB, OTHER)
        must surface a structured ProxyHostingError instead of
        crashing later when the factory tries to construct a Client."""
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            ToolListing,
            UpstreamChannel,
            UpstreamRef,
        )
        from purecipher.curation import (
            ProxyHostingError,
            build_curator_proxy_server,
        )

        listing = ToolListing(
            tool_name="github-curated",
            attestation_kind=AttestationKind.CURATOR,
            hosting_mode=HostingMode.PROXY,
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.GITHUB,
                identifier="github.com/example/mcp",
            ),
        )
        with pytest.raises(ProxyHostingError, match="not supported"):
            build_curator_proxy_server(listing)

    def test_submit_proxy_listing_persists_observed_tools_in_metadata(self):
        """End-to-end: a /curate/submit with hosting_mode=proxy must
        store the introspection's tool_names in listing.metadata so the
        proxy runtime can build an AllowlistPolicy from them.

        Regression: pre-fix the proxy fell back to AllowAllPolicy
        because manifest.tags only carried marker tags, not the
        observed tool names.
        """
        from fastmcp.server.security.policy.policies.allowlist import (
            AllowlistPolicy,
        )
        from purecipher.curation import (
            HTTPIntrospector,
            Introspector,
            build_curator_proxy_server,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(
                http_introspector=HTTPIntrospector(
                    client_factory=lambda url: _FakeClient(
                        tools=[
                            _FakeTool("search_docs"),
                            _FakeTool("fetch_doc"),
                        ]
                    )
                )
            )
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "https://mcp.example.com/sse",
                    "tool_name": "proxy-with-allowlist",
                    "version": "1.0.0",
                    "hosting_mode": "proxy",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            listing_id = r.json()["listing"]["listing_id"]

        # Build the proxy server from the persisted listing.
        listing = registry._marketplace().get(listing_id)
        assert listing is not None
        assert listing.metadata["introspection"]["tool_names"] == [
            "search_docs",
            "fetch_doc",
        ]

        proxy = build_curator_proxy_server(listing)
        providers = proxy.security_context.policy_engine.providers
        allowlists = [p for p in providers if isinstance(p, AllowlistPolicy)]
        assert allowlists, (
            "proxy did not attach AllowlistPolicy; observed tools were "
            "not threaded from listing.metadata"
        )
        assert allowlists[0].allowed == {"search_docs", "fetch_doc"}

    def test_proxy_attaches_allowlist_policy_from_observed_tools(self):
        """The security config built for a proxy listing must include
        an AllowlistPolicy whose allowed set matches the listing's
        observed-tool tags. This is what gives the curator-vouched
        attestation runtime teeth at the gateway."""
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
        )
        from fastmcp.server.security.policy.policies.allowlist import (
            AllowlistPolicy,
        )
        from purecipher.curation.proxy_runtime import (
            _build_proxy_security_config,
        )

        listing = self._curated_listing(
            hosting_mode=HostingMode.PROXY,
            observed_tools=["fetch_url", "save_doc"],
        )
        config = _build_proxy_security_config(listing)
        assert config.policy is not None
        providers = config.policy.providers or []
        allowlists = [p for p in providers if isinstance(p, AllowlistPolicy)]
        assert allowlists, "AllowlistPolicy not attached"
        allowed = allowlists[0].allowed
        # The non-marker tags from the manifest become the allowed set.
        assert "fetch_url" in allowed
        assert "save_doc" in allowed
        # Marker tags ("curated", "third-party") are excluded.
        assert "curated" not in allowed
        assert "third-party" not in allowed

    def test_curator_proxy_router_404_on_unknown(self):
        """The router maps unknown listing_ids to 404."""
        from purecipher.curation import CuratorProxyRouter

        router = CuratorProxyRouter(listing_lookup=lambda _id: None)
        events: list[Any] = []

        async def receive() -> dict:
            return {"type": "http.disconnect"}

        async def send(msg: dict) -> None:
            events.append(msg)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/lst-missing/mcp/call",
            "headers": [],
        }
        import asyncio

        asyncio.run(router(scope, receive, send))
        starts = [e for e in events if e.get("type") == "http.response.start"]
        assert starts, "no response sent"
        assert starts[0]["status"] == 404

    def test_curator_proxy_router_409_on_catalog_listing(self):
        """A listing that exists but is hosting_mode=catalog must NOT
        be served from the proxy mount — return 409 Conflict so the
        client knows the install recipe should target the upstream
        directly instead."""
        from fastmcp.server.security.gateway.tool_marketplace import HostingMode
        from purecipher.curation import CuratorProxyRouter

        listing = self._curated_listing(hosting_mode=HostingMode.CATALOG)
        router = CuratorProxyRouter(
            listing_lookup=lambda lid: listing if lid == listing.listing_id else None,
        )
        events: list[Any] = []

        async def receive() -> dict:
            return {"type": "http.disconnect"}

        async def send(msg: dict) -> None:
            events.append(msg)

        scope = {
            "type": "http",
            "method": "POST",
            "path": f"/{listing.listing_id}/mcp/call",
            "headers": [],
        }
        import asyncio

        asyncio.run(router(scope, receive, send))
        starts = [e for e in events if e.get("type") == "http.response.start"]
        assert starts and starts[0]["status"] == 409


class TestSubmitProxyMode:
    """The /curate/submit endpoint accepts ``hosting_mode: "proxy"``
    for HTTP, PyPI, and npm upstreams. PyPI/npm channels are hosted
    per-session via uvx/npx subprocess transports — the submit
    handler no longer rejects them."""

    def _registry(self, fake_client):
        from purecipher.curation import HTTPIntrospector, Introspector

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(
                http_introspector=HTTPIntrospector(
                    client_factory=lambda url: fake_client
                )
            )
        )
        return registry

    def _registry_with_stdio(self, fake_client):
        """Build a registry with an Introspector that dispatches stdio
        channels (PyPI/npm) through a shared fake. The HTTP branch is
        also wired so a single helper covers all three channels.
        """
        from purecipher.curation import (
            HTTPIntrospector,
            Introspector,
            StdioIntrospector,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(
                http_introspector=HTTPIntrospector(
                    client_factory=lambda url: fake_client
                ),
                stdio_introspector=StdioIntrospector(
                    client_factory=lambda channel, identifier, version: fake_client
                ),
            )
        )
        return registry

    def test_submit_with_proxy_mode_publishes_proxy_listing(self):
        fake = _FakeClient(
            tools=[
                _FakeTool(
                    "fetch_url",
                    "Fetch a URL",
                    {"properties": {"url": {"type": "string"}}},
                )
            ]
        )
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "https://mcp.example.com/sse",
                    "tool_name": "proxy-tool",
                    "version": "1.0.0",
                    "hosting_mode": "proxy",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            listing = r.json()["listing"]
            assert listing["hosting_mode"] == "proxy"
            assert listing["attestation_kind"] == "curator"

    def test_submit_proxy_mode_accepted_for_pypi(self):
        """Regression: ``hosting_mode=proxy`` on a PyPI upstream must
        be accepted — the registry hosts a uvx-backed gateway in front
        of the package and persists a proxy listing."""
        from purecipher.curation.upstream import PyPIUpstreamFetcher

        orig = PyPIUpstreamFetcher.__init__

        def _patched(self, **kwargs):
            kwargs.setdefault(
                "http_client_factory",
                lambda: _FakeHttpClient(
                    _FakeHttpResponse(
                        json_payload={
                            "info": {
                                "name": "markitdown-mcp",
                                "version": "1.0.0",
                                "summary": "Markdown converter as MCP",
                                "license": "MIT",
                            },
                            "releases": {"1.0.0": []},
                        }
                    )
                ),
            )
            orig(self, **kwargs)

        PyPIUpstreamFetcher.__init__ = _patched  # type: ignore[assignment]
        try:
            fake = _FakeClient(
                tools=[
                    _FakeTool("convert_to_markdown", "Convert a doc", {}),
                ]
            )
            registry = self._registry_with_stdio(fake)
            with TestClient(registry.http_app()) as client:
                r = client.post(
                    "/registry/curate/submit",
                    json={
                        "upstream": "pypi:markitdown-mcp",
                        "tool_name": "markitdown-mcp",
                        "version": "1.0.0",
                        "hosting_mode": "proxy",
                        "selected_permissions": [],
                    },
                )
                assert r.status_code == 201, r.text
                listing = r.json()["listing"]
                assert listing["hosting_mode"] == "proxy"
                assert listing["attestation_kind"] == "curator"
                # The upstream channel is preserved on the listing so
                # the proxy runtime can dispatch the right transport.
                assert listing["upstream_ref"]["channel"] == "pypi"
        finally:
            PyPIUpstreamFetcher.__init__ = orig  # type: ignore[assignment]

    def test_submit_proxy_mode_accepted_for_npm(self):
        """Same regression test for the npm channel — proxy mode must
        be accepted for ``npm:`` upstreams."""
        from purecipher.curation.upstream import NpmUpstreamFetcher

        orig = NpmUpstreamFetcher.__init__

        def _patched(self, **kwargs):
            kwargs.setdefault(
                "http_client_factory",
                lambda: _FakeHttpClient(
                    _FakeHttpResponse(
                        json_payload={
                            "name": "@modelcontextprotocol/server-filesystem",
                            "dist-tags": {"latest": "0.6.2"},
                            "versions": {
                                "0.6.2": {
                                    "name": ("@modelcontextprotocol/server-filesystem"),
                                    "version": "0.6.2",
                                    "description": "Filesystem MCP",
                                    "license": "MIT",
                                    "dist": {"tarball": "x", "shasum": "x"},
                                }
                            },
                        }
                    )
                ),
            )
            orig(self, **kwargs)

        NpmUpstreamFetcher.__init__ = _patched  # type: ignore[assignment]
        try:
            fake = _FakeClient(tools=[_FakeTool("read_file", "Read a file", {})])
            registry = self._registry_with_stdio(fake)
            with TestClient(registry.http_app()) as client:
                r = client.post(
                    "/registry/curate/submit",
                    json={
                        "upstream": "npm:@modelcontextprotocol/server-filesystem",
                        "tool_name": "fs-server",
                        "version": "0.6.2",
                        "hosting_mode": "proxy",
                        "selected_permissions": [],
                    },
                )
                assert r.status_code == 201, r.text
                listing = r.json()["listing"]
                assert listing["hosting_mode"] == "proxy"
                assert listing["upstream_ref"]["channel"] == "npm"
        finally:
            NpmUpstreamFetcher.__init__ = orig  # type: ignore[assignment]

    def test_submit_with_proxy_mode_accepted_for_docker(self):
        """``hosting_mode=proxy`` on a Docker upstream must be
        accepted — the registry will mount a per-session
        ``docker run`` gateway in front of the image. The submit
        flow doesn't actually launch docker (the introspector here
        is faked) but the listing is persisted with the Docker
        channel preserved so the proxy runtime can dispatch later."""
        fake = _FakeClient(
            tools=[_FakeTool("convert", "Convert a doc", {})],
        )
        registry = self._registry_with_stdio(fake)
        digest = "sha256:" + "f" * 64
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": f"docker:ghcr.io/example/mcp:v1@{digest}",
                    "tool_name": "docker-mcp",
                    "version": "v1",
                    "hosting_mode": "proxy",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            listing = r.json()["listing"]
            assert listing["hosting_mode"] == "proxy"
            assert listing["attestation_kind"] == "curator"
            assert listing["upstream_ref"]["channel"] == "docker"
            assert listing["upstream_ref"]["identifier"] == "ghcr.io/example/mcp"
            assert listing["upstream_ref"]["pinned_hash"] == digest

    def test_submit_with_catalog_mode_accepted_for_docker(self):
        """Catalog-only Docker submissions also work. The install
        recipe should point at the curator-vouched image directly;
        the registry doesn't host a gateway."""
        fake = _FakeClient(
            tools=[_FakeTool("convert", "Convert a doc", {})],
        )
        registry = self._registry_with_stdio(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:nginx:1.27",
                    "tool_name": "nginx-mcp",
                    "version": "1.27",
                    "hosting_mode": "catalog",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            listing = r.json()["listing"]
            assert listing["hosting_mode"] == "catalog"
            assert listing["upstream_ref"]["channel"] == "docker"

    def test_submit_invalid_hosting_mode_rejected(self):
        registry = self._registry(_FakeClient())
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "https://mcp.example.com/sse",
                    "tool_name": "x",
                    "version": "1.0.0",
                    "hosting_mode": "garbage",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 400
            assert "hosting_mode" in r.json()["error"]


class TestLauncherProbe:
    """``check_introspection_launchers`` reports whether ``uvx`` / ``npx``
    / ``docker`` are reachable so operators can preflight at startup."""

    def test_probe_returns_keys_for_all_channels(self):
        from purecipher.curation import check_introspection_launchers

        result = check_introspection_launchers()
        assert set(result.keys()) == {"uvx", "npx", "docker"}
        # Each entry is either a resolved absolute path or None.
        for value in result.values():
            assert value is None or isinstance(value, str)

    def test_probe_logs_warning_when_launchers_missing(self, caplog, monkeypatch):
        import logging

        import purecipher.curation.introspector as introspector_mod
        from purecipher.curation import check_introspection_launchers

        # Force shutil.which to return None for all launchers.
        monkeypatch.setattr(introspector_mod.shutil, "which", lambda _name: None)
        with caplog.at_level(logging.WARNING):
            result = check_introspection_launchers()
        assert result == {"uvx": None, "npx": None, "docker": None}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        warning_text = " ".join(r.getMessage() for r in warnings)
        assert "uvx" in warning_text
        assert "npx" in warning_text
        assert "docker" in warning_text


class TestDefaultIntrospectorIsMultiChannel:
    """A registry constructed without a custom introspector must accept
    PyPI / npm channels — not just HTTP.

    Regression: pre-fix the default was the single-channel
    ``HTTPIntrospector``, so the live wizard rejected ``pypi:...``
    submissions with "This iteration supports HTTP upstreams only".
    Tests passed because they always installed an
    :class:`Introspector` dispatcher via
    :meth:`set_curation_introspector`.
    """

    def test_default_curation_introspector_is_multi_channel(self):
        """The default introspector dispatches by channel rather than
        forcing HTTP."""
        from purecipher.curation import Introspector

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        # Touch the lazy initializer.
        introspector = registry._curation_introspector()
        assert isinstance(introspector, Introspector), (
            f"default introspector is {type(introspector).__name__!r}; "
            "must be the multi-channel ``Introspector`` dispatcher so "
            "PyPI/npm refs route to StdioIntrospector."
        )

    def test_pypi_channel_does_not_hit_http_only_error(self):
        """An attempt to introspect a PyPI ref on a default registry
        must NOT return the HTTP-only error message. The failure mode
        must be the stdio path's failure, not the dispatcher rejecting
        the channel up front.

        We patch :class:`StdioIntrospector` to raise
        :class:`IntrospectionError` immediately so the test doesn't
        spawn a real uvx subprocess (which makes the test brittle to
        host-side timing and network availability).
        """
        from purecipher.curation.introspector import (
            IntrospectionError,
            StdioIntrospector,
        )
        from purecipher.curation.upstream import PyPIUpstreamFetcher

        # Patch PyPI metadata so the resolve step doesn't hit the
        # network during the test.
        orig_fetcher = PyPIUpstreamFetcher.__init__

        def _patched_fetcher(self, **kwargs):
            kwargs.setdefault(
                "http_client_factory",
                lambda: _FakeHttpClient(
                    _FakeHttpResponse(
                        json_payload={
                            "info": {
                                "name": "fake",
                                "version": "1.0.0",
                                "summary": "",
                                "license": "",
                            },
                            "releases": {"1.0.0": []},
                        }
                    )
                ),
            )
            orig_fetcher(self, **kwargs)

        # Stub the stdio introspector so we don't spawn uvx — the
        # test only needs to confirm the *dispatcher* routed PyPI to
        # the stdio path, not what stdio does next.
        orig_introspect = StdioIntrospector.introspect

        async def _fake_introspect(self, upstream_ref):
            raise IntrospectionError("stub stdio introspection (test)")

        PyPIUpstreamFetcher.__init__ = _patched_fetcher  # type: ignore[assignment]
        StdioIntrospector.introspect = _fake_introspect  # type: ignore[assignment]
        try:
            registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
            with TestClient(registry.http_app()) as client:
                r = client.post(
                    "/registry/curate/introspect",
                    json={"upstream": "pypi:fake"},
                )
                # Whatever the status, the response error MUST NOT
                # contain the HTTP-only rejection message — that
                # would mean the dispatcher routed PyPI to
                # HTTPIntrospector instead of StdioIntrospector.
                error_msg = r.json().get("error", "")
                assert "supports HTTP upstreams only" not in error_msg, (
                    f"PyPI refs are still being routed to the HTTP-only "
                    f"introspector. Response: {r.status_code} {error_msg!r}"
                )
                # Positive signal that we *did* reach the stdio path —
                # the stub's marker phrase is in the error.
                assert "stub stdio introspection" in error_msg, (
                    f"PyPI ref didn't reach the stub StdioIntrospector. "
                    f"Response: {r.status_code} {error_msg!r}"
                )
        finally:
            PyPIUpstreamFetcher.__init__ = orig_fetcher  # type: ignore[assignment]
            StdioIntrospector.introspect = orig_introspect  # type: ignore[assignment]


class TestCuratorCertificationCap:
    """Curator-attested listings must cap at the BASIC certification
    tier. STANDARD / STRICT imply source-level guarantees that the
    registry can't make for a third-party server it only observed
    over the protocol.

    Regression for the issue where a Context7 curator submission
    rendered with a ``strict`` certification chip on the catalog —
    misleading trust signal.
    """

    def _registry(self, fake_client):
        from purecipher.curation import HTTPIntrospector, Introspector

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(
                http_introspector=HTTPIntrospector(
                    client_factory=lambda url: fake_client
                )
            )
        )
        return registry

    def test_curator_submission_caps_at_basic(self):
        from fastmcp.server.security.certification.attestation import (
            CertificationLevel,
        )

        # A rich manifest that would normally qualify for STANDARD or
        # higher: multiple permissions declared, complete data flows.
        fake = _FakeClient(
            tools=[
                _FakeTool(
                    "fetch_url",
                    "Fetch a URL",
                    {"properties": {"url": {"type": "string"}}},
                ),
                _FakeTool(
                    "save_doc",
                    "Save a document",
                    {"properties": {"path": {"type": "string"}}},
                ),
            ]
        )
        registry = self._registry(fake)
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "https://mcp.example.com/sse",
                    "tool_name": "well-described",
                    "version": "1.0.0",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            listing = r.json()["listing"]

        # Whatever the validator's heuristics qualified for, the
        # publish certification level must NOT exceed BASIC.
        capped_levels = {
            CertificationLevel.UNCERTIFIED.value,
            CertificationLevel.SELF_ATTESTED.value,
            CertificationLevel.BASIC.value,
        }
        assert listing["certification_level"] in capped_levels, (
            f"curator listing got {listing['certification_level']!r}, expected ≤ basic"
        )

    def test_curator_cap_overrides_explicit_higher_request(self):
        """Direct ``submit_tool(attestation_kind=CURATOR,
        requested_level=STRICT)`` must still cap at BASIC. Defends
        against a curator UI / CLI accidentally bypassing the cap."""
        from fastmcp.server.security.certification.attestation import (
            CertificationLevel,
        )
        from fastmcp.server.security.certification.manifest import (
            PermissionScope,
            SecurityManifest,
        )
        from fastmcp.server.security.gateway.tool_marketplace import (
            HostingMode,
            UpstreamChannel,
            UpstreamRef,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        manifest = SecurityManifest(
            tool_name="curator-cap-test",
            version="1.0.0",
            author="@curator",
            description="Curator vouches",
            permissions={
                PermissionScope.NETWORK_ACCESS,
                PermissionScope.CALL_TOOL,
            },
            tags={"curated"},
        )
        result = registry.submit_tool(
            manifest,
            display_name="Curator Cap Test",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.STRICT,  # caller asks for STRICT
            attestation_kind=AttestationKind.CURATOR,
            curator_id="@curator",
            upstream_ref=UpstreamRef(
                channel=UpstreamChannel.HTTP,
                identifier="https://mcp.example.com/sse",
            ),
            hosting_mode=HostingMode.CATALOG,
        )
        assert result.accepted, result.reason
        assert result.attestation is not None
        # The pipeline picked the smaller of (manifest qualification,
        # requested_level). Our requested_level was capped to BASIC
        # before the pipeline saw it, so the result must be ≤ BASIC.
        from fastmcp.server.security.certification.attestation import (
            CertificationLevel as _CL,
        )

        assert _level_index_helper(
            result.attestation.certification_level
        ) <= _level_index_helper(_CL.BASIC)

    def test_author_submission_unchanged(self):
        """The cap only applies to curator submissions — author
        submissions still hit whatever tier their manifest qualifies
        for."""
        from fastmcp.server.security.certification.attestation import (
            CertificationLevel,
        )

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        result = registry.submit_tool(
            _manifest(),
            display_name="Author Tool",
            categories={ToolCategory.NETWORK},
            requested_level=CertificationLevel.STANDARD,
            # No attestation_kind override — defaults to AUTHOR.
        )
        assert result.accepted, result.reason
        # Author can reach STANDARD.
        assert _level_index_helper(
            result.attestation.certification_level
        ) >= _level_index_helper(CertificationLevel.BASIC)


def _level_index_helper(level):
    from fastmcp.server.security.certification.attestation import (
        CertificationLevel,
    )

    return list(CertificationLevel).index(level)


def _manifest():
    """Minimal valid manifest used in author-path tests."""
    from fastmcp.server.security.certification.manifest import (
        PermissionScope,
        SecurityManifest,
    )

    return SecurityManifest(
        tool_name="author-tool",
        version="1.0.0",
        author="acme",
        description="Author tool",
        permissions={
            PermissionScope.NETWORK_ACCESS,
            PermissionScope.CALL_TOOL,
        },
    )


class TestEmptyUpstreamRejected:
    """An upstream with zero tools / resources / prompts is meaningless
    to vouch for — the submit endpoint should refuse with 422."""

    def test_empty_upstream_returns_422(self):
        from purecipher import PureCipherRegistry as _Registry
        from purecipher.curation.introspector import HTTPIntrospector as _Intro

        registry = _Registry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            _Intro(client_factory=lambda _url: _FakeClient())
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream_url": "https://mcp.example.com/sse",
                    "tool_name": "empty",
                    "version": "1.0.0",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 422
            assert "zero tools" in r.json()["error"].lower()


# ── Iter 14.8 — token-on-introspect ───────────────────────────────


class TestValidateIntrospectEnv:
    """Iter 14.8 — input validation for the curator-supplied env dict."""

    def test_none_returns_none(self):
        from purecipher.curation import validate_introspect_env

        assert validate_introspect_env(None) is None

    def test_empty_dict_returns_none(self):
        from purecipher.curation import validate_introspect_env

        assert validate_introspect_env({}) is None

    def test_valid_pair_round_trips(self):
        from purecipher.curation import validate_introspect_env

        out = validate_introspect_env({"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_abc"})
        assert out == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_abc"}

    def test_lowercase_key_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        with pytest.raises(CredentialValidationError, match="Invalid credential key"):
            validate_introspect_env({"github_token": "x"})

    def test_key_with_dash_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        with pytest.raises(CredentialValidationError, match="Invalid credential key"):
            validate_introspect_env({"GITHUB-TOKEN": "x"})

    def test_reserved_key_rejected(self):
        """Keys that would let a curator hijack the launcher itself
        (PATH, LD_PRELOAD, etc.) must be refused — even if otherwise
        well-formed."""
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        for key in ("PATH", "LD_PRELOAD", "PYTHONPATH", "NODE_OPTIONS", "HOME"):
            with pytest.raises(CredentialValidationError, match="cannot be set"):
                validate_introspect_env({key: "anything"})

    def test_empty_value_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        with pytest.raises(CredentialValidationError, match="empty"):
            validate_introspect_env({"GITHUB_PERSONAL_ACCESS_TOKEN": ""})

    def test_oversized_value_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        too_long = "x" * 5000
        with pytest.raises(CredentialValidationError, match="too long"):
            validate_introspect_env({"GITHUB_PERSONAL_ACCESS_TOKEN": too_long})

    def test_too_many_keys_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        big = {f"KEY_{i}": "v" for i in range(64)}
        with pytest.raises(CredentialValidationError, match="Too many"):
            validate_introspect_env(big)

    def test_non_string_value_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        with pytest.raises(CredentialValidationError, match="must be a string"):
            validate_introspect_env({"GITHUB_TOKEN": 123})  # type: ignore[dict-item]

    def test_not_a_dict_rejected(self):
        from purecipher.curation import (
            CredentialValidationError,
            validate_introspect_env,
        )

        with pytest.raises(CredentialValidationError, match="JSON object"):
            validate_introspect_env(["GITHUB_TOKEN=ghp"])  # type: ignore[arg-type]


class TestStdioIntrospectorEnv:
    """Iter 14.8 — env dict threads into the spawn for stdio channels."""

    def test_factory_receives_env_kwarg_for_pypi(self):
        """When env is provided, _build_client passes it as a kwarg to
        the test factory so the spawn can inject it."""
        import asyncio

        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        captured: list = []

        def factory(channel, identifier, version, *, env=None):
            captured.append((channel, identifier, version, env))
            return _FakeClient(tools=[_FakeTool("ok")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_pypi_upstream("pypi:markitdown-mcp@1.2.3")
        result = asyncio.run(
            introspector.introspect(
                ref,
                env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_secret"},
            )
        )
        assert result.tool_count == 1
        assert len(captured) == 1
        env_passed = captured[0][3]
        assert env_passed == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_secret"}

    def test_factory_receives_no_env_when_none_passed(self):
        """No env kwarg should arrive as ``None`` — preserving the
        original spawn semantics for upstreams that don't need creds."""
        import asyncio

        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        captured: list = []

        def factory(channel, identifier, version, *, env=None):
            captured.append(env)
            return _FakeClient(tools=[_FakeTool("ok")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_pypi_upstream("pypi:markitdown-mcp@1.2.3")
        asyncio.run(introspector.introspect(ref))
        assert captured == [None]

    def test_legacy_3arg_factory_still_works(self):
        """Tests written before Iter 14.8 use a 3-positional factory.
        The introspector must keep accepting them so existing test
        suites don't break."""
        import asyncio

        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        def factory(channel, identifier, version):
            return _FakeClient(tools=[_FakeTool("ok")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_pypi_upstream("pypi:p@1.0")
        # No env — falls back to 3-arg call.
        result = asyncio.run(introspector.introspect(ref))
        assert result.tool_count == 1

    def test_default_pypi_transport_carries_env_vars(self):
        """Without a factory override, _build_client constructs a real
        UvxStdioTransport — confirm it carries the env_vars dict."""
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        introspector = StdioIntrospector()
        ref = parse_pypi_upstream("pypi:markitdown-mcp@1.2.3")
        client = introspector._build_client(
            ref, env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp"}
        )
        # UvxStdioTransport stores env_vars directly; the env dict
        # ends up on the spawn's ``env`` (after merging defaults).
        env = getattr(client.transport, "env", None)
        assert env is not None
        assert env.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "ghp"

    def test_default_npm_transport_carries_env_vars(self):
        # NpxStdioTransport.__init__ requires ``npx`` on PATH — skip if
        # this CI box doesn't have Node installed. The env-passing
        # behavior is identical to UvxStdioTransport (covered above) so
        # we don't lose meaningful coverage when this skips.
        import shutil

        if shutil.which("npx") is None:
            pytest.skip("npx not on PATH in this environment")
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_npm_upstream

        introspector = StdioIntrospector()
        ref = parse_npm_upstream("npm:@modelcontextprotocol/server-github@1.0")
        client = introspector._build_client(
            ref, env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp"}
        )
        env = getattr(client.transport, "env", None)
        assert env is not None
        assert env.get("GITHUB_PERSONAL_ACCESS_TOKEN") == "ghp"

    def test_default_docker_transport_passes_e_flags_without_values(self):
        """For Docker, env values must NOT appear in argv (they'd show
        in ps); only ``-e KEY`` flags (without values). The actual
        VALUE goes onto the docker CLI's environment, which Docker
        forwards into the container."""
        from fastmcp.client.transports.stdio import StdioTransport
        from purecipher.curation import StdioIntrospector, parse_docker_upstream

        introspector = StdioIntrospector()
        ref = parse_docker_upstream("docker:ghcr.io/example/mcp:v1")
        client = introspector._build_client(
            ref,
            env={"STRIPE_SECRET_KEY": "sk_test_xxxxxx"},
        )
        assert isinstance(client.transport, StdioTransport)
        args = list(client.transport.args)
        # ``-e STRIPE_SECRET_KEY`` must be present without a value
        # bound to it on argv. Specifically the next token after ``-e``
        # is the bare key.
        assert "-e" in args
        e_index = args.index("-e")
        assert args[e_index + 1] == "STRIPE_SECRET_KEY"
        # The secret value must NOT appear anywhere in argv.
        for arg in args:
            assert "sk_test_xxxxxx" not in arg
        # But it does land on the CLI's env so Docker can forward it
        # into the container.
        env = getattr(client.transport, "env", None)
        assert env is not None
        assert env.get("STRIPE_SECRET_KEY") == "sk_test_xxxxxx"

    def test_http_introspector_rejects_env(self):
        """Iter 14.8 doesn't yet support env on HTTP — passing one
        must raise IntrospectionError, not silently drop it (which
        would leave the curator believing the value was sent)."""
        import asyncio

        from purecipher.curation import HTTPIntrospector

        introspector = HTTPIntrospector(
            client_factory=lambda url: _FakeClient(tools=[_FakeTool("a")])
        )
        ref = parse_http_upstream("https://mcp.example.com/sse")
        with pytest.raises(IntrospectionError, match="HTTP MCP servers"):
            asyncio.run(introspector.introspect(ref, env={"X": "y"}))

    def test_introspect_does_not_log_env_values(self, caplog):
        """When env is provided, the introspector logs the *keys* but
        never the values. This is the redaction contract that lets
        operators see what credentials were passed without exposing
        them in support logs."""
        import asyncio
        import logging

        from purecipher.curation import StdioIntrospector
        from purecipher.curation.upstream import parse_pypi_upstream

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        introspector = StdioIntrospector(client_factory=factory)
        ref = parse_pypi_upstream("pypi:p@1.0")
        secret_value = "ghp_super_secret_value_123"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                introspector.introspect(
                    ref,
                    env={"GITHUB_PERSONAL_ACCESS_TOKEN": secret_value},
                )
            )
        joined = "\n".join(rec.getMessage() for rec in caplog.records)
        # The key is OK to log (operators want to see it).
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in joined
        # The VALUE must never appear.
        assert secret_value not in joined


class TestCurateIntrospectRouteEnv:
    """Iter 14.8 — the registry route accepts ``env`` and passes it
    through to the introspector. Validation errors map to 400."""

    def test_route_passes_env_to_introspector(self):
        """The wizard's POST body's ``env`` field must reach the
        introspector verbatim. We use a stdio ref because HTTP
        upstreams don't accept env."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        captured: dict = {}

        def factory(channel, identifier, version, *, env=None):
            captured["env"] = env
            captured["channel"] = channel
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={
                    "upstream": "pypi:markitdown-mcp@1.2.3",
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_abc"},
                },
            )
            assert r.status_code == 200, r.text
        assert captured["channel"].value == "pypi"
        assert captured["env"] == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_abc"}

    def test_route_omits_env_field_from_response(self):
        """The introspect response must never echo the env dict back —
        otherwise we'd be passing tokens through additional layers
        (browser cache, network logs) needlessly."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={
                    "upstream": "pypi:markitdown-mcp@1.2.3",
                    "env": {"SECRET_API_KEY": "value-that-must-not-leak"},
                },
            )
            assert r.status_code == 200, r.text
            body_text = r.text
            assert "value-that-must-not-leak" not in body_text
            assert "SECRET_API_KEY" not in body_text

    def test_route_400_on_invalid_env_key(self):
        """Validation errors come back as 400 (curator's bad input),
        not 502 (upstream unreachable)."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={
                    "upstream": "pypi:markitdown-mcp@1.2.3",
                    "env": {"github-token": "ghp_abc"},  # lowercase + dash
                },
            )
            assert r.status_code == 400
            assert "Invalid credential key" in r.json()["error"]

    def test_route_400_on_reserved_env_key(self):
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={
                    "upstream": "pypi:markitdown-mcp@1.2.3",
                    "env": {"PATH": "/tmp/evil"},
                },
            )
            assert r.status_code == 400
            assert "cannot be set" in r.json()["error"]

    def test_route_no_env_field_works_unchanged(self):
        """Iter 14.8 must be backward-compatible: omitting ``env``
        works exactly like before."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        captured: dict = {}

        def factory(channel, identifier, version, *, env=None):
            captured["env"] = env
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/introspect",
                json={"upstream": "pypi:markitdown-mcp@1.2.3"},
            )
            assert r.status_code == 200, r.text
        assert captured["env"] is None


class TestCurateSubmitRouteEnv:
    """Iter 14.8.1 — submit handler accepts ``env`` and threads it
    into the re-introspect step.

    Without this, token-required upstreams (Atlassian, Stripe, Slack,
    GitHub) hit the empty-surface 422 at submit time even after a
    successful introspect at Step 2: the submit-time re-introspect
    can't see any tools without the same env.
    """

    def test_submit_accepts_env_and_succeeds_for_token_required(self):
        """Submit-time re-introspect uses the supplied env and the
        listing is created with the full observed surface."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        envs_seen: list = []

        def factory(channel, identifier, version, *, env=None):
            envs_seen.append(env)
            # Same fake client either way — the test asserts on env
            # capture, not on differential behavior. (In real life,
            # mcp-atlassian returns 0 tools without env and 49 with;
            # the fake stand-in just records what arrived.)
            return _FakeClient(tools=[_FakeTool("jira_get_issue")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "pypi:mcp-atlassian",
                    "tool_name": "atlassian-test",
                    "version": "1.0.0",
                    "env": {
                        "JIRA_URL": "https://x.atlassian.net",
                        "JIRA_USERNAME": "u@example.com",
                        "JIRA_API_TOKEN": "token-must-not-leak-anywhere",
                    },
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
        # Submit's re-introspect must have received the env, not None.
        assert envs_seen, "submit handler did not call introspect"
        assert envs_seen[-1] == {
            "JIRA_URL": "https://x.atlassian.net",
            "JIRA_USERNAME": "u@example.com",
            "JIRA_API_TOKEN": "token-must-not-leak-anywhere",
        }

    def test_submit_response_does_not_echo_env_values(self):
        """The submit response carries the listing summary back to
        the wizard. Token values must never appear in that payload."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        SECRET = "ghp_should_never_appear_in_response_xyz"
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "pypi:pkg@1.0",
                    "tool_name": "pkg",
                    "version": "1.0.0",
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": SECRET},
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
            assert SECRET not in r.text
            assert "GITHUB_PERSONAL_ACCESS_TOKEN" not in r.text

    def test_submit_400_on_invalid_env_key(self):
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "pypi:pkg@1.0",
                    "tool_name": "pkg",
                    "version": "1.0.0",
                    "env": {"github-token": "ghp"},  # lowercase + dash
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 400
            assert "Invalid credential key" in r.json()["error"]

    def test_submit_400_on_reserved_env_key(self):
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool("ok")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "pypi:pkg@1.0",
                    "tool_name": "pkg",
                    "version": "1.0.0",
                    "env": {"LD_PRELOAD": "/tmp/evil.so"},
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 400
            assert "cannot be set" in r.json()["error"]

    def test_submit_no_env_field_works_unchanged(self):
        """Backward-compat: submits without ``env`` still work for
        upstreams that don't need credentials (filesystem, fetch, etc.)."""
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        envs_seen: list = []

        def factory(channel, identifier, version, *, env=None):
            envs_seen.append(env)
            return _FakeClient(tools=[_FakeTool("read_file")])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "pypi:pkg@1.0",
                    "tool_name": "pkg",
                    "version": "1.0.0",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text
        # Submit's re-introspect was called with env=None (the
        # backward-compat path), not the empty dict.
        assert envs_seen[-1] is None


class TestCurateSubmitToolSelection:
    """Iter 14.10 — submit handler honors ``selected_tools``.

    The curator vouches for a subset of the observed tool surface.
    Same confirm-or-remove contract as ``selected_permissions``:
    requested names not present in the introspection are dropped
    rather than smuggled into the manifest.
    """

    def _registry_with_tools(self, *names: str):
        from purecipher import PureCipherRegistry
        from purecipher.curation import StdioIntrospector
        from purecipher.curation.introspector import Introspector

        def factory(channel, identifier, version, *, env=None):
            return _FakeClient(tools=[_FakeTool(n) for n in names])

        registry = PureCipherRegistry(signing_secret=TEST_SIGNING_SECRET)
        registry.set_curation_introspector(
            Introspector(stdio_introspector=StdioIntrospector(client_factory=factory))
        )
        return registry

    def test_selected_tools_subset_reflected_in_listing(self):
        """The listing's stored metadata reports the vouched subset
        as ``tool_names`` (used by the AllowlistPolicy in proxy mode)
        and the full observed surface separately."""
        registry = self._registry_with_tools(
            "jira_get_issue",
            "jira_create_issue",
            "jira_delete_issue",
            "jira_search",
        )
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "jira-readonly",
                    "version": "1.0.0",
                    "selected_permissions": [],
                    # Curator vouches only for read-shaped tools —
                    # explicitly drops ``jira_create_issue`` and
                    # ``jira_delete_issue`` so the proxy policy
                    # blocks mutations.
                    "selected_tools": ["jira_get_issue", "jira_search"],
                },
            )
            assert r.status_code == 201, r.text

        listing = registry._marketplace().get_by_name("jira-readonly")
        assert listing is not None
        intro_meta = listing.metadata["introspection"]
        # ``tool_names`` is the AllowlistPolicy source — must be the
        # vouched subset.
        assert sorted(intro_meta["tool_names"]) == sorted(
            ["jira_get_issue", "jira_search"]
        )
        # ``observed_tool_names`` preserves the full pre-filter surface
        # for transparency (admins can see what got deselected).
        assert sorted(intro_meta["observed_tool_names"]) == sorted(
            [
                "jira_get_issue",
                "jira_create_issue",
                "jira_delete_issue",
                "jira_search",
            ]
        )
        assert intro_meta["vouched_tool_count"] == 2

    def test_unobserved_tool_name_silently_dropped(self):
        """Same confirm-or-remove contract as permissions: a curator
        cannot smuggle a tool that wasn't in the introspection
        result (same defence as ``test_submit_curator_cannot_smuggle_unobserved_scope``)."""
        registry = self._registry_with_tools("jira_get_issue", "jira_search")
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "smuggle-test",
                    "version": "1.0.0",
                    "selected_permissions": [],
                    # ``forge_audit_log`` was never observed — must
                    # not appear in the listing.
                    "selected_tools": [
                        "jira_get_issue",
                        "forge_audit_log",
                    ],
                },
            )
            assert r.status_code == 201, r.text

        listing = registry._marketplace().get_by_name("smuggle-test")
        assert listing is not None
        tool_names = listing.metadata["introspection"]["tool_names"]
        assert "forge_audit_log" not in tool_names
        assert tool_names == ["jira_get_issue"]

    def test_selected_tools_omitted_defaults_to_all(self):
        """Backward-compat: pre-Iter 14.10 wizards don't send
        ``selected_tools`` at all. The submit handler must default
        to vouching for every observed tool in that case."""
        registry = self._registry_with_tools("a", "b", "c")
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "all-vouched",
                    "version": "1.0.0",
                    "selected_permissions": [],
                },
            )
            assert r.status_code == 201, r.text

        listing = registry._marketplace().get_by_name("all-vouched")
        assert listing is not None
        intro_meta = listing.metadata["introspection"]
        assert sorted(intro_meta["tool_names"]) == ["a", "b", "c"]
        assert intro_meta["vouched_tool_count"] == 3

    def test_zero_selected_tools_returns_422(self):
        """A curator-attested listing must vouch for at least one
        tool. Zero selection produces a clear 422 rather than
        silently minting an empty attestation."""
        registry = self._registry_with_tools("a", "b")
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "empty-vouch",
                    "version": "1.0.0",
                    "selected_permissions": [],
                    "selected_tools": [],
                },
            )
            assert r.status_code == 422
            assert "at least one tool" in r.json()["error"].lower()

    def test_selected_tools_must_be_list(self):
        """Type-check the submit body so a malformed wizard request
        fails fast with 400, not 500."""
        registry = self._registry_with_tools("a", "b")
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "bad-shape",
                    "version": "1.0.0",
                    "selected_permissions": [],
                    "selected_tools": "a,b",  # string, not list
                },
            )
            assert r.status_code == 400
            assert "list" in r.json()["error"].lower()

    def test_selected_tools_preserves_observation_order(self):
        """Tool order in the stored metadata matches the order the
        upstream returned, not the order the curator clicked. This
        keeps listings deterministic across re-introspections."""
        registry = self._registry_with_tools("alpha", "beta", "gamma", "delta")
        with TestClient(registry.http_app()) as client:
            r = client.post(
                "/registry/curate/submit",
                json={
                    "upstream": "docker:ghcr.io/example/mcp:v1",
                    "tool_name": "ordering",
                    "version": "1.0.0",
                    "selected_permissions": [],
                    # Submitted out-of-order.
                    "selected_tools": ["delta", "alpha", "gamma"],
                },
            )
            assert r.status_code == 201, r.text

        listing = registry._marketplace().get_by_name("ordering")
        assert listing is not None
        # Stored order matches introspection order, not submit order.
        assert listing.metadata["introspection"]["tool_names"] == [
            "alpha",
            "gamma",
            "delta",
        ]
