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
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">Federated Consent Graphs</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Admin role required to manage consent graphs.
          </p>
          <p className="mt-4">
            <Link href="/registry/app" className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100">
              ← Back to tools
            </Link>
          </p>
        </div>
      </main>
    );
  }

  const jurisdictionsData = await listJurisdictions();
  const institutionsData = await listInstitutions();

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Federated Consent
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">
            Evaluate, manage, and visualize consent graphs
          </h1>
          <p className="max-w-2xl text-[11px] text-emerald-100/80">
            Test consent queries across jurisdictions, view access rights matrices,
            manage jurisdiction policies, and explore consent relationships between agents and resources.
          </p>
        </header>
        <ConsentManager
          initialJurisdictions={jurisdictionsData}
          initialInstitutions={institutionsData}
        />
      </div>
    </main>
  );
}
