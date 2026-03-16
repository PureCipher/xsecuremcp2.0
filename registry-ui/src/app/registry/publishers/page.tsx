import Link from "next/link";
import { listPublishers, type PublisherSummary } from "@/lib/registryClient";

export default async function PublishersPage() {
  const payload = (await listPublishers()) ?? { publishers: [], count: 0 };
  const publishers: PublisherSummary[] = payload.publishers ?? [];

  return (
    <main className="px-4 py-8 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
              Publisher directory
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-emerald-50">
              People and teams behind the tools
            </h1>
            <p className="mt-1 max-w-xl text-[11px] text-emerald-100/80">
              Browse publishers with live listings in the registry. Open any profile to see their tools and trust
              signals.
            </p>
          </div>
        </header>

        <section className="rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          {publishers.length === 0 ? (
            <p className="text-emerald-100/90">
              No publishers are visible yet. Once tools are in the registry, their publishers will appear here.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {publishers.map((publisher) => (
                <Link
                  key={publisher.publisher_id}
                  href={`/registry/publishers/${encodeURIComponent(publisher.publisher_id)}`}
                  className="flex flex-col gap-2 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70 transition hover:ring-emerald-400/90"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-sm font-semibold text-emerald-50">
                      {publisher.display_name ?? publisher.publisher_id}
                    </h2>
                    {publisher.trust_score?.overall != null ? (
                      <span className="rounded-full bg-emerald-900/80 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
                        Trust {publisher.trust_score.overall.toFixed(1)}
                      </span>
                    ) : null}
                  </div>
                  <p className="line-clamp-3 text-[11px] leading-relaxed text-emerald-100/90">
                    {publisher.summary ?? "No summary provided."}
                  </p>
                  <p className="mt-auto text-[10px] text-emerald-200/90">
                    {publisher.tool_count ?? 0} tool
                    {(publisher.tool_count ?? 0) === 1 ? "" : "s"} in this registry
                  </p>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
