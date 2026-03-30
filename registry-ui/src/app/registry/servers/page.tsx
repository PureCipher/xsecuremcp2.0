import Link from "next/link";

import { EmptyState } from "@/components/security";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

export default async function ServersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
          MCP Servers
        </p>
        <h1 className="text-2xl font-semibold text-[--app-fg]">Onboard and introspect servers</h1>
        <p className="max-w-2xl text-[11px] text-[--app-muted]">
          Discover tools exposed by each MCP server, apply Governance attachments, and track access outcomes via the ledger and observability stream.
        </p>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[--app-fg]">Server inventory</h2>
            <p className="mt-1 text-[11px] text-[--app-muted]">Live directory backed by the registry backend.</p>
          </div>
          <Link
            href="/registry/servers/onboard"
            className="inline-flex items-center justify-center rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90"
          >
            Onboard MCP server
          </Link>
        </div>

        <div className="mt-6">
          {publishers.length === 0 ? (
            <EmptyState
              title="No servers visible yet"
              message="Once a publisher is present in the registry, it will appear here as an MCP server source."
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {publishers.map((publisher) => (
                <Link
                  key={publisher.publisher_id}
                  href={`/registry/servers/${encodeURIComponent(publisher.publisher_id)}`}
                  className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring] transition hover:border-[--app-accent] hover:ring-[--app-accent]"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-sm font-semibold text-[--app-fg]">
                      {publisher.display_name ?? publisher.publisher_id}
                    </h2>
                    {publisher.trust_score?.overall != null ? (
                      <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
                        Trust {publisher.trust_score.overall.toFixed(1)}
                      </span>
                    ) : null}
                  </div>

                  <p className="line-clamp-3 text-[11px] leading-relaxed text-[--app-muted]">
                    {publisher.summary ?? "No summary provided."}
                  </p>

                  <p className="mt-auto text-[10px] text-[--app-muted]">
                    {publisher.tool_count ?? 0} tool
                    {(publisher.tool_count ?? 0) === 1 ? "" : "s"} in this registry
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

