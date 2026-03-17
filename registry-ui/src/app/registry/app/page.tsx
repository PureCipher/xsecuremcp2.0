import Link from "next/link";
import { redirect } from "next/navigation";
import {
  getRegistrySession,
  listVerifiedTools,
  type RegistryToolListing,
} from "@/lib/registryClient";

export default async function RegistryAppPage() {
  const sessionPayload = await getRegistrySession();
  const hasSession = sessionPayload?.session != null;

  if (!hasSession) {
    redirect("/login");
  }

  const catalog = (await listVerifiedTools()) ?? { tools: [], count: 0 };
  const tools: RegistryToolListing[] = catalog.tools ?? [];

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
              PureCipher Secured MCP Registry
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-emerald-50">Trusted tool directory</h1>
            <p className="mt-1 max-w-xl text-xs text-emerald-100/80">
              Listings below are rendered from the existing Python registry backend via the Next.js frontend.
            </p>
          </div>
          <div className="mt-1 flex flex-col items-start gap-1 text-xs text-emerald-200/90 sm:items-end">
            <p>
              Signed in as{" "}
              <span className="font-semibold">{sessionPayload.session?.username ?? "account"}</span>
            </p>
            <Link
              href="/registry/publishers"
              className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100"
            >
              Browse publishers →
            </Link>
          </div>
        </header>

        <section className="rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          {tools.length === 0 ? (
            <p className="text-emerald-100/90">
              No verified tools are published yet. Once tools are in the registry they&apos;ll appear here.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {tools.map((tool) => (
                <Link
                  key={tool.tool_name}
                  href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                  className="flex flex-col gap-2 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70 transition hover:ring-emerald-400/90"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-semibold text-emerald-50">
                        {tool.display_name ?? tool.tool_name}
                      </h2>
                      <p className="text-[10px] text-emerald-300/90">{tool.tool_name}</p>
                    </div>
                    <span className="rounded-full bg-emerald-900/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                      {tool.certification_level?.toUpperCase?.() ?? "UNRATED"}
                    </span>
                  </div>
                  <p className="line-clamp-3 text-[11px] leading-relaxed text-emerald-100/90">
                    {tool.description ?? "No description provided."}
                  </p>
                  <div className="mt-auto flex flex-wrap items-center gap-2 pt-2 text-[10px] text-emerald-200/90">
                    {Array.isArray(tool.categories)
                      ? tool.categories.map((cat: string) => (
                          <span
                            key={cat}
                            className="rounded-full bg-emerald-900/80 px-2 py-0.5 text-[10px] font-medium text-emerald-100"
                          >
                            {cat}
                          </span>
                        ))
                      : null}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
