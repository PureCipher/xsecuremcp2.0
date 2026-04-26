"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { CertificationBadge, EmptyState, KeyValuePanel } from "@/components/security";
import type {
  PublisherSummary,
  RegistryToolListing,
  ServerConsentGovernanceResponse,
  ServerConsentToolBinding,
  ServerContractGovernanceResponse,
  ServerContractToolBinding,
  ServerLedgerGovernanceResponse,
  ServerLedgerToolBinding,
  ServerObservabilityResponse,
  ServerObservabilityToolBinding,
  ServerOverridesGovernanceResponse,
  ServerOverrideToolBinding,
  ServerPolicyGovernanceResponse,
  ServerPolicyToolBinding,
} from "@/lib/registryClient";
import { Box, Chip, Stack, Typography } from "@mui/material";

type TabKey = "overview" | "tools" | "governance" | "observability";

export function ServerDetailTabs({
  serverId,
  summary,
  listings,
  policyGovernance,
  contractGovernance,
  consentGovernance,
  ledgerGovernance,
  overridesGovernance,
  observability,
}: {
  serverId: string;
  summary: PublisherSummary;
  listings: RegistryToolListing[];
  // Each control plane gets its own optional payload so consumers
  // that don't fetch a particular plane still type-check; the
  // matching panel falls back to an "unavailable" empty state.
  // Iter1: policyGovernance     — Governance / Policy Kernel
  // Iter2: contractGovernance   — Governance / Contract Broker
  // Iter3: consentGovernance    — Governance / Consent Graph
  // Iter4: ledgerGovernance     — Governance / Provenance Ledger
  // Iter5: overridesGovernance  — Governance / Overrides
  // Iter6: observability        — Observability / Reflexive Core
  policyGovernance?: ServerPolicyGovernanceResponse | null;
  contractGovernance?: ServerContractGovernanceResponse | null;
  consentGovernance?: ServerConsentGovernanceResponse | null;
  ledgerGovernance?: ServerLedgerGovernanceResponse | null;
  overridesGovernance?: ServerOverridesGovernanceResponse | null;
  observability?: ServerObservabilityResponse | null;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const toolCount = useMemo(() => listings.length, [listings]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["overview", "Overview"],
            ["tools", "Tools"],
            ["governance", "Governance"],
            ["observability", "Observability"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key)}
            className={`rounded-full border border-[--app-border] px-4 py-2 text-xs font-semibold transition ${
              activeTab === key
                ? "bg-[--app-accent] border-[--app-accent] text-[--app-accent-contrast]"
                : "bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "overview" ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <div className="grid gap-4 md:grid-cols-2">
            <KeyValuePanel
              title="Server snapshot"
              entries={[
                { label: "server_id", value: serverId },
                { label: "display_name", value: summary.display_name ?? "—" },
                {
                  label: "tools_count",
                  value: toolCount.toString(),
                },
                {
                  label: "drift_status",
                  value: deriveDriftStatusLabel(observability ?? null),
                },
              ]}
            />
            <KeyValuePanel
              title="Control planes attached"
              entries={[
                {
                  label: "Policy Kernel",
                  value: policyGovernance?.registry_policy?.available
                    ? `v${policyGovernance.registry_policy.current_version ?? "?"}`
                    : "not configured",
                },
                {
                  label: "Contract Broker",
                  value: contractGovernance?.broker?.available
                    ? `${contractGovernance.broker.active_contract_count ?? 0} active`
                    : "not configured",
                },
                {
                  label: "Consent Graph",
                  value: consentGovernance?.consent_graph?.available
                    ? `${consentGovernance.consent_graph.active_edge_count ?? 0} active edges`
                    : "not configured",
                },
                {
                  label: "Provenance Ledger",
                  value: ledgerGovernance?.ledger?.available
                    ? `${ledgerGovernance.ledger.record_count ?? 0} records`
                    : "not configured",
                },
                {
                  label: "Reflexive Core",
                  value: observability?.analyzer?.available
                    ? `${observability.analyzer.total_drift_count ?? 0} drift events`
                    : "not configured",
                },
              ]}
            />
          </div>
        </div>
      ) : null}

      {activeTab === "tools" ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Tools exposed by this server
          </Typography>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Tool inventory is sourced from the server&apos;s publisher profile in the registry backend.
          </Typography>

          <div className="mt-6">
            {listings.length === 0 ? (
              <EmptyState
                title="No tools loaded yet"
                message="Once the publisher has live verified tools, they will show up here."
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {listings.map((tool) => (
                  <Link
                    key={tool.tool_name}
                    href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                    className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring] transition hover:border-[--app-accent] hover:ring-[--app-accent]"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <div>
                        <Typography variant="body2" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                          {tool.display_name ?? tool.tool_name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                          {tool.tool_name}
                        </Typography>
                      </div>
                      <CertificationBadge level={tool.certification_level} />
                    </div>
                    <Typography variant="caption" sx={{ color: "var(--app-muted)", lineHeight: 1.6 }}>
                      {tool.description ?? "No description provided."}
                    </Typography>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "governance" ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Governance association
          </Typography>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Effective control-plane bindings for this server and its tools.
            Iteration 1 (Policy Kernel) is live; Contract Broker, Consent
            Graph, and Ledger panels are next up.
          </Typography>

          <PolicyKernelPanel governance={policyGovernance ?? null} />

          <ContractBrokerPanel governance={contractGovernance ?? null} />

          <ConsentGraphPanel governance={consentGovernance ?? null} />

          <ProvenanceLedgerPanel governance={ledgerGovernance ?? null} />

          <OverridesPanel governance={overridesGovernance ?? null} />
        </div>
      ) : null}

      {activeTab === "observability" ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Observability
          </Typography>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Behavioral drift signals from the Reflexive Core, scoped
            to this server&apos;s tools. Powered by{" "}
            <code>BehavioralAnalyzer</code> at the engine layer.
          </Typography>

          <ReflexiveCorePanel observability={observability ?? null} />
        </div>
      ) : null}
    </div>
  );
}

// ── Policy Kernel panel ────────────────────────────────────────────
//
// Renders the registry-wide policy version + each listing's
// effective binding. Backed by ``GET /registry/servers/{id}
// /governance/policy`` — see ``PureCipherRegistry
// .get_server_policy_governance`` for the contract.

function PolicyKernelPanel({
  governance,
}: {
  governance: ServerPolicyGovernanceResponse | null;
}) {
  // ``governance.error`` is set when the backend explicitly returns
  // an error envelope (e.g. publisher not found). ``null`` is what
  // ``parseJson`` returns on transport-level failures. Both cases
  // need a clear empty state — silently rendering nothing would let
  // the page imply governance is fine when it's actually broken.
  if (!governance || governance.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Policy Kernel data unavailable"
          message={
            governance?.error ??
            "We couldn't load the registry's policy state for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const registry = governance.registry_policy;
  const perTool = governance.per_tool_policies ?? [];
  const summary = governance.summary ?? {
    tool_count: perTool.length,
    inherited_count: 0,
    overridden_count: 0,
  };
  const policyKernelHref = governance.links?.policy_kernel_url ?? "/registry/policy";

  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Policy Kernel
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {registry?.available
              ? `${registry.policy_set_id ?? "registry policy set"} · v${registry.current_version ?? "?"}` +
                (registry.version_count != null ? ` of ${registry.version_count}` : "")
              : "Registry policy engine not configured."}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          {registry?.available && registry.current_version != null ? (
            <Chip
              size="small"
              label={`Active v${registry.current_version}`}
              sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
          {registry?.fail_closed ? (
            <Chip
              size="small"
              label="fail-closed"
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
          <Chip
            size="small"
            label={`${summary.inherited_count} inherit`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
          <Chip
            size="small"
            label={`${summary.overridden_count} per-tool`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
        </Stack>
      </Box>

      {registry?.available ? (
        <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
          <span>
            Providers: <strong style={{ color: "var(--app-fg)" }}>{registry.provider_count ?? 0}</strong>
          </span>
          <span>
            Evaluations: <strong style={{ color: "var(--app-fg)" }}>{registry.evaluation_count ?? 0}</strong>
          </span>
          <span>
            Denies: <strong style={{ color: "var(--app-fg)" }}>{registry.deny_count ?? 0}</strong>
          </span>
        </Box>
      ) : null}

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool bindings
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools to govern yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <PolicyBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      <Box sx={{ mt: 2.5 }}>
        <Link href={policyKernelHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open Policy Kernel →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

// ── Contract Broker panel ──────────────────────────────────────────
//
// Renders the registry's Context Broker availability + per-tool
// agent-contract bindings. Backed by ``GET /registry/servers/{id}
// /governance/contracts`` — see ``PureCipherRegistry
// .get_server_contract_governance``.

function ContractBrokerPanel({
  governance,
}: {
  governance: ServerContractGovernanceResponse | null;
}) {
  if (!governance || governance.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Contract Broker data unavailable"
          message={
            governance?.error ??
            "We couldn't load the Context Broker state for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const broker = governance.broker;
  const perTool = governance.per_tool_contracts ?? [];
  const summary = governance.summary ?? {
    tool_count: perTool.length,
    contracted_count: 0,
    uncontracted_count: 0,
  };
  const brokerHref = governance.links?.contract_broker_url ?? "/registry/contracts";

  // The broker's ``available`` flag drives whether the rest of the
  // block carries real data. When it's false we render a clear,
  // operator-actionable empty state instead of stub-style fields —
  // this is the most common case in real deployments because the
  // Context Broker is opt-in on the registry's SecurityConfig.
  if (!broker?.available) {
    return (
      <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
        <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Contract Broker
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
              The Context Broker is not enabled on this registry.
            </Typography>
          </Box>
          <Chip
            size="small"
            label="not configured"
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
        </Box>
        <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>
          {broker?.reason ??
            "Operators can opt in by passing SecurityConfig(contracts=ContractConfig(...)) when constructing the registry."}{" "}
          Once enabled, this panel surfaces broker config, active contract counts, and which agents have contracts that reference each of your tools.
        </Typography>
      </div>
    );
  }

  // Format duration values defensively — broker.contract_duration_seconds
  // could be null when an operator wires the broker by hand.
  const formatSeconds = (value: number | null | undefined): string => {
    if (value == null) return "—";
    if (value % 3600 === 0) return `${value / 3600}h`;
    if (value % 60 === 0) return `${value / 60}m`;
    return `${value}s`;
  };

  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Contract Broker
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {broker.broker_id ?? "default"}
            {broker.server_id ? ` · server ${broker.server_id}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={`${broker.active_contract_count ?? 0} active`}
            sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700, fontSize: 11 }}
          />
          {broker.default_term_count ? (
            <Chip
              size="small"
              label={`${broker.default_term_count} default term${broker.default_term_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
          <Chip
            size="small"
            label={`${summary.contracted_count} contracted`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
          <Chip
            size="small"
            label={`${summary.uncontracted_count} uncontracted`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
        </Stack>
      </Box>

      <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
        <span>
          Max rounds: <strong style={{ color: "var(--app-fg)" }}>{broker.max_rounds ?? "—"}</strong>
        </span>
        <span>
          Contract duration: <strong style={{ color: "var(--app-fg)" }}>{formatSeconds(broker.contract_duration_seconds)}</strong>
        </span>
        <span>
          Session timeout: <strong style={{ color: "var(--app-fg)" }}>{formatSeconds(broker.session_timeout_seconds)}</strong>
        </span>
        <span>
          Sessions: <strong style={{ color: "var(--app-fg)" }}>{broker.negotiation_session_count ?? 0}</strong>
        </span>
        <span>
          Exchange-log entries: <strong style={{ color: "var(--app-fg)" }}>{broker.exchange_log_entry_count ?? 0}</strong>
        </span>
      </Box>

      {broker.default_terms && broker.default_terms.length > 0 ? (
        <Box sx={{ mt: 2 }}>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Default terms applied to every contract
          </Typography>
          <Box sx={{ mt: 1, display: "grid", gap: 0.75 }}>
            {broker.default_terms.map((term, idx) => (
              <Box
                key={term.term_id ?? idx}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1.25,
                  p: 1,
                  borderRadius: 2,
                  bgcolor: "var(--app-surface)",
                  border: "1px solid var(--app-border)",
                }}
              >
                <Chip
                  size="small"
                  label={term.term_type ?? "custom"}
                  sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700, fontSize: 10, fontFamily: "var(--font-geist-mono), monospace" }}
                />
                {term.required ? (
                  <Chip
                    size="small"
                    label="required"
                    sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700, fontSize: 10 }}
                  />
                ) : null}
                <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                  {term.description ?? "(no description)"}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      ) : null}

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool contract bindings
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          Contracts are agent ↔ server. A tool shows as {`"contracted"`} when at least one active contract carries a term whose constraint references it.
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools to contract over yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <ContractBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      <Box sx={{ mt: 2.5 }}>
        <Link href={brokerHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open Contract Broker →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

function ContractBindingRow({ row }: { row: ServerContractToolBinding }) {
  const isContracted = row.binding_source === "agent_contracts";
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography
            noWrap
            sx={{
              fontSize: 11,
              color: "var(--app-muted)",
              fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            }}
          >
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
            {row.status && row.status !== "published" ? ` · ${row.status}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={
              isContracted
                ? `${row.matching_contract_count} contract${row.matching_contract_count === 1 ? "" : "s"}`
                : "no contracts"
            }
            sx={{
              bgcolor: isContracted ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: isContracted ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
        </Stack>
      </Box>
      {isContracted && row.matching_agents.length > 0 ? (
        <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {row.matching_agents.slice(0, 5).map((agent) => (
            <Chip
              key={agent}
              size="small"
              label={agent}
              sx={{
                bgcolor: "var(--app-control-bg)",
                color: "var(--app-muted)",
                fontFamily: "var(--font-geist-mono), monospace",
                fontSize: 10,
              }}
            />
          ))}
          {row.matching_contract_count > row.matching_agents.length ? (
            <Chip
              size="small"
              label={`+${row.matching_contract_count - row.matching_agents.length} more`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontSize: 10 }}
            />
          ) : null}
        </Box>
      ) : null}
    </Link>
  );
}

// ── Consent Graph panel ────────────────────────────────────────────
//
// Renders the Consent Graph topology + per-tool consent posture.
// Backed by ``GET /registry/servers/{id}/governance/consent`` — see
// ``PureCipherRegistry.get_server_consent_governance`` in
// src/purecipher/registry.py.
//
// Two orthogonal axes per tool:
// * ``binding_source`` (consent_required | consent_optional) reflects
//   the LISTING's manifest-declared posture — deterministic.
// * ``graph_grant_count`` reflects active consent edges in the graph
//   that reference this tool — best-effort heuristic over scopes,
//   metadata, and node IDs.

function ConsentGraphPanel({
  governance,
}: {
  governance: ServerConsentGovernanceResponse | null;
}) {
  if (!governance || governance.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Consent Graph data unavailable"
          message={
            governance?.error ??
            "We couldn't load the Consent Graph state for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const graph = governance.consent_graph;
  const federation = governance.federation;
  const perTool = governance.per_tool_consent ?? [];
  const summary = governance.summary ?? {
    tool_count: perTool.length,
    requires_consent_count: 0,
    with_grants_count: 0,
    without_grants_count: 0,
  };
  const consentHref = governance.links?.consent_graph_url ?? "/registry/consent";

  // The graph's ``available`` flag drives whether the topology block
  // carries real data. The per-tool block ALWAYS renders because
  // the manifest-side ``requires_consent`` signal is independent of
  // graph wiring — a tool can declare consent_required without the
  // graph being configured at all.
  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Consent Graph
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {graph?.available
              ? `${graph.graph_id ?? "consent graph"} · ${graph.active_edge_count ?? 0} active edge${(graph.active_edge_count ?? 0) === 1 ? "" : "s"}`
              : "The Consent Graph is not enabled on this registry."}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={graph?.available ? "graph enabled" : "graph disabled"}
            sx={{
              bgcolor: graph?.available ? "var(--app-control-active-bg)" : "var(--app-surface)",
              color: graph?.available ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: graph?.available ? undefined : "1px solid var(--app-border)",
            }}
          />
          <Chip
            size="small"
            label={`${summary.requires_consent_count} require consent`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
          <Chip
            size="small"
            label={`${summary.with_grants_count} with grants`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
        </Stack>
      </Box>

      {graph?.available ? (
        <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
          <span>
            Nodes: <strong style={{ color: "var(--app-fg)" }}>{graph.node_count ?? 0}</strong>
          </span>
          <span>
            Edges: <strong style={{ color: "var(--app-fg)" }}>{graph.edge_count ?? 0}</strong>
          </span>
          <span>
            Active: <strong style={{ color: "var(--app-fg)" }}>{graph.active_edge_count ?? 0}</strong>
          </span>
          <span>
            Audit entries: <strong style={{ color: "var(--app-fg)" }}>{graph.audit_entry_count ?? 0}</strong>
          </span>
        </Box>
      ) : (
        <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>
          {graph?.reason ??
            "Operators can opt in by passing SecurityConfig(consent=ConsentConfig(...)) when constructing the registry."}{" "}
          Per-tool consent posture below is still derived from each listing&apos;s manifest.
        </Typography>
      )}

      {graph?.available && graph.node_counts_by_type ? (
        <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
          {(Object.entries(graph.node_counts_by_type) as [string, number][])
            .filter(([, count]) => count > 0)
            .map(([type, count]) => (
              <Chip
                key={type}
                size="small"
                label={`${type}: ${count}`}
                sx={{
                  bgcolor: "var(--app-surface)",
                  color: "var(--app-muted)",
                  fontFamily: "var(--font-geist-mono), monospace",
                  fontSize: 10,
                  border: "1px solid var(--app-border)",
                }}
              />
            ))}
          {Object.values(graph.node_counts_by_type).every(
            (count) => count === 0,
          ) ? (
            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
              Graph has no nodes yet.
            </Typography>
          ) : null}
        </Box>
      ) : null}

      {/* Federation block — currently always available=false until
          we plumb FederatedConsentGraph through the security context.
          Surfaced here so the cross-jurisdiction story is visible
          on the page and a future iteration can light it up
          without a new visual block. */}
      <Box sx={{ mt: 3, p: 2, borderRadius: 2, bgcolor: "var(--app-surface)", border: "1px solid var(--app-border)" }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5, flexWrap: "wrap" }}>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Federation
          </Typography>
          <Chip
            size="small"
            label={federation?.available ? "federated" : "not federated"}
            sx={{
              bgcolor: federation?.available ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: federation?.available ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: federation?.available ? undefined : "1px solid var(--app-border)",
            }}
          />
        </Box>
        {federation?.available ? (
          <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
            {federation.institution_id ? (
              <span>
                Institution: <strong style={{ color: "var(--app-fg)" }}>{federation.institution_id}</strong>
              </span>
            ) : null}
            <span>
              Jurisdictions: <strong style={{ color: "var(--app-fg)" }}>{federation.jurisdiction_count ?? 0}</strong>
            </span>
            <span>
              Peers: <strong style={{ color: "var(--app-fg)" }}>{federation.peer_count ?? 0}</strong>
            </span>
          </Box>
        ) : (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            {federation?.reason ??
              "Federated consent isn't surfaced on this registry yet."}
          </Typography>
        )}
      </Box>

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool consent posture
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          {`"requires consent" reflects the listing's manifest. Graph grants are best-effort matches across active consent edges.`}
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools to record consent for yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <ConsentBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      <Box sx={{ mt: 2.5 }}>
        <Link href={consentHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open Consent Graph →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

function ConsentBindingRow({ row }: { row: ServerConsentToolBinding }) {
  const requiresConsent = row.binding_source === "consent_required";
  const hasGrants = row.graph_grant_count > 0;
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography
            noWrap
            sx={{
              fontSize: 11,
              color: "var(--app-muted)",
              fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            }}
          >
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
            {row.status && row.status !== "published" ? ` · ${row.status}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={requiresConsent ? "requires consent" : "consent optional"}
            sx={{
              bgcolor: requiresConsent ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: requiresConsent ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
          <Chip
            size="small"
            label={
              hasGrants
                ? `${row.graph_grant_count} grant${row.graph_grant_count === 1 ? "" : "s"}`
                : "no grants"
            }
            sx={{
              bgcolor: hasGrants ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: hasGrants ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
        </Stack>
      </Box>
      {hasGrants && row.grant_sources.length > 0 ? (
        <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {row.grant_sources.slice(0, 5).map((source) => (
            <Chip
              key={source}
              size="small"
              label={source}
              sx={{
                bgcolor: "var(--app-control-bg)",
                color: "var(--app-muted)",
                fontFamily: "var(--font-geist-mono), monospace",
                fontSize: 10,
              }}
            />
          ))}
          {row.graph_grant_count > row.grant_sources.length ? (
            <Chip
              size="small"
              label={`+${row.graph_grant_count - row.grant_sources.length} more`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontSize: 10 }}
            />
          ) : null}
        </Box>
      ) : null}
    </Link>
  );
}

// ── Provenance Ledger panel ────────────────────────────────────────
//
// Renders the registry-wide ledger metrics + per-tool ledger
// bindings (proxy-mode listings get a dedicated ledger at gateway
// mount; catalog-only listings have no registry-attached ledger).
// Backed by ``GET /registry/servers/{id}/governance/ledger`` — see
// ``PureCipherRegistry.get_server_ledger_governance``.

function ProvenanceLedgerPanel({
  governance,
}: {
  governance: ServerLedgerGovernanceResponse | null;
}) {
  if (!governance || governance.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Provenance Ledger data unavailable"
          message={
            governance?.error ??
            "We couldn't load the Provenance Ledger state for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const ledger = governance.ledger;
  const perTool = governance.per_tool_ledger ?? [];
  const summary = governance.summary ?? {
    tool_count: perTool.length,
    with_proxy_ledger_count: 0,
    with_central_records_count: 0,
    total_central_records_for_tools: 0,
  };
  const ledgerHref =
    governance.links?.provenance_ledger_url ?? "/registry/provenance";

  // Helper: short-form root hash.
  const shortHash = (hash: string | undefined): string => {
    if (!hash) return "—";
    if (hash.length <= 14) return hash;
    return `${hash.slice(0, 7)}…${hash.slice(-7)}`;
  };

  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Provenance Ledger
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {ledger?.available
              ? `${ledger.ledger_id ?? "registry ledger"} · ${ledger.record_count ?? 0} record${(ledger.record_count ?? 0) === 1 ? "" : "s"}`
              : "The registry-wide Provenance Ledger is not enabled."}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={ledger?.available ? "ledger enabled" : "ledger disabled"}
            sx={{
              bgcolor: ledger?.available
                ? "var(--app-control-active-bg)"
                : "var(--app-surface)",
              color: ledger?.available ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: ledger?.available ? undefined : "1px solid var(--app-border)",
            }}
          />
          <Chip
            size="small"
            label={`${summary.with_proxy_ledger_count} per-listing`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
          <Chip
            size="small"
            label={`${summary.total_central_records_for_tools} central record${summary.total_central_records_for_tools === 1 ? "" : "s"}`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
        </Stack>
      </Box>

      {ledger?.available ? (
        <>
          <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
            <span>
              Records: <strong style={{ color: "var(--app-fg)" }}>{ledger.record_count ?? 0}</strong>
            </span>
            <span>
              Root: <strong style={{ color: "var(--app-fg)", fontFamily: "var(--font-geist-mono), monospace" }}>{shortHash(ledger.root_hash)}</strong>
            </span>
            {ledger.scheme_name ? (
              <span>
                Scheme: <strong style={{ color: "var(--app-fg)" }}>{ledger.scheme_name}</strong>
              </span>
            ) : null}
            {ledger.latest_record_at ? (
              <span>
                Last entry: <strong style={{ color: "var(--app-fg)" }}>{new Date(ledger.latest_record_at).toLocaleString()}</strong>
                {ledger.latest_record_action ? ` · ${ledger.latest_record_action}` : ""}
                {ledger.latest_record_resource_id ? ` · ${ledger.latest_record_resource_id}` : ""}
              </span>
            ) : (
              <span>
                No entries recorded yet.
              </span>
            )}
          </Box>
        </>
      ) : (
        <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>
          {ledger?.reason ??
            "Operators can opt in by passing SecurityConfig(provenance=ProvenanceConfig(...)) when constructing the registry."}{" "}
          Per-tool bindings below still show which of your listings get a dedicated proxy ledger at gateway mount, regardless of whether the central ledger is wired.
        </Typography>
      )}

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool ledger bindings
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          Proxy-mode listings get a dedicated ledger at gateway mount. Catalog-only listings bypass the registry. {ledger?.available ? "Central record counts come from the registry-wide ledger." : ""}
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools to record provenance for yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <LedgerBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      <Box sx={{ mt: 2.5 }}>
        <Link href={ledgerHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open Provenance Ledger →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

function LedgerBindingRow({ row }: { row: ServerLedgerToolBinding }) {
  const isProxy = row.binding_source === "proxy_ledger";
  const hasCentralRecords = row.central_record_count > 0;
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography
            noWrap
            sx={{
              fontSize: 11,
              color: "var(--app-muted)",
              fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            }}
          >
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
            {row.status && row.status !== "published" ? ` · ${row.status}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={isProxy ? "per-listing ledger" : "no ledger"}
            sx={{
              bgcolor: isProxy ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: isProxy ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
          {hasCentralRecords ? (
            <Chip
              size="small"
              label={`${row.central_record_count} central record${row.central_record_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
        </Stack>
      </Box>
      {isProxy && row.expected_ledger_id ? (
        <Typography
          sx={{
            mt: 1,
            fontSize: 11,
            color: "var(--app-muted)",
            fontFamily: "var(--font-geist-mono), monospace",
          }}
        >
          ledger_id: {row.expected_ledger_id}
        </Typography>
      ) : null}
      {hasCentralRecords && row.latest_central_record_at ? (
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          Last activity:{" "}
          <strong style={{ color: "var(--app-fg)" }}>
            {new Date(row.latest_central_record_at).toLocaleString()}
          </strong>
          {row.latest_central_record_action
            ? ` · ${row.latest_central_record_action}`
            : ""}
        </Typography>
      ) : null}
    </Link>
  );
}

// ── Overrides panel ────────────────────────────────────────────────
//
// Rolls up operator/moderator interventions across this server's
// tools: status overrides (PENDING_REVIEW / SUSPENDED / etc.),
// the moderation log of every approve/reject/suspend decision,
// yanked versions, and a cross-reference flag for per-listing
// policy overrides surfaced in detail on the Policy Kernel panel.
// Backed by ``GET /registry/servers/{id}/governance/overrides`` —
// see ``PureCipherRegistry.get_server_overrides_governance``.

function statusChipColors(status: string): {
  bg: string;
  fg: string;
  border?: string;
} {
  switch (status) {
    case "published":
      return {
        bg: "var(--app-control-active-bg)",
        fg: "var(--app-fg)",
      };
    case "pending_review":
      return {
        bg: "rgba(253, 230, 138, 0.4)",
        fg: "#92400e",
      };
    case "suspended":
    case "rejected":
      return {
        bg: "rgba(244, 63, 94, 0.18)",
        fg: "#b91c1c",
      };
    case "deprecated":
      return {
        bg: "var(--app-control-bg)",
        fg: "var(--app-muted)",
        border: "1px solid var(--app-border)",
      };
    default:
      return {
        bg: "var(--app-control-bg)",
        fg: "var(--app-muted)",
        border: "1px solid var(--app-border)",
      };
  }
}

function OverridesPanel({
  governance,
}: {
  governance: ServerOverridesGovernanceResponse | null;
}) {
  if (!governance || governance.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Overrides data unavailable"
          message={
            governance?.error ??
            "We couldn't load the overrides view for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const summary = governance.summary ?? {
    tool_count: 0,
    draft_count: 0,
    pending_review_count: 0,
    published_count: 0,
    suspended_count: 0,
    deprecated_count: 0,
    rejected_count: 0,
    yanked_version_count: 0,
    policy_override_count: 0,
    open_moderation_actions: 0,
  };
  const perTool = governance.per_tool_overrides ?? [];
  const recent = governance.recent_moderation_decisions ?? [];
  const queueHref =
    governance.links?.moderation_queue_url ?? "/registry/review";

  const hasAnyOverride =
    summary.pending_review_count +
      summary.suspended_count +
      summary.deprecated_count +
      summary.rejected_count +
      summary.yanked_version_count +
      summary.policy_override_count >
    0;

  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Overrides
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {hasAnyOverride
              ? "Operator interventions across this server's tools."
              : "No operator interventions recorded for this server's tools."}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={`${summary.open_moderation_actions} pending`}
            sx={{
              bgcolor:
                summary.open_moderation_actions > 0
                  ? "rgba(253, 230, 138, 0.4)"
                  : "var(--app-surface)",
              color:
                summary.open_moderation_actions > 0
                  ? "#92400e"
                  : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: summary.open_moderation_actions > 0 ? undefined : "1px solid var(--app-border)",
            }}
          />
          {summary.suspended_count > 0 ? (
            <Chip
              size="small"
              label={`${summary.suspended_count} suspended`}
              sx={{ bgcolor: "rgba(244, 63, 94, 0.18)", color: "#b91c1c", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
          {summary.policy_override_count > 0 ? (
            <Chip
              size="small"
              label={`${summary.policy_override_count} policy override${summary.policy_override_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
          {summary.yanked_version_count > 0 ? (
            <Chip
              size="small"
              label={`${summary.yanked_version_count} yanked version${summary.yanked_version_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
        </Stack>
      </Box>

      <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
        <span>
          Total tools: <strong style={{ color: "var(--app-fg)" }}>{summary.tool_count}</strong>
        </span>
        <span>
          Published: <strong style={{ color: "var(--app-fg)" }}>{summary.published_count}</strong>
        </span>
        <span>
          Pending review: <strong style={{ color: "var(--app-fg)" }}>{summary.pending_review_count}</strong>
        </span>
        {summary.deprecated_count > 0 ? (
          <span>
            Deprecated: <strong style={{ color: "var(--app-fg)" }}>{summary.deprecated_count}</strong>
          </span>
        ) : null}
        {summary.rejected_count > 0 ? (
          <span>
            Rejected: <strong style={{ color: "var(--app-fg)" }}>{summary.rejected_count}</strong>
          </span>
        ) : null}
      </Box>

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool overrides
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <OverrideBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      {recent.length > 0 ? (
        <Box sx={{ mt: 3 }}>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Recent moderation decisions
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
            Most-recent first across all of this server&apos;s tools, capped at the last 10.
          </Typography>
          <Box sx={{ mt: 1, display: "grid", gap: 0.75 }}>
            {recent.slice(0, 10).map((decision, idx) => (
              <Box
                key={decision.decision_id ?? idx}
                sx={{
                  p: 1.25,
                  borderRadius: 2,
                  border: "1px solid var(--app-border)",
                  bgcolor: "var(--app-surface)",
                  display: "grid",
                  gap: 0.5,
                }}
              >
                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                  <Chip
                    size="small"
                    label={decision.action}
                    sx={{
                      bgcolor: "var(--app-control-bg)",
                      color: "var(--app-muted)",
                      fontWeight: 700,
                      fontSize: 10,
                      fontFamily: "var(--font-geist-mono), monospace",
                    }}
                  />
                  {decision.tool_name ? (
                    <Link
                      href={`/registry/listings/${encodeURIComponent(decision.tool_name)}`}
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        color: "var(--app-fg)",
                        textDecoration: "none",
                      }}
                    >
                      {decision.display_name ?? decision.tool_name}
                    </Link>
                  ) : null}
                  {decision.created_at ? (
                    <Typography sx={{ fontSize: 11, color: "var(--app-muted)", ml: "auto" }}>
                      {new Date(decision.created_at).toLocaleString()}
                    </Typography>
                  ) : null}
                </Box>
                {decision.reason ? (
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    {decision.reason}
                  </Typography>
                ) : null}
                {decision.moderator_id ? (
                  <Typography
                    sx={{
                      fontSize: 11,
                      color: "var(--app-muted)",
                      fontFamily: "var(--font-geist-mono), monospace",
                    }}
                  >
                    by {decision.moderator_id}
                  </Typography>
                ) : null}
              </Box>
            ))}
          </Box>
        </Box>
      ) : null}

      <Box sx={{ mt: 2.5 }}>
        <Link href={queueHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open moderation queue →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

function OverrideBindingRow({ row }: { row: ServerOverrideToolBinding }) {
  const statusColors = statusChipColors(row.status);
  const isPending = row.binding_source === "moderation_pending";
  const isModerated = row.binding_source === "moderated";
  const hasYanks = row.yanked_versions.length > 0;
  const hasPolicyOverride = row.policy_override.active;
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography
            noWrap
            sx={{
              fontSize: 11,
              color: "var(--app-muted)",
              fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            }}
          >
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={row.status}
            sx={{
              bgcolor: statusColors.bg,
              color: statusColors.fg,
              fontWeight: 700,
              fontSize: 11,
              fontFamily: "var(--font-geist-mono), monospace",
              border: statusColors.border,
            }}
          />
          {isPending ? (
            <Chip
              size="small"
              label="awaiting moderator"
              sx={{ bgcolor: "rgba(253, 230, 138, 0.4)", color: "#92400e", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
          {hasPolicyOverride ? (
            <Chip
              size="small"
              label={`policy override · ${row.policy_override.allowed_count} tool${row.policy_override.allowed_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
          {hasYanks ? (
            <Chip
              size="small"
              label={`${row.yanked_versions.length} yanked`}
              sx={{ bgcolor: "rgba(244, 63, 94, 0.18)", color: "#b91c1c", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
        </Stack>
      </Box>
      {(isPending || isModerated) && row.moderation.latest_action ? (
        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
          Last decision:{" "}
          <strong style={{ color: "var(--app-fg)" }}>{row.moderation.latest_action}</strong>
          {row.moderation.latest_reason ? ` — ${row.moderation.latest_reason}` : ""}
          {row.moderation.latest_at
            ? ` · ${new Date(row.moderation.latest_at).toLocaleString()}`
            : ""}
          {row.moderation.latest_moderator_id
            ? ` · by ${row.moderation.latest_moderator_id}`
            : ""}
        </Typography>
      ) : null}
      {hasYanks ? (
        <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {row.yanked_versions.slice(0, 5).map((v) => (
            <Chip
              key={v.version}
              size="small"
              label={
                v.yank_reason ? `v${v.version} · ${v.yank_reason}` : `v${v.version}`
              }
              sx={{
                bgcolor: "var(--app-control-bg)",
                color: "var(--app-muted)",
                fontFamily: "var(--font-geist-mono), monospace",
                fontSize: 10,
              }}
            />
          ))}
        </Box>
      ) : null}
    </Link>
  );
}

function deriveDriftStatusLabel(
  observability: ServerObservabilityResponse | null,
): string {
  if (!observability || observability.error || !observability.analyzer) {
    return "—";
  }
  const analyzer = observability.analyzer;
  if (!analyzer.available) {
    return "analyzer not configured";
  }
  const summary = observability.summary;
  if (summary) {
    if (summary.with_critical_drift_count > 0) {
      return `critical drift on ${summary.with_critical_drift_count} tool${summary.with_critical_drift_count === 1 ? "" : "s"}`;
    }
    if (summary.with_high_drift_count > 0) {
      return `high drift on ${summary.with_high_drift_count} tool${summary.with_high_drift_count === 1 ? "" : "s"}`;
    }
    if (summary.monitored_count > 0) {
      return `${summary.monitored_count} tool${summary.monitored_count === 1 ? "" : "s"} with drift events`;
    }
  }
  return analyzer.total_drift_count
    ? `${analyzer.total_drift_count} drift events (no per-tool match)`
    : "stable";
}

// ── Reflexive Core panel ───────────────────────────────────────────
//
// Renders the BehavioralAnalyzer's state + per-tool drift bindings.
// Backed by ``GET /registry/servers/{id}/observability`` — see
// ``PureCipherRegistry.get_server_observability``.

function severityChipColors(severity: string | null | undefined): {
  bg: string;
  fg: string;
  border?: string;
} {
  switch (severity) {
    case "critical":
      return { bg: "rgba(244, 63, 94, 0.28)", fg: "#9f1239" };
    case "high":
      return { bg: "rgba(244, 63, 94, 0.18)", fg: "#b91c1c" };
    case "medium":
      return { bg: "rgba(253, 186, 116, 0.35)", fg: "#9a3412" };
    case "low":
      return { bg: "rgba(253, 230, 138, 0.4)", fg: "#92400e" };
    case "info":
      return {
        bg: "var(--app-control-bg)",
        fg: "var(--app-muted)",
        border: "1px solid var(--app-border)",
      };
    default:
      return {
        bg: "var(--app-control-bg)",
        fg: "var(--app-muted)",
        border: "1px solid var(--app-border)",
      };
  }
}

function ReflexiveCorePanel({
  observability,
}: {
  observability: ServerObservabilityResponse | null;
}) {
  if (!observability || observability.error) {
    return (
      <div className="mt-6">
        <EmptyState
          title="Reflexive Core data unavailable"
          message={
            observability?.error ??
            "We couldn't load observability data for this server. Try refreshing."
          }
        />
      </div>
    );
  }

  const analyzer = observability.analyzer;
  const perTool = observability.per_tool_observability ?? [];
  const recent = observability.recent_drift_events ?? [];
  const summary = observability.summary ?? {
    tool_count: perTool.length,
    monitored_count: 0,
    with_high_drift_count: 0,
    with_critical_drift_count: 0,
  };
  const reflexiveHref =
    observability.links?.reflexive_core_url ?? "/registry/reflexive";

  return (
    <div className="mt-6 rounded-3xl border border-[--app-border] bg-[--app-control-bg] p-5">
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Reflexive Core
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {analyzer?.available
              ? `${analyzer.analyzer_id ?? "analyzer"} · ${analyzer.total_drift_count ?? 0} drift event${(analyzer.total_drift_count ?? 0) === 1 ? "" : "s"}`
              : "The Reflexive Core is not enabled on this registry."}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={analyzer?.available ? "analyzer enabled" : "analyzer disabled"}
            sx={{
              bgcolor: analyzer?.available
                ? "var(--app-control-active-bg)"
                : "var(--app-surface)",
              color: analyzer?.available ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: analyzer?.available ? undefined : "1px solid var(--app-border)",
            }}
          />
          <Chip
            size="small"
            label={`${summary.monitored_count} monitored`}
            sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
          />
          {summary.with_critical_drift_count > 0 ? (
            <Chip
              size="small"
              label={`${summary.with_critical_drift_count} critical`}
              sx={{ bgcolor: "rgba(244, 63, 94, 0.28)", color: "#9f1239", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
          {summary.with_high_drift_count > 0 ? (
            <Chip
              size="small"
              label={`${summary.with_high_drift_count} high`}
              sx={{ bgcolor: "rgba(244, 63, 94, 0.18)", color: "#b91c1c", fontWeight: 700, fontSize: 11 }}
            />
          ) : null}
        </Stack>
      </Box>

      {analyzer?.available ? (
        <>
          <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 2, fontSize: 12, color: "var(--app-muted)" }}>
            <span>
              Monitored actors: <strong style={{ color: "var(--app-fg)" }}>{analyzer.monitored_actor_count ?? 0}</strong>
            </span>
            <span>
              Tracked metrics: <strong style={{ color: "var(--app-fg)" }}>{analyzer.tracked_metric_count ?? 0}</strong>
            </span>
            <span>
              Detectors: <strong style={{ color: "var(--app-fg)" }}>{analyzer.detector_count ?? 0}</strong>
            </span>
            <span>
              Min samples: <strong style={{ color: "var(--app-fg)" }}>{analyzer.min_samples ?? 0}</strong>
            </span>
            {analyzer.latest_drift_at ? (
              <span>
                Last drift: <strong style={{ color: "var(--app-fg)" }}>{new Date(analyzer.latest_drift_at).toLocaleString()}</strong>
                {analyzer.latest_drift_severity ? ` · ${analyzer.latest_drift_severity}` : ""}
                {analyzer.latest_drift_actor_id ? ` · ${analyzer.latest_drift_actor_id}` : ""}
              </span>
            ) : (
              <span>No drift events recorded yet.</span>
            )}
          </Box>

          {analyzer.severity_distribution &&
          Object.values(analyzer.severity_distribution).some((n) => n > 0) ? (
            <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
              {(["critical", "high", "medium", "low", "info"] as const).map(
                (severity) => {
                  const count = analyzer.severity_distribution?.[severity] ?? 0;
                  if (count === 0) return null;
                  const colors = severityChipColors(severity);
                  return (
                    <Chip
                      key={severity}
                      size="small"
                      label={`${severity}: ${count}`}
                      sx={{
                        bgcolor: colors.bg,
                        color: colors.fg,
                        fontWeight: 700,
                        fontSize: 10,
                        fontFamily: "var(--font-geist-mono), monospace",
                        border: colors.border,
                      }}
                    />
                  );
                },
              )}
            </Box>
          ) : null}

          {analyzer.tracked_metrics && analyzer.tracked_metrics.length > 0 ? (
            <Box sx={{ mt: 1.25, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {analyzer.tracked_metrics.slice(0, 8).map((metric) => (
                <Chip
                  key={metric}
                  size="small"
                  label={metric}
                  sx={{
                    bgcolor: "var(--app-surface)",
                    color: "var(--app-muted)",
                    fontFamily: "var(--font-geist-mono), monospace",
                    fontSize: 10,
                    border: "1px solid var(--app-border)",
                  }}
                />
              ))}
              {analyzer.tracked_metrics.length > 8 ? (
                <Chip
                  size="small"
                  label={`+${analyzer.tracked_metrics.length - 8} more`}
                  sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10 }}
                />
              ) : null}
            </Box>
          ) : null}
        </>
      ) : (
        <Typography sx={{ mt: 2, fontSize: 12, color: "var(--app-muted)" }}>
          {analyzer?.reason ??
            "Operators can opt in by passing SecurityConfig(reflexive=ReflexiveConfig(...)) when constructing the registry."}{" "}
          Per-tool observability still renders below — bindings just stay empty until drift events accumulate.
        </Typography>
      )}

      <Box sx={{ mt: 3 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Per-tool drift bindings
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          Drift events are actor-centric. Tool bindings are best-effort matches on event metadata + descriptions.
        </Typography>
        {perTool.length === 0 ? (
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            This server has no tools to observe yet.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.25, display: "grid", gap: 1 }}>
            {perTool.map((row) => (
              <ObservabilityBindingRow key={row.listing_id} row={row} />
            ))}
          </Box>
        )}
      </Box>

      {recent.length > 0 ? (
        <Box sx={{ mt: 3 }}>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Recent drift events
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
            Most-recent first across this server&apos;s tools, capped at the last 10.
          </Typography>
          <Box sx={{ mt: 1, display: "grid", gap: 0.75 }}>
            {recent.slice(0, 10).map((event, idx) => {
              const colors = severityChipColors(event.severity);
              return (
                <Box
                  key={event.event_id ?? idx}
                  sx={{
                    p: 1.25,
                    borderRadius: 2,
                    border: "1px solid var(--app-border)",
                    bgcolor: "var(--app-surface)",
                    display: "grid",
                    gap: 0.5,
                  }}
                >
                  <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                    <Chip
                      size="small"
                      label={event.severity ?? "—"}
                      sx={{
                        bgcolor: colors.bg,
                        color: colors.fg,
                        fontWeight: 700,
                        fontSize: 10,
                        fontFamily: "var(--font-geist-mono), monospace",
                        border: colors.border,
                      }}
                    />
                    {event.drift_type ? (
                      <Chip
                        size="small"
                        label={event.drift_type}
                        sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700, fontSize: 10, fontFamily: "var(--font-geist-mono), monospace" }}
                      />
                    ) : null}
                    {event.tool_name ? (
                      <Link
                        href={`/registry/listings/${encodeURIComponent(event.tool_name)}`}
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color: "var(--app-fg)",
                          textDecoration: "none",
                        }}
                      >
                        {event.display_name ?? event.tool_name}
                      </Link>
                    ) : null}
                    {event.timestamp ? (
                      <Typography sx={{ fontSize: 11, color: "var(--app-muted)", ml: "auto" }}>
                        {new Date(event.timestamp).toLocaleString()}
                      </Typography>
                    ) : null}
                  </Box>
                  {event.description ? (
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      {event.description}
                    </Typography>
                  ) : null}
                  <Typography
                    sx={{
                      fontSize: 11,
                      color: "var(--app-muted)",
                      fontFamily: "var(--font-geist-mono), monospace",
                    }}
                  >
                    actor: {event.actor_id || "—"}
                    {event.observed_value != null && event.baseline_value != null
                      ? ` · ${event.observed_value} (baseline ${event.baseline_value}, σ${event.deviation ?? "—"})`
                      : ""}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Box>
      ) : null}

      <Box sx={{ mt: 2.5 }}>
        <Link href={reflexiveHref} className="hover:text-[--app-fg]">
          <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
            Open Reflexive Core →
          </Typography>
        </Link>
      </Box>
    </div>
  );
}

function ObservabilityBindingRow({
  row,
}: {
  row: ServerObservabilityToolBinding;
}) {
  const isMonitored = row.binding_source === "monitored";
  const colors = severityChipColors(row.highest_severity);
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography
            noWrap
            sx={{
              fontSize: 11,
              color: "var(--app-muted)",
              fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            }}
          >
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
            {row.status && row.status !== "published" ? ` · ${row.status}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={
              isMonitored
                ? `${row.drift_event_count} drift event${row.drift_event_count === 1 ? "" : "s"}`
                : "no drift"
            }
            sx={{
              bgcolor: isMonitored
                ? "var(--app-control-active-bg)"
                : "var(--app-control-bg)",
              color: isMonitored ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
          {isMonitored && row.highest_severity ? (
            <Chip
              size="small"
              label={`peak: ${row.highest_severity}`}
              sx={{
                bgcolor: colors.bg,
                color: colors.fg,
                fontWeight: 700,
                fontSize: 11,
                border: colors.border,
              }}
            />
          ) : null}
        </Stack>
      </Box>
      {isMonitored ? (
        <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {(["critical", "high", "medium", "low", "info"] as const).map(
            (severity) => {
              const count = row.severity_distribution?.[severity] ?? 0;
              if (count === 0) return null;
              const c = severityChipColors(severity);
              return (
                <Chip
                  key={severity}
                  size="small"
                  label={`${severity}: ${count}`}
                  sx={{
                    bgcolor: c.bg,
                    color: c.fg,
                    fontFamily: "var(--font-geist-mono), monospace",
                    fontSize: 10,
                    border: c.border,
                  }}
                />
              );
            },
          )}
          {row.latest_drift_at ? (
            <Typography sx={{ ml: "auto", fontSize: 11, color: "var(--app-muted)" }}>
              Last: {new Date(row.latest_drift_at).toLocaleString()}
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Link>
  );
}

function PolicyBindingRow({ row }: { row: ServerPolicyToolBinding }) {
  const isOverride = row.binding_source === "proxy_allowlist";
  return (
    <Link
      href={`/registry/listings/${encodeURIComponent(row.tool_name)}`}
      className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 transition hover:border-[--app-accent] hover:ring-1 hover:ring-[--app-accent]"
      style={{ display: "block", textDecoration: "none" }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
            {row.display_name ?? row.tool_name}
          </Typography>
          <Typography noWrap sx={{ fontSize: 11, color: "var(--app-muted)", fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}>
            {row.tool_name} · {row.hosting_mode ?? "—"} · {row.attestation_kind ?? "—"}
            {row.status && row.status !== "published" ? ` · ${row.status}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", justifyContent: "flex-end" }}>
          <Chip
            size="small"
            label={isOverride ? "proxy allowlist" : "inherits registry policy"}
            sx={{
              bgcolor: isOverride ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
              color: isOverride ? "var(--app-fg)" : "var(--app-muted)",
              fontWeight: 700,
              fontSize: 11,
              border: "1px solid var(--app-border)",
            }}
          />
          {isOverride && row.policy_provider?.allowed_count != null ? (
            <Chip
              size="small"
              label={`${row.policy_provider.allowed_count} tool${row.policy_provider.allowed_count === 1 ? "" : "s"}`}
              sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontWeight: 700, fontSize: 11, border: "1px solid var(--app-border)" }}
            />
          ) : null}
        </Stack>
      </Box>
      {isOverride && row.policy_provider?.allowed_sample?.length ? (
        <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
          {row.policy_provider.allowed_sample.slice(0, 8).map((tool) => (
            <Chip
              key={tool}
              size="small"
              label={tool}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontFamily: "var(--font-geist-mono), monospace", fontSize: 10 }}
            />
          ))}
          {(row.policy_provider.allowed_count ?? 0) > 8 ? (
            <Chip
              size="small"
              label={`+${(row.policy_provider.allowed_count ?? 0) - 8} more`}
              sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontSize: 10 }}
            />
          ) : null}
        </Box>
      ) : null}
    </Link>
  );
}

