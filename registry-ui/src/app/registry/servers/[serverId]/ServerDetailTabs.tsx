"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { CertificationBadge, EmptyState, KeyValuePanel } from "@/components/security";
import type { PublisherSummary, RegistryToolListing } from "@/lib/registryClient";
import { Typography } from "@mui/material";

type TabKey = "overview" | "tools" | "governance" | "observability";

export function ServerDetailTabs({
  serverId,
  summary,
  listings,
}: {
  serverId: string;
  summary: PublisherSummary;
  listings: RegistryToolListing[];
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
                { label: "drift_status", value: "unknown (stub)" },
              ]}
            />
            <KeyValuePanel
              title="Governance defaults"
              entries={[
                { label: "Policy Kernel", value: "pending (stub)" },
                { label: "Contract Broker", value: "pending (stub)" },
                { label: "Consent Graph", value: "pending (stub)" },
                { label: "Ledger", value: "enabled (stub)" },
              ]}
            />
          </div>

          <div className="mt-4">
            <EmptyState
              title="Next: attach governance + review drift"
              message="This tab is now backed by publisher inventory; Governance and drift will become real once the backend server binding layer is wired."
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
            Stub UI: visualize effective bindings (Policy, Contract, Ledger, Consent) for this server and its tools.
          </Typography>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <KeyValuePanel
              title="Effective controls"
              entries={[
                { label: "Policy Kernel", value: "inherited (stub)" },
                { label: "Contract Broker", value: "inherited (stub)" },
                { label: "Consent Graph", value: "inherited (stub)" },
                { label: "Ledger", value: "recording (stub)" },
              ]}
            />
            <KeyValuePanel
              title="Overrides"
              entries={[
                { label: "Policy overrides", value: "none (stub)" },
                { label: "Contract overrides", value: "none (stub)" },
                { label: "Tool-level quarantine", value: "—" },
                { label: "Pending approvals", value: "0" },
              ]}
            />
          </div>
        </div>
      ) : null}

      {activeTab === "observability" ? (
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Observability stream
          </Typography>
          <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
            Stub UI: show access decision events and ledger integrity checks feeding Reflexive Core recommendations.
          </Typography>
          <div className="mt-6">
            <KeyValuePanel
              title="Reflexive Core (stub)"
              entries={[
                { label: "recommendations", value: "none yet" },
                { label: "alerts", value: "—" },
                { label: "learning_window", value: "rolling (stub)" },
                { label: "confidence", value: "0%" },
              ]}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

