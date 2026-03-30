import Link from "next/link";

import {
  getPublisherProfile,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { ServerDetailTabs } from "./ServerDetailTabs";

export default async function ServerDetailPage(props: {
  params: Promise<{ serverId: string }>;
}) {
  const { serverId } = await props.params;
  const decodedId = decodeURIComponent(serverId);

  const profile = await getPublisherProfile(decodedId);
  if (!profile || profile.error) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <h1 className="text-base font-semibold text-[--app-fg]">Unable to load server</h1>
        <p className="mt-2 text-[12px] text-[--app-muted]">
          No server profile is available for <span className="font-mono">{decodedId}</span>.
        </p>
        <p className="mt-3">
          <Link
            href="/registry/servers"
            className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
          >
            ← Back to MCP servers
          </Link>
        </p>
      </div>
    );
  }

  const summary: PublisherSummary = profile.summary ?? { publisher_id: decodedId };
  const listings: RegistryToolListing[] = profile.listings ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            MCP server profile
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-[--app-fg]">
            {summary.display_name ?? summary.publisher_id}
          </h1>
          <p className="mt-1 text-[11px] text-[--app-muted]">
            {summary.publisher_id} · {summary.tool_count ?? listings.length} tool
            {(summary.tool_count ?? listings.length) === 1 ? "" : "s"} in this registry
          </p>
        </div>
        {summary.trust_score?.overall != null ? (
          <span className="rounded-full bg-[--app-surface] px-3 py-1 text-[10px] font-semibold text-[--app-muted]">
            Trust score {summary.trust_score.overall.toFixed(1)}
          </span>
        ) : null}
      </header>

      <ServerDetailTabs serverId={decodedId} summary={summary} listings={listings} />

      <div className="pt-2">
        <Link
          href="/registry/servers"
          className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
        >
          ← Back to MCP servers
        </Link>
      </div>
    </div>
  );
}

