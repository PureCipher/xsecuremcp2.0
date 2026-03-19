import Link from "next/link";
import {
  getRegistrySession,
  listJurisdictions,
  listInstitutions,
} from "@/lib/registryClient";
import { ConsentManager } from "./ConsentManager";

export default async function ConsentPage() {
  const sessionPayload = await getRegistrySession();
  const role = sessionPayload?.session?.role ?? null;
  const canAdmin = role === "admin";

  if (!canAdmin) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-xl font-semibold text-[--app-fg]">Federated Consent Graphs</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            Admin role required to manage consent graphs.
          </p>
          <p className="mt-4">
            <Link
              href="/registry/app"
              className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
            >
              ← Back to tools
            </Link>
          </p>
      </div>
    );
  }

  const jurisdictionsData = await listJurisdictions();
  const institutionsData = await listInstitutions();

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Federated Consent
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">
            Evaluate, manage, and visualize consent graphs
          </h1>
          <p className="max-w-2xl text-[11px] text-[--app-muted]">
            Test consent queries across jurisdictions, view access rights matrices,
            manage jurisdiction policies, and explore consent relationships between agents and resources.
          </p>
        </header>
        <ConsentManager
          initialJurisdictions={jurisdictionsData}
          initialInstitutions={institutionsData}
        />
    </div>
  );
}
