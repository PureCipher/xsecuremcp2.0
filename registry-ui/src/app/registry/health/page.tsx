import Link from "next/link";
import type { ReactNode } from "react";
import {
  getRegistryHealth,
  getSecurityHealth,
  getFederationStatus,
  getRevocations,
} from "@/lib/registryClient";

import { Box, Card, CardContent, Chip, Divider, Typography } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

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

const SECURITY_PILLARS = [
  { label: "Policy Engine", href: "/registry/policy", desc: "Policy packs, validation, audit, and governance" },
  { label: "Contracts", href: "/registry/contracts", desc: "Negotiated agent agreements and signatures" },
  { label: "Provenance", href: "/registry/provenance", desc: "Immutable records, chain integrity, and proofs" },
  { label: "Reflexive", href: "/registry/reflexive", desc: "Behavioral introspection and execution verdicts" },
  { label: "Consent", href: "/registry/consent", desc: "Federated consent checks and jurisdiction graphs" },
];

const sectionTitleSx = {
  fontSize: 12,
  fontWeight: 800,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--app-muted)",
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
      <Card variant="outlined">
        <CardContent>
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

  const okComponents = Object.values(components).filter((status) => status === "ok").length;
  const attentionComponents = Math.max(componentCount - okComponents, 0);
  const peerCount = federationData && !federationData.error ? (federationData.peer_count ?? federationData.peers?.length ?? 0) : 0;
  const revocationCount = revocationsData && !revocationsData.error ? (revocationsData.count ?? revocationsData.entries?.length ?? 0) : 0;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Registry health"
        title="SecureMCP registry status"
        description="A calm operational view of registry readiness, security components, federation, revocations, and the five guardrail pillars."
      />

      <Card variant="outlined" sx={{ overflow: "hidden" }}>
        <CardContent sx={{ p: 0 }}>
          <Box
            sx={{
              p: { xs: 2.5, md: 3 },
              display: "grid",
              gap: 2.5,
              gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.1fr) minmax(280px, 0.9fr)" },
              alignItems: "stretch",
            }}
          >
            <Box
              sx={{
                p: { xs: 2.5, md: 3 },
                borderRadius: 4,
                bgcolor: health.status === "ok" ? "var(--app-control-active-bg)" : "rgba(239, 68, 68, 0.10)",
                border: "1px solid var(--app-border)",
                display: "grid",
                gap: 2,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
                <Box>
                  <Typography sx={sectionTitleSx}>Registry posture</Typography>
                  <Typography sx={{ mt: 1, fontSize: { xs: 24, md: 30 }, lineHeight: 1.1, fontWeight: 850, color: "var(--app-fg)" }}>
                    {health.status === "ok" ? "Healthy and accepting registry traffic" : `Status: ${String(health.status)}`}
                  </Typography>
                  <Typography sx={{ mt: 1, maxWidth: 640, fontSize: 13, color: "var(--app-muted)" }}>
                    Minimum certification is {health.minimum_certification ?? "not set"}. Authentication is {health.auth_enabled ? "enabled" : "disabled"} and moderation is {health.require_moderation ? "required" : "not required"}.
                  </Typography>
                </Box>
                <Chip
                  label={health.status === "ok" ? "Healthy" : String(health.status)}
                  sx={{
                    bgcolor: health.status === "ok" ? "var(--app-accent)" : "rgba(239, 68, 68, 0.14)",
                    color: health.status === "ok" ? "var(--app-accent-contrast)" : "#b91c1c",
                    fontWeight: 800,
                  }}
                />
              </Box>

              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(3, minmax(0, 1fr))" } }}>
                <MetricTile label="Registered tools" value={health.registered_tools ?? 0} />
                <MetricTile label="Verified tools" value={health.verified_tools ?? 0} />
                <MetricTile label="Pending review" value={health.pending_review ?? 0} />
              </Box>
            </Box>

            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <SignalTile label="Security components" value={`${okComponents}/${componentCount}`} detail={attentionComponents ? `${attentionComponents} need attention` : "All reported operational"} tone={attentionComponents ? "warn" : "ok"} />
              <SignalTile label="Federation peers" value={peerCount} detail={peerCount ? "Trust federation connected" : "No peers configured"} />
              <SignalTile label="Revocations" value={revocationCount} detail={revocationCount ? "Review revoked certificates" : "All tools in good standing"} tone={revocationCount ? "warn" : "ok"} />
              <SignalTile label="Server" value={health.server ?? "registry"} detail={health.timestamp ?? "No timestamp"} />
            </Box>
          </Box>

          <Divider />

          {componentCount > 0 ? (
            <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gap: 2 }}>
              <SectionHeader title="Security components" detail={`${componentCount} reported components`} />
              <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "repeat(3, minmax(0, 1fr))" } }}>
                {Object.entries(components).map(([key, status]) => {
                  const info = PILLAR_COMPONENTS[key];
                  return (
                    <Link key={key} href={info?.href ?? "/registry/health"} style={{ textDecoration: "none" }}>
                      <Box
                        sx={{
                          p: 1.75,
                          minHeight: 82,
                          borderRadius: 3,
                          border: "1px solid var(--app-border)",
                          bgcolor: "var(--app-control-bg)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 1.5,
                          transition: "background-color 120ms ease, border-color 120ms ease, transform 120ms ease",
                          "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-accent)", transform: "translateY(-1px)" },
                        }}
                      >
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontSize: 13, fontWeight: 800, color: "var(--app-fg)" }}>
                            {info?.label ?? key}
                          </Typography>
                          <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                            {status === "ok" ? "Operational" : status}
                          </Typography>
                        </Box>
                        <StatusDot ok={status === "ok"} />
                      </Box>
                    </Link>
                  );
                })}
              </Box>
            </Box>
          ) : null}

          <Divider />

          <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
            {federationData && !federationData.error ? (
              <OperationalPanel title="Federation peers" badge={`${peerCount} peers`}>
                {federationData.peers && federationData.peers.length > 0 ? (
                  <Box sx={{ display: "grid", gap: 1 }}>
                    {federationData.peers.map((peer) => (
                      <Box key={peer.peer_id} sx={{ p: 1.5, borderRadius: 2.5, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
                        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1.5 }}>
                          <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)", wordBreak: "break-word" }}>
                            {peer.peer_id}
                          </Typography>
                          <Chip size="small" label={peer.status} sx={{ bgcolor: peer.status === "active" ? "var(--app-control-active-bg)" : "rgba(100, 116, 139, 0.14)", color: "var(--app-muted)", fontWeight: 700 }} />
                        </Box>
                        <Typography sx={{ mt: 0.75, fontSize: 11, color: "var(--app-muted)", wordBreak: "break-word" }}>
                          {peer.endpoint}
                        </Typography>
                        <Typography sx={{ mt: 0.75, fontSize: 11, color: "var(--app-muted)" }}>
                          Trust {typeof peer.trust_score === "number" ? peer.trust_score.toFixed(1) : "-"} / Last seen {peer.last_seen}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                ) : (
                  <EmptyPanel title="No federation peers configured" message="This registry is running as a standalone trust domain." />
                )}
              </OperationalPanel>
            ) : null}

            {revocationsData && !revocationsData.error ? (
              <OperationalPanel title="Certificate revocations" badge={`${revocationCount} entries`}>
                {revocationsData.entries && revocationsData.entries.length > 0 ? (
                  <Box sx={{ display: "grid", gap: 1 }}>
                    {revocationsData.entries.map((entry, index) => (
                      <Box key={`${entry.tool_name}-${index}`} sx={{ p: 1.5, borderRadius: 2.5, border: "1px solid rgba(239, 68, 68, 0.28)", bgcolor: "rgba(239, 68, 68, 0.08)" }}>
                        <Typography sx={{ fontSize: 12, fontWeight: 800, color: "#b91c1c" }}>
                          {entry.tool_name}
                        </Typography>
                        <Typography sx={{ mt: 0.75, fontSize: 11, color: "var(--app-muted)" }}>
                          {entry.reason}
                        </Typography>
                        <Typography sx={{ mt: 0.75, fontSize: 10, color: "var(--app-muted)" }}>
                          Revoked by {entry.revoked_by} on {entry.revoked_at}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                ) : (
                  <EmptyPanel title="No certificate revocations" message="No tools are currently blocked by the revocation list." />
                )}
              </OperationalPanel>
            ) : null}
          </Box>

          <Divider />

          <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gap: 2 }}>
            <SectionHeader title="Security pillars" detail="Jump into each guardrail workspace" />
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "repeat(5, minmax(0, 1fr))" } }}>
              {SECURITY_PILLARS.map((pillar) => (
                <Link key={pillar.href} href={pillar.href} style={{ textDecoration: "none" }}>
                  <Box
                    sx={{
                      minHeight: 132,
                      p: 2,
                      borderRadius: 3,
                      border: "1px solid var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                      display: "grid",
                      alignContent: "space-between",
                      gap: 1.5,
                      "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-accent)" },
                    }}
                  >
                    <Typography sx={{ fontSize: 13, fontWeight: 850, color: "var(--app-fg)" }}>
                      {pillar.label}
                    </Typography>
                    <Typography sx={{ fontSize: 11, lineHeight: 1.55, color: "var(--app-muted)" }}>
                      {pillar.desc}
                    </Typography>
                  </Box>
                </Link>
              ))}
            </Box>
          </Box>

          <Divider />

          <Box sx={{ px: { xs: 2.5, md: 3 }, py: 1.75, display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1.5, bgcolor: "var(--app-control-bg)" }}>
            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
              Registry updated: {health.timestamp ?? "-"}
            </Typography>
            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
              Security updated: {securityHealth?.timestamp ?? "-"}
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

