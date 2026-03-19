"use client";

import { useMemo } from "react";
import type {
  PolicyAnalyticsResponse,
  PolicyBundleItem,
  RegistryPayload,
} from "@/lib/registryClient";
import { usePolicyContext } from "../../contexts/PolicyContext";

type OverviewTabProps = {
  analytics: PolicyAnalyticsResponse;
  bundles: PolicyBundleItem[];
  onStageBundle: (bundleId: string, title: string) => Promise<void>;
};

function riskLevelClass(level: string | undefined): string {
  switch (level?.toLowerCase()) {
    case "critical":
      return "bg-red-500/15 text-red-200 ring-1 ring-red-400/50";
    case "high":
      return "bg-rose-500/15 text-rose-200 ring-1 ring-rose-400/50";
    case "medium":
      return "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/50";
    case "low":
      return "bg-[--app-control-active-bg] text-[--app-muted] ring-1 ring-[--app-accent]";
    default:
      return "bg-zinc-500/15 text-zinc-200 ring-1 ring-zinc-400/40";
  }
}

function TrendIndicator({ value, invertColor }: { value: number | undefined; invertColor?: boolean }) {
  const num = Number(value ?? 0);
  if (num === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[--app-muted]">
        <span className="text-sm">&mdash;</span> no change
      </span>
    );
  }

  // For deny/risk counts, "up" is bad (red) and "down" is good (green)
  // For eval counts, "up" is good — use invertColor to flip
  const isUp = num > 0;
  const isGood = invertColor ? isUp : !isUp;

  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-semibold ${
        isGood ? "text-[--app-muted]" : "text-rose-300"
      }`}
    >
      <svg viewBox="0 0 12 12" className={`h-3 w-3 ${isUp ? "" : "rotate-180"}`} fill="currentColor">
        <path d="M6 2l4 6H2z" />
      </svg>
      {isUp ? "+" : ""}{num}
    </span>
  );
}

export function OverviewTab({
  analytics,
  bundles,
  onStageBundle,
}: OverviewTabProps) {
  const { busyKey } = usePolicyContext();

  const topDeniedResources = useMemo(() => {
    const auditResources = analytics.blocked?.audit?.top_denied_resources;
    if (Array.isArray(auditResources)) return auditResources as RegistryPayload[];
    const monitorWindow = analytics.blocked?.monitor?.window as RegistryPayload | undefined;
    const monitorResources = monitorWindow?.top_denied_resources;
    if (Array.isArray(monitorResources)) return monitorResources as RegistryPayload[];
    return [] as RegistryPayload[];
  }, [analytics.blocked?.audit?.top_denied_resources, analytics.blocked?.monitor]);

  return (
    <div className="flex flex-col gap-6">
      {/* ── Analytics ─────────────────────────────────────────────── */}
      <section className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
          <div className="space-y-1">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
              Policy analytics
            </p>
            <h2 className="text-xl font-semibold text-[--app-fg]">
              See what is blocked, changed, and risky
            </h2>
            <p className="text-xs text-[--app-muted]">
              Live deny patterns, recent changes, and rollout risk at a glance.
            </p>
          </div>

          {/* Key metrics */}
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <MetricCard
              label="Blocked now"
              value={String(
                (analytics.blocked?.audit?.current_deny as number | undefined) ??
                  analytics.overview?.deny_count ?? 0,
              )}
              subtitle="Denials in the current window"
            />
            <MetricCard
              label="Deny rate"
              value={`${Math.round(
                Number(
                  (analytics.blocked?.audit?.deny_rate as number | undefined) ??
                    (analytics.blocked?.monitor?.window as RegistryPayload | undefined)
                      ?.deny_rate ?? 0,
                ) * 100,
              )}%`}
              subtitle="Recent blocked traffic share"
            />
            <MetricCard
              label="Active risks"
              value={String(analytics.risks?.length ?? 0)}
              subtitle="Review items worth attention"
            />
          </div>

          {/* Most blocked + version changes */}
          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr,1fr]">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Most blocked resources
              </p>
              <ul className="mt-3 space-y-2 text-xs text-[--app-muted]">
                {topDeniedResources.slice(0, 4).map((item, index) => (
                  <li
                    key={`top-denied-${index}`}
                    className="rounded-2xl border border-[--app-border] bg-[--app-surface] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                  >
                    {String(item.resource_id ?? "unknown")} ·{" "}
                    {String(item.count ?? 0)} denials
                  </li>
                ))}
                {topDeniedResources.length === 0 ? (
                  <li className="text-xs text-[--app-muted]">
                    No deny hot spots have been recorded yet.
                  </li>
                ) : null}
              </ul>
            </div>

            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Recent version change
              </p>
              {analytics.changes?.latest_version_summary ? (
                <div className="mt-3 space-y-2 text-xs text-[--app-muted]">
                  <p>
                    Compared v{analytics.changes.latest_version_from ?? "?"} to v
                    {analytics.changes.latest_version_to ?? "?"}.
                  </p>
                  <p>
                    {String((analytics.changes.latest_version_summary?.changed_count as number | undefined) ?? 0)} changed ·{" "}
                    {String((analytics.changes.latest_version_summary?.added_count as number | undefined) ?? 0)} added ·{" "}
                    {String((analytics.changes.latest_version_summary?.removed_count as number | undefined) ?? 0)} removed
                  </p>
                </div>
              ) : (
                <p className="mt-3 text-xs text-[--app-muted]">
                  No prior version delta is available yet.
                </p>
              )}
              {(analytics.risks ?? []).slice(0, 3).map((risk, index) => (
                <div
                  key={`risk-${index}`}
                  className="mt-3 rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring]"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-semibold text-[--app-fg]">{risk.title}</p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] ${riskLevelClass(risk.level)}`}
                    >
                      {risk.level}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-[--app-muted]">{risk.detail}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Trend history */}
          <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                  Trend history
                </p>
                <p className="mt-1 text-xs text-[--app-muted]">
                  Recent analytics snapshots show how the policy set has behaved over time.
                </p>
              </div>
              <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                {String(analytics.history?.sample_count ?? 0)} samples
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-4">
              {[
                { label: "Eval trend", value: analytics.history?.deltas?.evaluation_count, invertColor: true },
                { label: "Deny trend", value: analytics.history?.deltas?.deny_count, invertColor: false },
                { label: "Queue trend", value: analytics.history?.deltas?.pending_proposals, invertColor: false },
                { label: "Risk trend", value: analytics.history?.deltas?.risk_count, invertColor: false },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring]">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                    {item.label}
                  </p>
                  <div className="mt-2">
                    <TrendIndicator
                      value={item.value as number | undefined}
                      invertColor={item.invertColor}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr,0.8fr]">
              <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring]">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                  Recent snapshots
                </p>
                <div className="mt-3 space-y-2">
                  {((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? [])
                    .slice(-6)
                    .map((snapshot, index) => (
                      <div
                        key={`analytics-snapshot-${index}`}
                        className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-[--app-muted]">
                          <span>{String(snapshot.captured_at ?? "Unknown time")}</span>
                          <span>v{String(snapshot.current_version ?? "live")}</span>
                        </div>
                        <p className="mt-2 text-xs text-[--app-muted]">
                          {String(snapshot.deny_count ?? 0)} denials ·{" "}
                          {String(snapshot.pending_proposals ?? 0)} open proposals ·{" "}
                          {String(snapshot.risk_count ?? 0)} active risks
                        </p>
                      </div>
                    ))}
                  {(((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? []).length === 0) ? (
                    <p className="text-xs text-[--app-muted]">
                      Trend history will start filling in as policy changes are reviewed.
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="rounded-2xl border border-[--app-border] bg-[--app-surface] p-3 ring-1 ring-[--app-surface-ring]">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                  Recent promotions
                </p>
                <div className="mt-3 space-y-2">
                  {(analytics.history?.recent_promotions ?? []).slice(0, 4).map((promotion, index) => (
                    <div
                      key={`analytics-promotion-${promotion.promotion_id ?? index}`}
                      className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-[--app-fg]">
                          {promotion.source_environment ?? "source"} →{" "}
                          {promotion.target_environment ?? "target"}
                        </p>
                        <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                          {promotion.status ?? "staged"}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-[--app-muted]">
                        {promotion.note || "Promotion tracked through the policy workflow."}
                      </p>
                    </div>
                  ))}
                  {((analytics.history?.recent_promotions ?? []).length === 0) ? (
                    <p className="text-xs text-[--app-muted]">
                      No environment promotions have been staged yet.
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Bundles ──────────────────────────────────────────────── */}
        <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
          <div className="space-y-1">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
              Reusable bundles
            </p>
            <h2 className="text-xl font-semibold text-[--app-fg]">
              Start from proven policy packs
            </h2>
            <p className="text-xs text-[--app-muted]">
              Bundles stage full-chain proposals for common registry operating modes.
            </p>
          </div>

          <div className="mt-4 flex flex-col gap-3">
            {bundles.length === 0 ? (
              <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
                <p className="text-xs text-[--app-muted]">
                  No reusable bundles are available yet.
                </p>
              </div>
            ) : (
              bundles.map((bundle) => (
                <article
                  key={bundle.bundle_id}
                  className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold text-[--app-fg]">
                          {bundle.title ?? bundle.bundle_id}
                        </p>
                        <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                          {bundle.risk_posture ?? "bundle"}
                        </span>
                      </div>
                      <p className="text-xs text-[--app-muted]">
                        {bundle.summary ?? bundle.description}
                      </p>
                      <p className="text-[11px] text-[--app-muted]">
                        {bundle.provider_count ?? 0} steps · Best for{" "}
                        {(bundle.recommended_environments ?? []).join(", ") || "any environment"}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void onStageBundle(bundle.bundle_id, bundle.title ?? bundle.bundle_id)}
                      disabled={busyKey === `bundle-${bundle.bundle_id}`}
                      className="rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
                    >
                      {busyKey === `bundle-${bundle.bundle_id}` ? "Staging\u2026" : "Stage bundle"}
                    </button>
                  </div>
                  <ul className="mt-3 space-y-1 text-[10px] text-[--app-muted]">
                    {(bundle.provider_summaries ?? []).slice(0, 3).map((summary, index) => (
                      <li key={`${bundle.bundle_id}-summary-${index}`}>
                        \u2022 {summary}
                      </li>
                    ))}
                  </ul>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  subtitle,
}: {
  label: string;
  value: string;
  subtitle: string;
}) {
  return (
    <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold text-[--app-fg]">{value}</p>
      <p className="mt-1 text-[11px] text-[--app-muted]">{subtitle}</p>
    </div>
  );
}
