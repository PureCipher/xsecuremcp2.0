import Link from "next/link";

import { EmptyState } from "@/components/security";

export default function ClientsPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
          Clients
        </p>
        <h1 className="text-2xl font-semibold text-[--app-fg]">Onboard and bind clients</h1>
        <p className="max-w-2xl text-[11px] text-[--app-muted]">
          UI skeleton for connecting client identities to MCP servers with effective Policy/Contract/Consent controls.
        </p>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[--app-fg]">Client registry</h2>
            <p className="mt-1 text-[11px] text-[--app-muted]">
              After backend integration, this will list onboarded clients and their access bindings.
            </p>
          </div>
          <Link
            href="/registry/clients/onboard"
            className="inline-flex items-center justify-center rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90"
          >
            Onboard client
          </Link>
        </div>

        <div className="mt-6">
          <EmptyState
            title="No clients onboarded yet"
            message="Connect a client identity, select the MCP servers (and optionally tool scope), then run a simulation to validate effective access."
          />
        </div>
      </section>
    </div>
  );
}

