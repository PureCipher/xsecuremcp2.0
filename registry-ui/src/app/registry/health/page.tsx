import Link from "next/link";
import {
  getRegistryHealth,
  getSecurityHealth,
  getFederationStatus,
  getRevocations,
} from "@/lib/registryClient";

import { Box, Card, CardContent, Chip, Typography } from "@mui/material";

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
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Registry health
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            Unable to load health information from the registry.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const components = securityHealth?.components ?? {};
  const componentCount = securityHealth?.component_count ?? 0;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Registry health
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          SecureMCP registry status
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
          Comprehensive health view of the SecureMCP guardrail pipeline, all five security pillars, authentication, moderation, and registry counts.
        </Typography>
      </Box>

        {/* Registry Overview */}
      <Box component="section" sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" } }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Status
            </Typography>
            <Typography sx={{ mt: 1.5, fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
              {health.status === "ok" ? "Healthy" : String(health.status)}
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
              Minimum level:{" "}
              <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                {health.minimum_certification}
              </Box>
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Policy
            </Typography>
            <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
              <li>
                Auth enabled:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {health.auth_enabled ? "Yes" : "No"}
                </Box>
              </li>
              <li>
                Moderation required:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {health.require_moderation ? "Yes" : "No"}
                </Box>
              </li>
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Counts
            </Typography>
            <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
              <li>
                Registered tools:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {health.registered_tools}
                </Box>
              </li>
              <li>
                Verified tools:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {health.verified_tools}
                </Box>
              </li>
              <li>
                Pending review:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {health.pending_review}
                </Box>
              </li>
            </Box>
          </CardContent>
        </Card>
      </Box>

        {/* Security Components Grid */}
        {componentCount > 0 ? (
          <Box component="section" sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Security Components
              </Typography>
              <Chip
                size="small"
                label={`${componentCount} active`}
                sx={{ borderRadius: 999, bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11 }}
              />
            </Box>
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr", lg: "1fr 1fr 1fr 1fr" } }}>
              {Object.entries(components).map(([key, status]) => {
                const info = PILLAR_COMPONENTS[key];
                return (
                  <Link
                    key={key}
                    href={info?.href ?? "/registry/health"}
                    className="group"
                    style={{ textDecoration: "none" }}
                  >
                    <Box
                      sx={{
                        borderRadius: 3,
                        border: "1px solid var(--app-border)",
                        bgcolor: "var(--app-surface)",
                        p: 1.5,
                        boxShadow: "none",
                        transition: "background-color 120ms ease, border-color 120ms ease",
                        "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-accent)" },
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Box
                          sx={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            bgcolor: status === "ok" ? "var(--app-accent)" : "rgb(248, 113, 113)",
                          }}
                        />
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-muted)" }}>
                          {info?.label ?? key}
                        </Typography>
                      </Box>
                      <Typography variant="caption" sx={{ mt: 0.5, display: "block", pl: 2.25, color: "var(--app-muted)", fontSize: 10 }}>
                        {status === "ok" ? "Operational" : status}
                      </Typography>
                    </Box>
                  </Link>
                );
              })}
            </Box>
          </Box>
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
    </Box>
  );
}
