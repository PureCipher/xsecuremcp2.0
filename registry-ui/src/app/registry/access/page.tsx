"use server";

import Link from "next/link";

import {
  getPublisherProfile,
  listPublishers,
  type PublisherSummary,
  type RegistryToolListing,
  verifyTool,
  getToolDetail,
} from "@/lib/registryClient";
import { JsonViewer, KeyValuePanel, EmptyState } from "@/components/security";

function getStringParam(param: string | string[] | undefined): string | undefined {
  if (typeof param !== "string") return undefined;
  return param.trim() ? param : undefined;
}

export default async function AccessStudioPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  const clientId = getStringParam(searchParams?.clientId);
  const serverIdParam = getStringParam(searchParams?.serverId);
  const toolName = getStringParam(searchParams?.toolName);

  const serverId = serverIdParam ? decodeURIComponent(serverIdParam) : undefined;

  const profile = serverId ? await getPublisherProfile(serverId) : null;
  const listings: RegistryToolListing[] = profile?.listings ?? [];

  let error: string | null = null;
  let toolDetail: RegistryToolListing | null = null;
  let verification:
    | Awaited<ReturnType<typeof verifyTool>>
    | null = null;

  if (serverId && toolName) {
    try {
      const detail = await getToolDetail(toolName);
      if (detail && "tool_name" in detail) {
        toolDetail = detail as RegistryToolListing;
      }

      verification = await verifyTool(toolName);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load tool verification";
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
          Access Studio
        </p>
        <h1 className="text-2xl font-semibold text-[--app-fg]">Simulate MCP tool eligibility</h1>
        <p className="max-w-2xl text-[11px] text-[--app-muted]">
          MCP-only phase: server tool inventory + registry certification/verification preview. Contract/ledger/consent enforcement comes next.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Link
          href="/registry/clients"
          className="ml-auto text-[11px] font-semibold text-[--app-accent] hover:text-[--app-fg]"
        >
          ← Clients
        </Link>
      </div>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <h2 className="mb-4 text-sm font-semibold text-[--app-fg]">MCP simulation query</h2>
        <form method="GET" className="grid gap-4 md:grid-cols-2">
          <label className="space-y-1">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
              Client ID
            </span>
            <input
              name="clientId"
              defaultValue={clientId ?? ""}
              placeholder="e.g., client-123"
              className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
            />
          </label>

          <label className="space-y-1">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
              MCP Server
            </span>
            <select
              name="serverId"
              defaultValue={serverIdParam ?? ""}
              className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
            >
              <option value="">Select a server (publisher)</option>
              {publishers.map((p) => (
                <option key={p.publisher_id} value={p.publisher_id}>
                  {p.display_name ?? p.publisher_id}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 md:col-span-2">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
              Tool (optional)
            </span>
            <select
              name="toolName"
              defaultValue={toolName ?? ""}
              className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              disabled={!serverId || listings.length === 0}
            >
              <option value="">Use server-level resource</option>
              {listings.map((l) => (
                <option key={l.tool_name} value={l.tool_name}>
                  {l.display_name ?? l.tool_name}
                </option>
              ))}
            </select>
          </label>

          <div className="md:col-span-2 flex flex-wrap items-center justify-between gap-2">
            <button
              type="submit"
              className="rounded-full bg-[--app-accent] px-5 py-2 text-xs font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90"
            >
              Run simulation
            </button>

            <p className="text-[11px] text-[--app-muted]">
              Server:{" "}
              <span className="font-semibold text-[--app-fg]">{serverId ? serverId : "—"}</span>
              {toolName ? (
                <>
                  {" "}
                  · Tool: <span className="font-semibold text-[--app-fg]">{toolName}</span>
                </>
              ) : null}
            </p>
          </div>
        </form>
      </section>

      {error ? (
        <div className="rounded-3xl border border-red-500/40 bg-red-500/10 p-4 ring-1 ring-red-700/60">
          <p className="text-[12px] text-red-200">Simulation failed: {error}</p>
        </div>
      ) : null}

      {serverId ? (
        <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h2 className="mb-4 text-sm font-semibold text-[--app-fg]">Server tool inventory</h2>

          {profile?.error ? (
            <EmptyState
              title="Server profile unavailable"
              message="The registry backend returned an error for this server profile."
            />
          ) : (
            <div className="space-y-4">
              <KeyValuePanel
                title="Server snapshot (MCP-only)"
                entries={[
                  { label: "server_id", value: serverId },
                  {
                    label: "tool_count",
                    value: String(profile?.summary?.tool_count ?? listings.length),
                  },
                  {
                    label: "client_id (optional)",
                    value: clientId ?? "—",
                  },
                ]}
              />

              <div className="grid gap-4 sm:grid-cols-2">
                {listings.length === 0 ? (
                  <EmptyState
                    title="No tool listings"
                    message="This server profile currently has no tool listings in the registry."
                  />
                ) : (
                  listings.slice(0, 8).map((tool) => (
                    <div
                      key={tool.tool_name}
                      className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <h3 className="text-sm font-semibold text-[--app-fg]">
                          {tool.display_name ?? tool.tool_name}
                        </h3>
                        <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
                          {tool.certification_level ?? "unlisted"}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-[11px] text-[--app-muted]">
                        {tool.description ?? "No description provided."}
                      </p>
                    </div>
                  ))
                )}
              </div>

              <div className="mt-2">
                <p className="text-[11px] text-[--app-muted]">
                  Showing up to 8 tools for performance. Use the Tool dropdown to inspect certification details.
                </p>
              </div>
            </div>
          )}
        </section>
      ) : (
        <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <EmptyState
            title="Pick a server to simulate"
            message="Choose a server (publisher) and optionally a tool, then click “Run simulation”."
          />
        </section>
      )}

      {toolName ? (
        <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h2 className="mb-4 text-sm font-semibold text-[--app-fg]">Tool verification (registry)</h2>
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.95fr]">
            <KeyValuePanel
              title="MCP tool eligibility preview"
              entries={[
                { label: "tool_name", value: toolName },
                {
                  label: "listed_in_selected_server",
                  value: listings.some((l) => l.tool_name === toolName) ? "true" : "false",
                },
                {
                  label: "certification_level",
                  value:
                    (toolDetail?.certification_level ?? listings.find((l) => l.tool_name === toolName)?.certification_level) ??
                    "—",
                },
              ]}
            />

            <div className="space-y-4">
              <KeyValuePanel
                title="Verification details"
                entries={[
                  {
                    label: "signature_valid",
                    value: verification?.verification?.signature_valid ? "true" : "false",
                  },
                  {
                    label: "manifest_match",
                    value: verification?.verification?.manifest_match ? "true" : "false",
                  },
                  {
                    label: "issues",
                    value: verification?.verification?.issues?.length
                      ? verification.verification.issues.join("; ")
                      : "—",
                  },
                ]}
              />
              {verification ? (
                <JsonViewer data={verification} title="Raw tool verification response" defaultExpanded={false} />
              ) : (
                <EmptyState title="No verification loaded" message="Run simulation again to fetch verification." />
              )}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}

