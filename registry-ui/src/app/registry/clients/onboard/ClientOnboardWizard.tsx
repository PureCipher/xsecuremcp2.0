"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import type { RegistryToolListing } from "@/lib/registryClient";
import { EmptyState, KeyValuePanel } from "@/components/security";

type WizardStep = 1 | 2 | 3 | 4 | 5;

type OnboardServer = {
  serverId: string;
  displayName: string;
  toolCount: number;
};

export function ClientOnboardWizard({ servers }: { servers: OnboardServer[] }) {
  const [step, setStep] = useState<WizardStep>(1);

  const [clientName, setClientName] = useState("");
  const [clientType, setClientType] = useState<"desktop" | "agent" | "service">("agent");
  const [selectedServers, setSelectedServers] = useState<string[]>([]);

  const [toolScopeMode, setToolScopeMode] = useState<"all" | "scoped">("all");
  const [selectedToolsByServer, setSelectedToolsByServer] = useState<Record<string, string[]>>({});
  const [toolInventoryByServer, setToolInventoryByServer] = useState<
    Record<string, RegistryToolListing[]>
  >({});
  const [toolInventoryLoading, setToolInventoryLoading] = useState(false);
  const [toolInventoryError, setToolInventoryError] = useState<string | null>(null);

  const [attachPolicy, setAttachPolicy] = useState(true);
  const [attachContract, setAttachContract] = useState(true);
  const [attachLedger, setAttachLedger] = useState(true);
  const [attachConsent, setAttachConsent] = useState(true);

  const summary = useMemo(() => {
    const selectedScopedToolCount = Object.values(selectedToolsByServer).reduce(
      (a, b) => a + b.length,
      0,
    );
    const toolScopeLabel =
      toolScopeMode === "all"
        ? "All tools"
        : selectedScopedToolCount > 0
          ? `Scoped tools (${selectedScopedToolCount})`
          : "Scoped tools (none selected)";
    return [
      { label: "Client", value: clientName ? clientName : "—" },
      { label: "Type", value: clientType },
      { label: "Servers", value: selectedServers.length ? `${selectedServers.length} selected` : "—" },
      { label: "Tool scope", value: toolScopeLabel },
      { label: "Policy attached", value: attachPolicy ? "yes" : "no" },
      { label: "Contract attached", value: attachContract ? "yes" : "no" },
      { label: "Ledger attached", value: attachLedger ? "yes" : "no" },
      { label: "Consent Graph defined", value: attachConsent ? "yes" : "no" },
    ];
  }, [
    clientName,
    clientType,
    selectedServers,
    toolScopeMode,
    selectedToolsByServer,
    attachPolicy,
    attachContract,
    attachLedger,
    attachConsent,
  ]);

  const serverById = useMemo(() => {
    const map: Record<string, OnboardServer> = {};
    for (const s of servers) map[s.serverId] = s;
    return map;
  }, [servers]);

  useEffect(() => {
    if (toolScopeMode !== "scoped") return;
    if (selectedServers.length === 0) return;

    let cancelled = false;

    setToolInventoryLoading(true);
    setToolInventoryError(null);

    Promise.all(
      selectedServers.map(async (serverId) => {
        const res = await fetch(
          `/api/servers/publishers/${encodeURIComponent(serverId)}/profile`,
          { method: "GET" },
        );
        if (!res.ok) throw new Error(`Failed to load server profile (${serverId})`);
        const data = (await res.json()) as { listings?: RegistryToolListing[] };
        return { serverId, listings: data.listings ?? [] };
      }),
    )
      .then((results) => {
        if (cancelled) return;
        const nextInv: Record<string, RegistryToolListing[]> = {};
        for (const r of results) nextInv[r.serverId] = r.listings;
        setToolInventoryByServer(nextInv);
      })
      .catch((e) => {
        if (cancelled) return;
        setToolInventoryError(e instanceof Error ? e.message : "Failed to load tool inventory");
        setToolInventoryByServer({});
      })
      .finally(() => {
        if (cancelled) return;
        setToolInventoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [toolScopeMode, selectedServers]);

  function toggleToolSelection(serverId: string, toolName: string) {
    setSelectedToolsByServer((current) => {
      const existing = current[serverId] ?? [];
      const has = existing.includes(toolName);
      const next = has ? existing.filter((t) => t !== toolName) : [...existing, toolName];
      return { ...current, [serverId]: next };
    });
  }

  function next() {
    setStep((s) => (s < 5 ? ((s + 1) as WizardStep) : s));
  }

  function back() {
    setStep((s) => (s > 1 ? ((s - 1) as WizardStep) : s));
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
          Clients
        </p>
        <h1 className="text-2xl font-semibold text-[--app-fg]">Onboard client</h1>
        <p className="max-w-2xl text-[11px] text-[--app-muted]">
          UI skeleton for client onboarding: discover eligible servers, bind governance (Policy/Contract/Ledger/Consent),
          simulate access, and activate.
        </p>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-[--app-fg]">Step {step} of 5</h2>
            <p className="text-[11px] text-[--app-muted]">
              {step === 1
                ? "Define client identity."
                : step === 2
                  ? "Select MCP servers to bind."
                  : step === 3
                    ? "Attach governance layers."
                    : step === 4
                      ? "Simulate effective access."
                      : "Review and activate (stub)."}
            </p>
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
              disabled={step === 5}
              className="rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
            >
              Next
            </button>
          </div>
        </div>

        {step === 1 ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="space-y-1">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Client name
              </span>
              <input
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g., Cursor agent / Desktop app / CI service"
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
            </label>

            <label className="space-y-1">
              <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Client type
              </span>
              <select
                value={clientType}
                onChange={(e) => setClientType(e.target.value as "desktop" | "agent" | "service")}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                <option value="agent">Agent</option>
                <option value="desktop">Desktop</option>
                <option value="service">Service</option>
              </select>
            </label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Select servers (live directory)
              </h3>
              <p className="mt-2 text-[11px] text-[--app-muted]">
                Servers are sourced from the registry backend&apos;s publisher directory. In MCP terms, each server can expose many tools; scope will be implemented next.
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {servers.length === 0 ? (
                  <span className="text-[11px] text-[--app-muted]">No servers available.</span>
                ) : (
                  servers.map((s) => {
                    const selected = selectedServers.includes(s.serverId);
                    return (
                      <button
                        key={s.serverId}
                        type="button"
                        onClick={() =>
                          setSelectedServers((current) =>
                            selected
                              ? current.filter((x) => x !== s.serverId)
                              : [...current, s.serverId],
                          )
                        }
                        className={`rounded-full border border-[--app-border] px-4 py-2 text-xs font-semibold transition ${
                          selected
                            ? "bg-[--app-accent] border-[--app-accent] text-[--app-accent-contrast]"
                            : "bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
                        }`}
                      >
                        {s.displayName}
                        <span className="ml-2 text-[10px] text-[--app-muted]">
                          ({s.toolCount})
                        </span>
                      </button>
                    );
                  })
                )}
              </div>

              <p className="mt-3 text-[11px] text-[--app-muted]">
                Selected servers:{" "}
                <span className="font-semibold text-[--app-fg]">{selectedServers.length}</span>
              </p>
            </div>

            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Server/tool scope (scaffolding)
              </h3>
              <p className="mt-2 text-[11px] text-[--app-muted]">
                Choose whether the client binding covers all tools for each selected server, or a scoped subset (UI stub).
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setToolScopeMode("all");
                    setSelectedToolsByServer({});
                  }}
                  className={`rounded-full border border-[--app-border] px-4 py-2 text-xs font-semibold transition ${
                    toolScopeMode === "all"
                      ? "bg-[--app-accent] border-[--app-accent] text-[--app-accent-contrast]"
                      : "bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
                  }`}
                >
                  All tools
                </button>
                <button
                  type="button"
                  onClick={() => setToolScopeMode("scoped")}
                  className={`rounded-full border border-[--app-border] px-4 py-2 text-xs font-semibold transition ${
                    toolScopeMode === "scoped"
                      ? "bg-[--app-accent] border-[--app-accent] text-[--app-accent-contrast]"
                      : "bg-[--app-control-bg] text-[--app-muted] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
                  }`}
                >
                  Scoped tools (stub)
                </button>
              </div>

              {toolScopeMode === "scoped" ? (
                <div className="mt-4">
                  {toolInventoryError ? (
                    <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-3">
                      <p className="text-[11px] text-red-200">{toolInventoryError}</p>
                    </div>
                  ) : toolInventoryLoading ? (
                    <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-4">
                      <p className="text-[11px] text-[--app-muted]">Loading tool inventory…</p>
                    </div>
                  ) : selectedServers.length === 0 ? (
                    <EmptyState
                      title="Select servers first"
                      message="Choose one or more MCP servers before scoping tools."
                    />
                  ) : (
                    <div className="space-y-4">
                      {selectedServers.map((serverId) => {
                        const server = serverById[serverId];
                        const inventory = toolInventoryByServer[serverId] ?? [];
                        const selectedForServer = selectedToolsByServer[serverId] ?? [];

                        return (
                          <div
                            key={serverId}
                            className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-4"
                          >
                            <div className="flex items-baseline justify-between gap-3">
                              <h3 className="text-sm font-semibold text-[--app-fg]">
                                {server?.displayName ?? serverId}
                              </h3>
                              <span className="rounded-full bg-[--app-chrome-bg] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
                                {selectedForServer.length}/{inventory.length} selected
                              </span>
                            </div>

                            {inventory.length === 0 ? (
                              <p className="mt-2 text-[11px] text-[--app-muted]">
                                No tool listings found for this server profile.
                              </p>
                            ) : (
                              <div className="mt-3 flex flex-col gap-2">
                                {inventory.map((tool) => {
                                  const checked = selectedForServer.includes(tool.tool_name);
                                  return (
                                    <label
                                      key={tool.tool_name}
                                      className="flex cursor-pointer items-start justify-between gap-3 rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2"
                                    >
                                      <span className="min-w-0">
                                        <span className="block text-[11px] font-semibold text-[--app-fg]">
                                          {tool.display_name ?? tool.tool_name}
                                        </span>
                                        {tool.description ? (
                                          <span className="mt-1 block line-clamp-2 text-[10px] text-[--app-muted]">
                                            {tool.description}
                                          </span>
                                        ) : null}
                                      </span>
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={() => toggleToolSelection(serverId, tool.tool_name)}
                                        className="mt-1 h-4 w-4 cursor-pointer accent-[--app-accent]"
                                      />
                                    </label>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <KeyValuePanel
              title="Access binding preview (stub)"
              entries={[
                { label: "client_id", value: clientName ? clientName : "pending" },
                {
                  label: "server_bindings",
                  value: selectedServers.length ? String(selectedServers.length) : "—",
                },
                {
                  label: "tool_scope",
                  value:
                    toolScopeMode === "all"
                      ? "all-tools"
                      : Object.values(selectedToolsByServer).reduce((a, b) => a + b.length, 0) > 0
                        ? `scoped-tools (${Object.values(selectedToolsByServer).reduce((a, b) => a + b.length, 0)})`
                        : "scoped-tools (none selected)",
                },
              ]}
            />
          </div>
        ) : null}

        {step === 3 ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Governance layers
              </h3>
              <div className="mt-4 space-y-3">
                <ToggleRow
                  checked={attachPolicy}
                  label="Apply Policy Kernel"
                  onChange={setAttachPolicy}
                />
                <ToggleRow
                  checked={attachContract}
                  label="Attach Contract Broker"
                  onChange={setAttachContract}
                />
                <ToggleRow
                  checked={attachLedger}
                  label="Record in Provenance Ledger"
                  onChange={setAttachLedger}
                />
                <ToggleRow
                  checked={attachConsent}
                  label="Define Consent Graph"
                  onChange={setAttachConsent}
                />
              </div>
            </div>

            <KeyValuePanel title="Effective coverage (stub)" entries={summary} />
          </div>
        ) : null}

        {step === 4 ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Access simulation
              </h3>
              <p className="mt-2 text-[11px] text-[--app-muted]">
                UI skeleton: run a matrix of allowed/denied operations based on Policy Kernel + Consent Graph + Contract terms.
              </p>
              <button
                type="button"
                disabled
                className="mt-4 cursor-not-allowed rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] opacity-60"
              >
                Run simulation (stub)
              </button>
            </div>

            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Simulation results (placeholder)
              </h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <MiniCell label="allowed_calls" value="—" />
                <MiniCell label="denied_calls" value="—" />
                <MiniCell label="consent_misses" value="—" />
                <MiniCell label="contract_violations" value="—" />
              </div>
            </div>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
            <KeyValuePanel title="Final review (stub)" entries={summary} />
            <div className="space-y-3">
              <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                  Reflexive Core
                </h3>
                <p className="mt-2 text-[11px] text-[--app-muted]">
                  Reflexive Core will learn from outcomes (allows/denies/overrides) and propose improvements as reviewable proposals.
                </p>
              </div>
              <div className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <p className="text-[11px] font-semibold text-[--app-fg]">Activate binding (stub)</p>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-full bg-[--app-control-bg] px-4 py-2 text-xs font-semibold text-[--app-muted] opacity-60"
                >
                  Activate client access (coming soon)
                </button>
                <Link href="/registry/clients" className="text-[11px] font-semibold text-[--app-accent] hover:text-[--app-fg]">
                  ← Back to clients
                </Link>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ToggleRow({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`flex w-full items-center justify-between rounded-2xl border border-[--app-border] px-3 py-2 text-left text-[11px] transition ${
        checked ? "bg-[--app-control-active-bg]" : "bg-[--app-control-bg] hover:bg-[--app-hover-bg]"
      }`}
    >
      <span className="font-semibold text-[--app-fg]">{label}</span>
      <span
        className={`inline-flex h-5 w-10 items-center rounded-full px-1 text-[10px] font-bold ${
          checked ? "bg-[--app-accent]" : "bg-[--app-control-border]"
        }`}
      >
        {checked ? "On" : "Off"}
      </span>
    </button>
  );
}

function MiniCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">{label}</p>
      <p className="mt-2 text-[12px] font-semibold text-[--app-fg]">{value}</p>
    </div>
  );
}

