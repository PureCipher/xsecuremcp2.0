"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type {
  RegistryClientCreateResponse,
  RegistryClientKind,
  RegistryToolListing,
} from "@/lib/registryClient";
import { EmptyState, KeyValuePanel } from "@/components/security";
import { Box, Typography } from "@mui/material";

type WizardStep = 1 | 2 | 3 | 4 | 5;

type OnboardServer = {
  serverId: string;
  displayName: string;
  toolCount: number;
};

const CLIENT_KIND_OPTIONS: {
  value: RegistryClientKind;
  label: string;
  hint: string;
}[] = [
  {
    value: "agent",
    label: "Agent",
    hint: "An LLM-driven client (Claude Desktop, Cursor, custom agents).",
  },
  {
    value: "service",
    label: "Service",
    hint: "A backend service that calls MCP servers (CI bot, data sync).",
  },
  {
    value: "framework",
    label: "Framework",
    hint: "A toolkit or harness that hosts other clients (LangChain, LlamaIndex).",
  },
  {
    value: "tooling",
    label: "Tooling",
    hint: "Developer/operator tools (CLIs, dashboards, scripts).",
  },
  { value: "other", label: "Other", hint: "Anything that doesn't fit above." },
];

export function ClientOnboardWizard({ servers }: { servers: OnboardServer[] }) {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(1);

  const [clientName, setClientName] = useState("");
  const [clientSlug, setClientSlug] = useState("");
  const [clientDescription, setClientDescription] = useState("");
  const [clientIntendedUse, setClientIntendedUse] = useState("");
  const [clientType, setClientType] = useState<RegistryClientKind>("agent");
  const [selectedServers, setSelectedServers] = useState<string[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] =
    useState<RegistryClientCreateResponse | null>(null);

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
      { label: "Display name", value: clientName ? clientName : "—" },
      { label: "Slug", value: clientSlug ? clientSlug : "(auto)" },
      { label: "Kind", value: clientType },
      { label: "Servers", value: selectedServers.length ? `${selectedServers.length} selected` : "—" },
      { label: "Tool scope", value: toolScopeLabel },
      { label: "Policy attached", value: attachPolicy ? "yes" : "no" },
      { label: "Contract attached", value: attachContract ? "yes" : "no" },
      { label: "Ledger attached", value: attachLedger ? "yes" : "no" },
      { label: "Consent Graph defined", value: attachConsent ? "yes" : "no" },
    ];
  }, [
    clientName,
    clientSlug,
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

  const canSubmit = clientName.trim().length > 0 && !submitting && !submitResult;

  async function handleActivate() {
    if (!canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const slug = clientSlug.trim();
      const payload: Record<string, unknown> = {
        display_name: clientName.trim(),
        kind: clientType,
        description: clientDescription.trim(),
        intended_use: clientIntendedUse.trim(),
        issue_initial_token: true,
        token_name: "Default",
      };
      if (slug) payload.slug = slug;

      const res = await fetch("/api/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await res.json().catch(() => ({}))) as RegistryClientCreateResponse;
      if (!res.ok) {
        setSubmitError(
          (typeof data.error === "string" && data.error) ||
            `Failed to register client (${res.status})`,
        );
        return;
      }
      setSubmitResult(data);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to register client");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-1">
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          Clients
        </Typography>
        <Typography variant="h5" sx={{ color: "var(--app-fg)" }}>
          Onboard client
        </Typography>
        <Typography variant="body2" sx={{ maxWidth: 720, color: "var(--app-muted)" }}>
          UI skeleton for client onboarding: discover eligible servers, bind governance (Policy/Contract/Ledger/Consent),
          simulate access, and activate.
        </Typography>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Step {step} of 5
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              {step === 1
                ? "Define client identity."
                : step === 2
                  ? "Select MCP servers to bind."
                  : step === 3
                    ? "Attach governance layers."
                    : step === 4
                      ? "Simulate effective access."
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
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Display name
              </Typography>
              <input
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g., Claude Desktop / Acme CI bot"
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
            </label>

            <label className="space-y-1">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Slug (optional — auto-derived)
              </Typography>
              <input
                value={clientSlug}
                onChange={(e) => setClientSlug(e.target.value)}
                placeholder="claude-desktop"
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent] font-mono"
              />
              <Typography component="span" variant="caption" sx={{ display: "block", mt: 0.5, color: "var(--app-muted)" }}>
                Stable identifier broadcast to every plane as <code>actor_id</code>. Cannot be changed after creation.
              </Typography>
            </label>

            <label className="space-y-1 md:col-span-2">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Client kind
              </Typography>
              <select
                value={clientType}
                onChange={(e) => setClientType(e.target.value as RegistryClientKind)}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              >
                {CLIENT_KIND_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <Typography component="span" variant="caption" sx={{ display: "block", mt: 0.5, color: "var(--app-muted)" }}>
                {CLIENT_KIND_OPTIONS.find((o) => o.value === clientType)?.hint}
              </Typography>
            </label>

            <label className="space-y-1 md:col-span-2">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Description
              </Typography>
              <textarea
                value={clientDescription}
                onChange={(e) => setClientDescription(e.target.value)}
                placeholder="Short description shown on the client's profile"
                rows={2}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
            </label>

            <label className="space-y-1 md:col-span-2">
              <Typography component="span" variant="overline" sx={{ display: "block", color: "var(--app-muted)", letterSpacing: "0.14em" }}>
                Intended use
              </Typography>
              <textarea
                value={clientIntendedUse}
                onChange={(e) => setClientIntendedUse(e.target.value)}
                placeholder="What will this client do? Helps reviewers understand its scope."
                rows={2}
                className="w-full rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
            </label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                Select servers (live directory)
              </Typography>
              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                Servers are sourced from the registry backend&apos;s publisher directory. In MCP terms, each server can expose many tools; scope will be implemented next.
              </Typography>

              <div className="mt-4 flex flex-wrap gap-2">
                {servers.length === 0 ? (
                  <Typography component="span" variant="caption" sx={{ color: "var(--app-muted)" }}>
                    No servers available.
                  </Typography>
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
                        <Typography component="span" variant="caption" sx={{ ml: 1, color: "var(--app-muted)" }}>
                          ({s.toolCount})
                        </Typography>
                      </button>
                    );
                  })
                )}
              </div>

              <Typography variant="caption" sx={{ mt: 1.5, color: "var(--app-muted)" }}>
                Selected servers:{" "}
                <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {selectedServers.length}
                </Box>
              </Typography>
            </div>

            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
              <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                Server/tool scope (scaffolding)
              </Typography>
              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                Choose whether the client binding covers all tools for each selected server, or a scoped subset (UI stub).
              </Typography>

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
                      <Typography variant="caption" sx={{ color: "rgb(254, 202, 202)" }}>
                        {toolInventoryError}
                      </Typography>
                    </div>
                  ) : toolInventoryLoading ? (
                    <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-4">
                      <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                        Loading tool inventory…
                      </Typography>
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
                              <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                                {server?.displayName ?? serverId}
                              </Typography>
                              <span className="rounded-full bg-[--app-chrome-bg] px-2 py-0.5 text-[10px] font-semibold text-[--app-muted]">
                                {selectedForServer.length}/{inventory.length} selected
                              </span>
                            </div>

                            {inventory.length === 0 ? (
                              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                                No tool listings found for this server profile.
                              </Typography>
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
                                        <Typography component="span" variant="caption" sx={{ display: "block", fontWeight: 700, color: "var(--app-fg)" }}>
                                          {tool.display_name ?? tool.tool_name}
                                        </Typography>
                                        {tool.description ? (
                                          <Typography component="span" variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
                                            {tool.description}
                                          </Typography>
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
              <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                Governance layers
              </Typography>
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
              <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                Access simulation
              </Typography>
              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                Simulation will evaluate selected client bindings against Policy Kernel, Consent Graph, and Contract Broker rules once the binding API is connected.
              </Typography>
              <button
                type="button"
                disabled
                className="mt-4 cursor-not-allowed rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] opacity-60"
              >
                Run simulation
              </button>
            </div>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.9fr]">
            <KeyValuePanel title="Final review" entries={summary} />
            <div className="space-y-3">
              <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                  Reflexive Core
                </Typography>
                <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                  Once the client makes calls, Reflexive Core learns its baseline behavior and surfaces drift events on the per-client governance panel.
                </Typography>
              </div>
              <div className="flex flex-col gap-2 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4">
                <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                  {submitResult ? "Client registered" : "Register client identity"}
                </Typography>

                {submitResult ? (
                  <SecretPanel
                    response={submitResult}
                    onDone={() => {
                      router.push(
                        `/registry/clients/${encodeURIComponent(
                          submitResult.client?.slug ?? "",
                        )}`,
                      );
                    }}
                  />
                ) : (
                  <>
                    <Typography
                      variant="caption"
                      sx={{ color: "var(--app-muted)" }}
                    >
                      Creates the client identity, mints an initial API token, and shows you the secret <strong>once</strong>. Server bindings &amp; per-tool scope flow into the per-client governance page after activation.
                    </Typography>

                    {submitError ? (
                      <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2">
                        <Typography
                          variant="caption"
                          sx={{ color: "rgb(254, 202, 202)", fontWeight: 600 }}
                        >
                          {submitError}
                        </Typography>
                      </div>
                    ) : null}

                    <button
                      type="button"
                      onClick={handleActivate}
                      disabled={!canSubmit}
                      className="rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {submitting ? "Registering…" : "Register client"}
                    </button>
                  </>
                )}

                <Link href="/registry/clients" className="hover:text-[--app-fg]">
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-accent)" }}>
                    ← Back to clients
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

function SecretPanel({
  response,
  onDone,
}: {
  response: RegistryClientCreateResponse;
  onDone: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const secret = response.secret ?? "";
  const slug = response.client?.slug ?? "";

  async function copySecret() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2">
        <Typography
          variant="caption"
          sx={{ color: "rgb(252, 211, 77)", fontWeight: 700 }}
        >
          Save this secret now — it won&apos;t be shown again
        </Typography>
      </div>

      <div className="rounded-xl border border-[--app-border] bg-[--app-chrome-bg] px-3 py-2">
        <Typography
          variant="caption"
          sx={{
            display: "block",
            color: "var(--app-muted)",
            fontSize: 10,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          API token
        </Typography>
        <div className="mt-1 flex items-center justify-between gap-2">
          <code className="flex-1 break-all font-mono text-xs text-[--app-fg]">
            {secret || "(no secret returned)"}
          </code>
          <button
            type="button"
            onClick={copySecret}
            disabled={!secret}
            className="rounded-full border border-[--app-border] bg-[--app-control-bg] px-3 py-1 text-[10px] font-semibold text-[--app-fg] transition hover:bg-[--app-hover-bg] disabled:opacity-50"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2">
        <Typography
          variant="caption"
          sx={{
            display: "block",
            color: "var(--app-muted)",
            fontSize: 10,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
          }}
        >
          Authorization header
        </Typography>
        <code className="mt-1 block break-all font-mono text-[11px] text-[--app-fg]">
          Authorization: Bearer {secret || "<token>"}
        </code>
        <Typography
          variant="caption"
          sx={{ display: "block", mt: 1, color: "var(--app-muted)" }}
        >
          Configure your client to send this header. Every request flows through the registry as <code>actor_id={slug}</code>.
        </Typography>
      </div>

      <button
        type="button"
        onClick={onDone}
        className="w-full rounded-full bg-[--app-accent] px-4 py-2 text-xs font-semibold text-[--app-accent-contrast] transition hover:opacity-90"
      >
        Open client profile
      </button>
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
      <Typography component="span" variant="caption" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
        {label}
      </Typography>
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


