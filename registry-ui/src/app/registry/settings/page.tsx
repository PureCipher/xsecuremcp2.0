import Link from "next/link";
import { getRegistryHealth } from "@/lib/registryClient";

import { AppThemePreferencesPanel } from "./AppThemePreferencesPanel";
import { CliTerminalPreferencesPanel } from "./CliTerminalPreferencesPanel";

export default async function RegistrySettingsPage() {
  const health = await getRegistryHealth();

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Registry settings
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">Policy overview</h1>
          <p className="max-w-xl text-[11px] text-[--app-muted]">
            Read-only view of how this SecureMCP registry is configured. Use the dedicated Policy
            page to manage live access rules and rollbacks.
          </p>
        </header>

        {health ? (
          <section className="grid gap-4 md:grid-cols-2">
            <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                Certification & moderation
              </h2>
              <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
                <li>
                  Minimum certification level:{" "}
                  <span className="font-semibold text-[--app-fg]">
                    {health.minimum_certification}
                  </span>
                </li>
                <li>
                  Moderation required:{" "}
                  <span className="font-semibold text-[--app-fg]">
                    {health.require_moderation ? "Yes" : "No"}
                  </span>
                </li>
              </ul>
            </div>

            <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
              <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                Authentication
              </h2>
              <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
                <li>
                  Auth enabled:{" "}
                  <span className="font-semibold text-[--app-fg]">
                    {health.auth_enabled ? "Yes" : "No"}
                  </span>
                </li>
                <li>
                  Issuer ID:{" "}
                  <span className="font-mono text-[--app-muted]">{health.issuer_id}</span>
                </li>
              </ul>
            </div>
          </section>
        ) : (
          <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[12px] text-[--app-muted]">
              Unable to load settings from the registry. Check that the registry is running and reachable.
            </p>
          </section>
        )}

        <AppThemePreferencesPanel />
        <CliTerminalPreferencesPanel />

        <p className="text-[10px] text-[--app-muted]">
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
  );
}
