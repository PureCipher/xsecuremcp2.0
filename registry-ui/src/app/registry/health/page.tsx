import Link from "next/link";
import {
  getRegistryHealth,
  getSecurityHealth,
  getFederationStatus,
  getRevocations,
} from "@/lib/registryClient";

const PILLAR_COMPONENTS: Record<string, { label: string; href: string }> = {
  policy_engine: { label: "Policy Engine", href: "/registry/policy" },
  policy_audit_log: { label: "Policy Audit", href: "/registry/policy" },
  policy_versioning: { label: "Policy Versioning", href: "/registry/policy" },
  policy_validator: { label: "Policy Validator", href: "/registry/policy" },
  policy_monitor: { label: "Policy Monitor", href: "/registry/policy" },
  policy_governor: { label: "Policy Governance", href: "/registry/policy" },
  contracts: { label: "Digital Contracts", href: "/registry/contracts" },
  provenance: { label: "Provenance Ledger", href: "/registry/provenance" },
  introspection_engine: { label: "Reflexive Engine", href: "/registry/reflexive" },
  federated_consent: { label: "Federated Consent", href: "/registry/consent" },
  federation: { label: "Trust Federation", href: "/registry/health" },
  crl: { label: "Revocation List", href: "/registry/health" },
  dashboard: { label: "Security Dashboard", href: "/registry/health" },
  marketplace: { label: "Tool Marketplace", href: "/registry/app" },
  registry: { label: "Trust Registry", href: "/registry/publishers" },
  compliance: { label: "Compliance Reporter", href: "/registry/health" },
  event_bus: { label: "Event Bus", href: "/registry/health" },
};

export default async function RegistryHealthPage() {
  const [health, securityHealth, federationData, revocationsData] = await Promise.all([
    getRegistryHealth(),
    getSecurityHealth(),
    getFederationStatus(),
    getRevocations(),
  ]);

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

  const components = securityHealth?.components ?? {};
  const componentCount = securityHealth?.component_count ?? 0;

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Registry health
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">SecureMCP registry status</h1>
          <p className="max-w-xl text-[11px] text-emerald-100/80">
            Comprehensive health view of the SecureMCP guardrail pipeline, all five security
            pillars, authentication, moderation, and registry counts.
          </p>
        </header>

        {/* Registry Overview */}
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

        {/* Security Components Grid */}
        {componentCount > 0 ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                Security Components
              </p>
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                {componentCount} active
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {Object.entries(components).map(([key, status]) => {
                const info = PILLAR_COMPONENTS[key];
                return (
                  <Link
                    key={key}
                    href={info?.href ?? "/registry/health"}
                    className="group rounded-2xl bg-emerald-900/30 p-3 ring-1 ring-emerald-700/40 transition hover:bg-emerald-800/30 hover:ring-emerald-600/50"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${
                          status === "ok" ? "bg-emerald-400" : "bg-red-400"
                        }`}
                      />
                      <p className="text-[11px] font-medium text-emerald-100 group-hover:text-emerald-50">
                        {info?.label ?? key}
                      </p>
                    </div>
                    <p className="mt-1 pl-4 text-[10px] text-emerald-300/60">
                      {status === "ok" ? "Operational" : status}
                    </p>
                  </Link>
                );
              })}
            </div>
          </section>
        ) : null}

        {/* Federation Peers */}
        {federationData && !federationData.error ? (
          <section className="space-y-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
              Federation Peers
            </p>
            {federationData.peers && federationData.peers.length > 0 ? (
              <div className="overflow-hidden rounded-2xl ring-1 ring-emerald-700/60">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-emerald-700/50 bg-emerald-900/60">
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Peer ID
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Endpoint
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Status
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Trust
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Last Seen
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {federationData.peers.map((peer) => (
                      <tr
                        key={peer.peer_id}
                        className="border-b border-emerald-800/30 bg-emerald-900/20"
                      >
                        <td className="px-3 py-2 font-mono text-[10px] text-emerald-200">
                          {peer.peer_id}
                        </td>
                        <td className="px-3 py-2 text-emerald-100">{peer.endpoint}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                              peer.status === "active"
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-zinc-500/20 text-zinc-300"
                            }`}
                          >
                            {peer.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-emerald-100">
                          {typeof peer.trust_score === "number"
                            ? peer.trust_score.toFixed(1)
                            : "—"}
                        </td>
                        <td className="px-3 py-2 text-[10px] text-emerald-300/70">
                          {peer.last_seen}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-2xl bg-emerald-900/20 py-6 text-center ring-1 ring-emerald-700/30">
                <p className="text-[11px] text-emerald-200/70">No federation peers configured</p>
              </div>
            )}
          </section>
        ) : null}

        {/* Certificate Revocation List */}
        {revocationsData && !revocationsData.error ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                Certificate Revocations
              </p>
              <span className="rounded-full bg-emerald-900/60 px-2 py-0.5 text-[10px] font-medium text-emerald-200">
                {revocationsData.count ?? 0} entries
              </span>
            </div>
            {revocationsData.entries && revocationsData.entries.length > 0 ? (
              <div className="overflow-hidden rounded-2xl ring-1 ring-emerald-700/60">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-emerald-700/50 bg-emerald-900/60">
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Tool
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Reason
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Revoked By
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-emerald-300">
                        Date
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {revocationsData.entries.map((entry, i) => (
                      <tr
                        key={i}
                        className="border-b border-emerald-800/30 bg-emerald-900/20"
                      >
                        <td className="px-3 py-2 font-medium text-red-300">
                          {entry.tool_name}
                        </td>
                        <td className="px-3 py-2 text-emerald-100">{entry.reason}</td>
                        <td className="px-3 py-2 text-emerald-200/80">{entry.revoked_by}</td>
                        <td className="px-3 py-2 text-[10px] text-emerald-300/70">
                          {entry.revoked_at}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-2xl bg-emerald-900/20 py-6 text-center ring-1 ring-emerald-700/30">
                <p className="text-[11px] text-emerald-200/70">No revocations — all tools in good standing</p>
              </div>
            )}
          </section>
        ) : null}

        {/* Quick Links */}
        <section className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Security Pillars
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              { label: "Policy Engine", href: "/registry/policy", desc: "Pluggable policies" },
              { label: "Contracts", href: "/registry/contracts", desc: "Digital agreements" },
              { label: "Provenance", href: "/registry/provenance", desc: "Immutable ledger" },
              { label: "Reflexive", href: "/registry/reflexive", desc: "Behavioral gating" },
              { label: "Consent", href: "/registry/consent", desc: "Federated graphs" },
            ].map((pillar) => (
              <Link
                key={pillar.href}
                href={pillar.href}
                className="group rounded-2xl bg-emerald-900/30 p-3 ring-1 ring-emerald-700/40 transition hover:bg-emerald-800/30 hover:ring-emerald-500/40"
              >
                <p className="text-[11px] font-semibold text-emerald-100 group-hover:text-emerald-50">
                  {pillar.label}
                </p>
                <p className="mt-0.5 text-[10px] text-emerald-300/60">{pillar.desc}</p>
              </Link>
            ))}
          </div>
        </section>

        <p className="text-[10px] text-emerald-300/80">
          Last updated: {health.timestamp} · Server: {health.server}
          {securityHealth?.timestamp ? ` · Security: ${securityHealth.timestamp}` : ""}
        </p>
      </div>
    </main>
  );
}