function MetricTile({ label, value }: { label: string; value: number | string }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2.5,
        bgcolor: "var(--app-surface)",
        border: "1px solid var(--app-border)",
      }}
    >
      <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>{label}</Typography>
      <Typography sx={{ mt: 0.5, fontSize: 22, lineHeight: 1, fontWeight: 850, color: "var(--app-fg)" }}>
        {value}
      </Typography>
    </Box>
  );
}

function SignalTile({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: number | string;
  detail: string;
  tone?: "ok" | "warn" | "neutral";
}) {
  const color = tone === "ok" ? "var(--app-accent)" : tone === "warn" ? "#d97706" : "var(--app-muted)";
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-surface)",
        display: "grid",
        gap: 0.75,
      }}
    >
      <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 20, lineHeight: 1, fontWeight: 850, color }}>
        {value}
      </Typography>
      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
        {detail}
      </Typography>
    </Box>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <Box
      sx={{
        width: 12,
        height: 12,
        borderRadius: "50%",
        bgcolor: ok ? "var(--app-accent)" : "#ef4444",
        boxShadow: ok ? "0 0 0 4px var(--app-control-active-bg)" : "0 0 0 4px rgba(239, 68, 68, 0.12)",
        flex: "0 0 auto",
      }}
    />
  );
}

function SectionHeader({ title, detail }: { title: string; detail: string }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
      <Typography sx={sectionTitleSx}>{title}</Typography>
      <Chip size="small" label={detail} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
    </Box>
  );
}

function OperationalPanel({
  title,
  badge,
  children,
}: {
  title: string;
  badge: string;
  children: ReactNode;
}) {
  return (
    <Box
      component="section"
      sx={{
        border: "1px solid var(--app-border)",
        borderRadius: 3,
        bgcolor: "var(--app-surface)",
        overflow: "hidden",
      }}
    >
      <Box sx={{ p: 2, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5, borderBottom: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
        <Typography sx={sectionTitleSx}>{title}</Typography>
        <Chip size="small" label={badge} sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700 }} />
      </Box>
      <Box sx={{ p: 2 }}>{children}</Box>
    </Box>
  );
}

function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <Box
      sx={{
        p: 3,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        textAlign: "center",
      }}
    >
      <Typography sx={{ fontSize: 13, fontWeight: 800, color: "var(--app-fg)" }}>{title}</Typography>
      <Typography sx={{ mt: 0.75, fontSize: 12, color: "var(--app-muted)" }}>{message}</Typography>
    </Box>
  );
}
