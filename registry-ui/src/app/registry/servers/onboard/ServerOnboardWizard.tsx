"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import type { RegistryToolListing } from "@/lib/registryClient";
import { KeyValuePanel, EmptyState } from "@/components/security";
import { Box, Typography } from "@mui/material";

type WizardStep = 1 | 2 | 3 | 4;

type ServerOnboardTarget = {
  publisherId: string;
  displayName: string;
  toolCount: number;
};

export function ServerOnboardWizard({ servers }: { servers: ServerOnboardTarget[] }) {
  const [step, setStep] = useState<WizardStep>(1);

  const [selectedPublisherId, setSelectedPublisherId] = useState<string>(
    servers[0]?.publisherId ?? "",
  );
  const [authMode, setAuthMode] = useState<"none" | "token">("none");

  const [profileLoading, setProfileLoading] = useState(false);
  const [tools, setTools] = useState<RegistryToolListing[] | null>(null);
  const [toolsError, setToolsError] = useState<string | null>(null);

  const [defaultPolicyProfile, setDefaultPolicyProfile] = useState("policy-kernel-default");
  const [defaultContractTemplate, setDefaultContractTemplate] = useState("contract-broker-default");
  const [consentProfile, setConsentProfile] = useState("consent-graph-default");

  const selected = useMemo(() => {
    return servers.find((s) => s.publisherId === selectedPublisherId) ?? null;
  }, [servers, selectedPublisherId]);

  const toolsDiscoveredCount = tools?.length ?? selected?.toolCount ?? null;

  const derivedSummary = useMemo(() => {
    return [
      { label: "MCP Server", value: selected?.displayName ?? "—" },
      { label: "Auth mode", value: authMode },
      { label: "Tools discovered", value: toolsDiscoveredCount == null ? "—" : String(toolsDiscoveredCount) },
      { label: "Policy Kernel", value: defaultPolicyProfile },
      { label: "Contract Broker", value: defaultContractTemplate },
      { label: "Consent Graph", value: consentProfile },
    ];
  }, [
    selected,
    authMode,
    toolsDiscoveredCount,
    defaultPolicyProfile,
    defaultContractTemplate,
    consentProfile,
  ]);

  useEffect(() => {
    // If server list changes (rare), keep selection valid.
    if (!selectedPublisherId && servers[0]?.publisherId) {
      setSelectedPublisherId(servers[0].publisherId);
    }
  }, [servers, selectedPublisherId]);

  function next() {
    setStep((s) => (s < 4 ? ((s + 1) as WizardStep) : s));
  }

  function back() {
    setStep((s) => (s > 1 ? ((s - 1) as WizardStep) : s));
  }

  async function discoverTools() {
    if (!selectedPublisherId) return;

    setProfileLoading(true);
    setToolsError(null);
    setTools(null);

    try {
      const res = await fetch(
        `/api/servers/publishers/${encodeURIComponent(selectedPublisherId)}/profile`,
        { method: "GET" },
      );

      if (!res.ok) {
        throw new Error(`Backend responded with ${res.status}`);
      }

      const data = (await res.json()) as { listings?: RegistryToolListing[] };
      setTools(data.listings ?? []);
    } catch (e) {
      setToolsError(e instanceof Error ? e.message : "Failed to fetch server profile");
    } finally {
      setProfileLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          MCP Servers
        </Typography>
        <Typography variant="h5" sx={{ color: "var(--app-fg)" }}>
          Onboard MCP server
        </Typography>
        <Typography variant="body2" sx={{ maxWidth: 720, color: "var(--app-muted)" }}>
          MCP-first onboarding wizard: select a live server source from the registry, discover its tool inventory, then
          attach Governance defaults (stub until SecureMCP guardrails phase).
        </Typography>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Step {step} of 4
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              {step === 1
                ? "Select MCP server source + auth settings."
                : step === 2
                  ? "Discover the server tool inventory."
                  : step === 3
                    ? "Choose default Policy/Contract/Consent bindings."
                    : "Review and activate (stub)."}
            </Typography>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={back}
              disabled={step === 1}
              className="rounded-full border border-[--app-border] px-4 py-2 text-xs font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-50"
            >
              Back
            </button>
            <button
              type="button"
              onClick={next}
              disabled={step === 4}
              className="rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
            >
              Next
            </button>
          </div>
        </div>

        {step === 1 ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                MCP server source
              </Typography>
              <select
                value={selectedPublisherId}
                onChange={(e) => setSelectedPublisherId(e.target.value)}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                {servers.length === 0 ? <option value="">No servers available</option> : null}
                {servers.map((s) => (
                  <option key={s.publisherId} value={s.publisherId}>
                    {s.displayName} ({s.toolCount})
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Auth mode
              </Typography>
              <select
                value={authMode}
                onChange={(e) => setAuthMode(e.target.value as "none" | "token")}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                <option value="none">None</option>
                <option value="token">Token</option>
              </select>
            </label>

            <div className="md:col-span-2">
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                This phase focuses on MCP tool inventory discovery using the registry backend. Connectivity validation and
                activation will be added once SecureMCP guardrails are introduced.
              </Typography>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                Tool discovery
              </Typography>
              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                Uses registry backend publisher profile as the initial Capability Snapshot source (MCP-first).
              </Typography>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={discoverTools}
                  disabled={profileLoading || !selectedPublisherId}
                  className="rounded-full border border-[--app-border] bg-[--app-control-bg] px-4 py-2 text-xs font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-60"
                >
                  {profileLoading ? "Discovering..." : "Discover tools"}
                </button>
                <span className="text-[11px] text-[--app-muted]">
                  Tools discovered:{" "}
                  <span className="font-semibold text-[--app-fg]">
                    {toolsDiscoveredCount == null ? "—" : toolsDiscoveredCount}
                  </span>
                </span>
              </div>

              {toolsError ? (
                <div className="mt-3 rounded-2xl border border-red-500/40 bg-red-500/10 p-3">
                  <Typography variant="caption" sx={{ color: "rgb(254, 202, 202)" }}>
                    Discovery failed: {toolsError}
                  </Typography>
                </div>
              ) : null}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <KeyValuePanel
                title="Capability Snapshot"
                entries={[
                  {
                    label: "tools_count",
                    value: toolsDiscoveredCount == null ? "—" : String(toolsDiscoveredCount),
                  },
                  { label: "snapshot_hash", value: "pending-integration" },
                ]}
              />
              <KeyValuePanel
                title="Drift detection"
                entries={[
                  { label: "status", value: "unknown" },
                  { label: "next check", value: "on-activation" },
                ]}
              />
            </div>

            <div className="mt-2">
              {tools == null ? (
                <EmptyState
                  title="No discovery yet"
                  message="Click “Discover tools” to load the server tool inventory from the registry."
                />
              ) : tools.length === 0 ? (
                <EmptyState
                  title="No tools found"
                  message="The selected server profile currently has no tool listings."
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {tools.map((tool) => (
                    <Link
                      key={tool.tool_name}
                      href={`/registry/listings/${encodeURIComponent(tool.tool_name)}`}
                      className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring] transition hover:border-[--app-accent] hover:ring-[--app-accent]"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <h3 className="text-sm font-semibold text-[--app-fg]">
                          {tool.display_name ?? tool.tool_name}
                        </h3>
                        <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
                          {tool.certification_level ?? "unlisted"}
                        </span>
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

        {step === 3 ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Policy Kernel (default profile)
              </Typography>
              <select
                value={defaultPolicyProfile}
                onChange={(e) => setDefaultPolicyProfile(e.target.value)}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                <option value="policy-kernel-default">policy-kernel-default</option>
                <option value="policy-kernel-strict">policy-kernel-strict</option>
              </select>
            </label>

            <label className="space-y-1">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Contract Broker (template)
              </Typography>
              <select
                value={defaultContractTemplate}
                onChange={(e) => setDefaultContractTemplate(e.target.value)}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                <option value="contract-broker-default">contract-broker-default</option>
                <option value="contract-broker-minimum">contract-broker-minimum</option>
              </select>
            </label>

            <label className="space-y-1 md:col-span-2">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Consent Graph (baseline)
              </Typography>
              <select
                value={consentProfile}
                onChange={(e) => setConsentProfile(e.target.value)}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                <option value="consent-graph-default">consent-graph-default</option>
                <option value="consent-graph-restrictive">consent-graph-restrictive</option>
              </select>
            </label>

            <div className="md:col-span-2">
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Governance attachments are a stub in this MCP-first iteration. SecureMCP guardrails will make these choices enforceable.
              </Typography>
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
            <KeyValuePanel title="Governance Stack Preview" entries={derivedSummary} />

            <div className="space-y-3">
              <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                  Activation (stub)
                </Typography>
                <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                  This skeleton will later call backend endpoints to:
                  <br />• activate server snapshot
                  <br />• attach default governance
                  <br />• set initial reflexive learning hooks
                </Typography>
                <button
                  type="button"
                  disabled
                  className="mt-2 cursor-not-allowed rounded-full bg-[--app-control-bg] px-4 py-2 text-xs font-semibold text-[--app-muted] opacity-60"
                >
                  Activate server (coming soon)
                </button>
              </div>

              <div className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  Next
                </Typography>
                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  Back to server directory and review your newly discovered tool inventory.
                </Typography>
                <Link
                  href="/registry/servers"
                  className="hover:text-[--app-fg]"
                >
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-accent)" }}>
                    ← Back to MCP servers
                  </Typography>
                </Link>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

