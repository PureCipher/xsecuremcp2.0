import Link from "next/link";
import {
  getRegistrySession,
  getAccountabilityLog,
  getSecurityHealth,
} from "@/lib/registryClient";
import { ReflexiveManager } from "./ReflexiveManager";

export default async function ReflexivePage() {
  const sessionPayload = await getRegistrySession();
  const role = sessionPayload?.session?.role ?? null;
  const canAdmin = role === "admin";

  if (!canAdmin) {
    return (
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">Reflexive Execution Engine</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Admin role required to access the reflexive execution engine.
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

  const accountabilityData = await getAccountabilityLog();
  const healthData = await getSecurityHealth();

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Reflexive Execution
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">
            Monitor, introspect, and gate agent behavior
          </h1>
          <p className="max-w-2xl text-[11px] text-emerald-100/80">
            Examine behavioral drift, threat levels, compliance status, and execution verdicts
            for every actor in the system. Pre-execution gating halts, throttles, or requires
            confirmation for high-risk operations.
          </p>
        </header>
        <ReflexiveManager
          initialAccountability={
            accountabilityData?.entries?.map(entry => ({
              ...entry,
              threat_level: entry.threat_level ?? "unknown",
              compliance_status: entry.compliance_status ?? "unknown",
              verdict: entry.verdict ?? "unknown",
              timestamp: entry.timestamp ?? new Date().toISOString(),
            })) ?? []
          }
          initialHealth={
            healthData
              ? {
                  overall_status: (healthData.status as "ok" | "not_configured" | "degraded") ?? "not_configured",
                  component_count: healthData.component_count ?? 0,
                  components: healthData.components
                    ? Object.entries(healthData.components).map(([name, status]) => ({
                        name,
                        status: (status as "ok" | "not_configured") ?? "not_configured",
                      }))
                    : undefined,
                  timestamp: healthData.timestamp,
                }
              : undefined
          }
        />
      </div>
    </main>
  );
}
