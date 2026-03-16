import Link from "next/link";
import { getRegistryHealth } from "@/lib/registryClient";

export default async function RegistrySettingsPage() {
  const health = await getRegistryHealth();

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Registry settings
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">Policy overview</h1>
          <p className="max-w-xl text-[11px] text-emerald-100/80">
            Read-only view of how this SecureMCP registry is configured. Use the dedicated Policy
            page to manage live access rules and rollbacks.
          </p>
        </header>

        {health ? (
          <section className="grid gap-4 md:grid-cols-2">
            <div className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                Certification & moderation
              </h2>
              <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
                <li>
                  Minimum certification level:{" "}
                  <span className="font-semibold text-emerald-50">
                    {health.minimum_certification}
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
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
                Authentication
              </h2>
              <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
                <li>
                  Auth enabled:{" "}
                  <span className="font-semibold text-emerald-50">
                    {health.auth_enabled ? "Yes" : "No"}
                  </span>
                </li>
                <li>
                  Issuer ID:{" "}
                  <span className="font-mono text-emerald-100">{health.issuer_id}</span>
                </li>
              </ul>
            </div>
          </section>
        ) : (
          <section className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60">
            <p className="text-[12px] text-emerald-100/90">
              Unable to load settings from the registry. Check that the registry is running and reachable.
            </p>
          </section>
        )}

        <p className="text-[10px] text-emerald-300/80">
          Policy changes now live in{" "}
          <Link href="/registry/policy" className="underline">
            Policy
          </Link>
          . For a live snapshot of counts and status, see{" "}
          <Link href="/registry/health" className="underline">
            Health
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
