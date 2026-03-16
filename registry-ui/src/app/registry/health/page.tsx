import { getRegistryHealth } from "@/lib/registryClient";

export default async function RegistryHealthPage() {
  const health = await getRegistryHealth();

  if (!health) {
    return (
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">Registry health</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Unable to load health information from the registry.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Registry health
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">SecureMCP registry status</h1>
          <p className="max-w-xl text-[11px] text-emerald-100/80">
            Snapshot of the SecureMCP guardrail pipeline, authentication, moderation, and registry counts.
          </p>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Status
            </p>
            <p className="mt-2 text-sm font-semibold text-emerald-50">
              {health.status === "ok" ? "Healthy" : String(health.status)}
            </p>
            <p className="mt-1 text-[11px] text-emerald-200/90">
              Minimum level: <span className="font-semibold">{health.minimum_certification}</span>
            </p>
          </div>

          <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Policy
            </p>
            <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
              <li>
                Auth enabled:{" "}
                <span className="font-semibold text-emerald-50">
                  {health.auth_enabled ? "Yes" : "No"}
                </span>
              </li>
              <li>
                Moderation required:{" "}
                <span className="font-semibold text-emerald-50">
                  {health.require_moderation ? "Yes" : "No"}
                </span>
              </li>
            </ul>
          </div>

          <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Counts
            </p>
            <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
              <li>
                Registered tools:{" "}
                <span className="font-semibold text-emerald-50">{health.registered_tools}</span>
              </li>
              <li>
                Verified tools:{" "}
                <span className="font-semibold text-emerald-50">{health.verified_tools}</span>
              </li>
              <li>
                Pending review:{" "}
                <span className="font-semibold text-emerald-50">{health.pending_review}</span>
              </li>
            </ul>
          </div>
        </section>

        <p className="text-[10px] text-emerald-300/80">
          Last updated: {health.timestamp} · Server: {health.server}
        </p>
      </div>
    </main>
  );
}

