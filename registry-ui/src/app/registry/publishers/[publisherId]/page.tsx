import Link from "next/link";
import {
  getPublisherProfile,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { CertificationBadge } from "@/components/security";

export default async function PublisherProfilePage(props: { params: Promise<{ publisherId: string }> }) {
  const { publisherId } = await props.params;
  const decodedId = decodeURIComponent(publisherId);
  const profile = await getPublisherProfile(decodedId);

  if (!profile) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-base font-semibold text-[--app-fg]">Publisher not found</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            No publisher profile is available for <span className="font-mono">{decodedId}</span>.
          </p>
          <p className="mt-3">
            <Link
              href="/registry/publishers"
              className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
            >
              ← Back to all publishers
            </Link>
          </p>
      </div>
    );
  }

  if (profile.error) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-base font-semibold text-[--app-fg]">Unable to load publisher</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">{profile.error}</p>
          <p className="mt-3">
            <Link
              href="/registry/publishers"
              className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
            >
              ← Back to all publishers
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
              Publisher profile
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-[--app-fg]">
              {summary.display_name ?? summary.publisher_id}
            </h1>
            <p className="mt-1 text-[11px] text-[--app-muted]">
              {summary.publisher_id} · {summary.tool_count ?? 0} tool
              {(summary.tool_count ?? 0) === 1 ? "" : "s"} in this registry
            </p>
          </div>
          {summary.trust_score?.overall != null ? (
            <span className="rounded-full bg-[--app-surface] px-3 py-1 text-[10px] font-semibold text-[--app-muted]">
              Trust score {summary.trust_score.overall.toFixed(1)}
            </span>
          ) : null}
        </header>

        <section className="grid gap-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <div className="space-y-3 rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              About
            </h2>
            <p className="text-[13px] leading-relaxed text-[--app-muted]">
              {summary.description ?? "This publisher has not added a profile description yet."}
            </p>
          </div>
          <div className="space-y-3 rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Snapshot
            </h2>
            <ul className="space-y-1 text-[11px] text-[--app-muted]">
              <li>
                <span className="font-medium text-[--app-fg]">Tools:</span>{" "}
                {summary.tool_count ?? listings.length}
              </li>
              {summary.verified_tool_count != null ? (
                <li>
                  <span className="font-medium text-[--app-fg]">Verified tools:</span>{" "}
                  {summary.verified_tool_count}
                </li>
              ) : null}
            </ul>
          </div>
        </section>

        <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
            Tools from this publisher
          </h2>
          {listings.length === 0 ? (
            <p className="text-[12px] text-[--app-muted]">
              This publisher does not have any live verified tools yet.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {listings.map((tool) => (
                <Link
                  key={tool.tool_name}
                  href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                  className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring] transition hover:border-[--app-accent] hover:ring-[--app-accent]"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold text-[--app-fg]">
                        {tool.display_name ?? tool.tool_name}
                      </h3>
                      <p className="text-[10px] text-[--app-muted]">{tool.tool_name}</p>
                    </div>
                    <CertificationBadge level={tool.certification_level} />
                  </div>
                  <p className="line-clamp-3 text-[11px] leading-relaxed text-[--app-muted]">
                    {tool.description ?? "No description provided."}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </section>

        <div className="pt-2">
          <Link
            href="/registry/publishers"
            className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
          >
            ← Back to all publishers
          </Link>
        </div>
    </div>
  );
}
