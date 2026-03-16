import Link from "next/link";
import { getPublisherProfile } from "@/lib/registryClient";

export default async function PublisherProfilePage(props: { params: Promise<{ publisherId: string }> }) {
  const { publisherId } = await props.params;
  const decodedId = decodeURIComponent(publisherId);
  const profile = await getPublisherProfile(decodedId);

  if (!profile) {
    return (
      <main className="px-4 py-8 text-sm text-emerald-50">
        <div className="mx-auto max-w-5xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-base font-semibold text-emerald-50">Publisher not found</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            No publisher profile is available for <span className="font-mono">{decodedId}</span>.
          </p>
          <p className="mt-3">
            <Link href="/registry/publishers" className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100">
              ← Back to all publishers
            </Link>
          </p>
        </div>
      </main>
    );
  }

  if (profile.error) {
    return (
      <main className="px-4 py-8 text-sm text-emerald-50">
        <div className="mx-auto max-w-5xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-base font-semibold text-emerald-50">Unable to load publisher</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">{profile.error}</p>
          <p className="mt-3">
            <Link href="/registry/publishers" className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100">
              ← Back to all publishers
            </Link>
          </p>
        </div>
      </main>
    );
  }

  const summary = profile.summary ?? {};
  const listings: any[] = profile.listings ?? [];

  return (
    <main className="px-4 py-8 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
              Publisher profile
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-emerald-50">
              {summary.display_name ?? summary.publisher_id}
            </h1>
            <p className="mt-1 text-[11px] text-emerald-200/90">
              {summary.publisher_id} · {summary.tool_count ?? 0} tool
              {(summary.tool_count ?? 0) === 1 ? "" : "s"} in this registry
            </p>
          </div>
          {summary.trust_score?.overall != null ? (
            <span className="rounded-full bg-emerald-900/80 px-3 py-1 text-[10px] font-semibold text-emerald-200">
              Trust score {summary.trust_score.overall.toFixed(1)}
            </span>
          ) : null}
        </header>

        <section className="grid gap-4 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <div className="space-y-3 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              About
            </h2>
            <p className="text-[13px] leading-relaxed text-emerald-100/90">
              {summary.description ?? "This publisher has not added a profile description yet."}
            </p>
          </div>
          <div className="space-y-3 rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Snapshot
            </h2>
            <ul className="space-y-1 text-[11px] text-emerald-100/90">
              <li>
                <span className="font-medium text-emerald-50">Tools:</span>{" "}
                {summary.tool_count ?? listings.length}
              </li>
              {summary.verified_tool_count != null ? (
                <li>
                  <span className="font-medium text-emerald-50">Verified tools:</span>{" "}
                  {summary.verified_tool_count}
                </li>
              ) : null}
            </ul>
          </div>
        </section>

        <section className="rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
            Tools from this publisher
          </h2>
          {listings.length === 0 ? (
            <p className="text-[12px] text-emerald-100/90">
              This publisher does not have any live verified tools yet.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {listings.map((tool) => (
                <Link
                  key={tool.tool_name}
                  href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                  className="flex flex-col gap-2 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70 transition hover:ring-emerald-400/90"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold text-emerald-50">
                        {tool.display_name ?? tool.tool_name}
                      </h3>
                      <p className="text-[10px] text-emerald-300/90">{tool.tool_name}</p>
                    </div>
                    <span className="rounded-full bg-emerald-900/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                      {tool.certification_level?.toUpperCase?.() ?? "UNRATED"}
                    </span>
                  </div>
                  <p className="line-clamp-3 text-[11px] leading-relaxed text-emerald-100/90">
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
            className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100"
          >
            ← Back to all publishers
          </Link>
        </div>
      </div>
    </main>
  );
}

