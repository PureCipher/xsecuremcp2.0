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
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-xl font-semibold text-[--app-fg]">Registry health</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            Unable to load health information from the registry.
          </p>
      </div>
    );
  }

  const components = securityHealth?.components ?? {};
  const componentCount = securityHealth?.component_count ?? 0;

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Registry health
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">SecureMCP registry status</h1>
          <p className="max-w-xl text-[11px] text-[--app-muted]">
            Comprehensive health view of the SecureMCP guardrail pipeline, all five security
            pillars, authentication, moderation, and registry counts.
          </p>
        </header>

        {/* Registry Overview */}
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Status
            </p>
            <p className="mt-2 text-sm font-semibold text-[--app-fg]">
              {health.status === "ok" ? "Healthy" : String(health.status)}
            </p>
            <p className="mt-1 text-[11px] text-[--app-muted]">
              Minimum level: <span className="font-semibold">{health.minimum_certification}</span>
            </p>
          </div>

          <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Policy
            </p>
            <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
              <li>
                Auth enabled:{" "}
                <span className="font-semibold text-[--app-fg]">
                  {health.auth_enabled ? "Yes" : "No"}
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
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Counts
            </p>
            <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
              <li>
                Registered tools:{" "}
                <span className="font-semibold text-[--app-fg]">{health.registered_tools}</span>
              </li>
              <li>
                Verified tools:{" "}
                <span className="font-semibold text-[--app-fg]">{health.verified_tools}</span>
              </li>
              <li>
                Pending review:{" "}
                <span className="font-semibold text-[--app-fg]">{health.pending_review}</span>
              </li>
            </ul>
          </div>
        </section>

        {/* Security Components Grid */}
        {componentCount > 0 ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                Security Components
              </p>
              <span className="rounded-full bg-[--app-control-active-bg] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
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
                    className="group rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring] transition hover:bg-[--app-hover-bg] hover:border-[--app-accent] hover:ring-[--app-accent]"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${
                          status === "ok" ? "bg-[--app-accent]" : "bg-red-400"
                        }`}
                      />
                      <p className="text-[11px] font-medium text-[--app-muted] group-hover:text-[--app-fg]">
                        {info?.label ?? key}
                      </p>
                    </div>
                    <p className="mt-1 pl-4 text-[10px] text-[--app-muted]">
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
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
              Federation Peers
            </p>
            {federationData.peers && federationData.peers.length > 0 ? (
              <div className="overflow-hidden rounded-2xl ring-1 ring-[--app-surface-ring]">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-[--app-border] bg-[--app-surface]">
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Peer ID
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Endpoint
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Status
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Trust
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Last Seen
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {federationData.peers.map((peer) => (
                      <tr
                        key={peer.peer_id}
                        className="border-b border-[--app-border] bg-[--app-control-bg]"
                      >
                        <td className="px-3 py-2 font-mono text-[10px] text-[--app-muted]">
                          {peer.peer_id}
                        </td>
                        <td className="px-3 py-2 text-[--app-fg]">{peer.endpoint}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                              peer.status === "active"
                                ? "bg-[--app-control-active-bg] text-[--app-muted]"
                                : "bg-zinc-500/20 text-zinc-300"
                            }`}
                          >
                            {peer.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-[--app-fg]">
                          {typeof peer.trust_score === "number"
                            ? peer.trust_score.toFixed(1)
                            : "—"}
                        </td>
                        <td className="px-3 py-2 text-[10px] text-[--app-muted]">
                          {peer.last_seen}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] py-6 text-center ring-1 ring-[--app-surface-ring]">
                <p className="text-[11px] text-[--app-muted]">No federation peers configured</p>
              </div>
            )}
          </section>
        ) : null}

        {/* Certificate Revocation List */}
        {revocationsData && !revocationsData.error ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
                Certificate Revocations
              </p>
              <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-medium text-[--app-muted]">
                {revocationsData.count ?? 0} entries
              </span>
            </div>
            {revocationsData.entries && revocationsData.entries.length > 0 ? (
              <div className="overflow-hidden rounded-2xl ring-1 ring-[--app-surface-ring]">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-[--app-border] bg-[--app-surface]">
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Tool
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Reason
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Revoked By
                      </th>
                      <th className="px-3 py-2 font-semibold uppercase tracking-wider text-[--app-muted]">
                        Date
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {revocationsData.entries.map((entry, i) => (
                      <tr
                        key={i}
                        className="border-b border-[--app-border] bg-[--app-control-bg]"
                      >
                        <td className="px-3 py-2 font-medium text-red-300">
                          {entry.tool_name}
                        </td>
                        <td className="px-3 py-2 text-[--app-fg]">{entry.reason}</td>
                        <td className="px-3 py-2 text-[--app-muted]">{entry.revoked_by}</td>
                        <td className="px-3 py-2 text-[10px] text-[--app-muted]">
                          {entry.revoked_at}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] py-6 text-center ring-1 ring-[--app-surface-ring]">
                <p className="text-[11px] text-[--app-muted]">No revocations — all tools in good standing</p>
              </div>
            )}
          </section>
        ) : null}

        {/* Quick Links */}
        <section className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[--app-muted]">
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
                className="group rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring] transition hover:bg-[--app-hover-bg] hover:border-[--app-accent] hover:ring-[--app-accent]"
              >
                <p className="text-[11px] font-semibold text-[--app-muted] group-hover:text-[--app-fg]">
                  {pillar.label}
                </p>
                <p className="mt-0.5 text-[10px] text-[--app-muted]">{pillar.desc}</p>
              </Link>
            ))}
          </div>
        </section>

        <p className="text-[10px] text-[--app-muted]">
          Last updated: {health.timestamp} · Server: {health.server}
          {securityHealth?.timestamp ? ` · Security: ${securityHealth.timestamp}` : ""}
        </p>
    </div>
  );
}
