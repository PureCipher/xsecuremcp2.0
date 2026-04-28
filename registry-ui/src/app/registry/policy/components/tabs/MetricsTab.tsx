"use client";

import { useMemo, useState } from "react";
import type {
  PolicyAnalyticsResponse,
  RegistryPayload,
} from "@/lib/registryClient";
import { Box, Button, Card, CardContent, Chip, Typography } from "@mui/material";

type MetricsTabProps = {
  analytics: PolicyAnalyticsResponse;
};

/**
 * Iter 14.16 — Metrics tab.
 *
 * Lifted out of the legacy Overview tab as part of splitting two
 * different workflows that don't belong on the same page (see
 * :file:`CatalogTab.tsx` for the picking workflow). This tab is a
 * monitoring dashboard: live deny patterns, version-change deltas,
 * trend history, recent snapshots, recent promotions.
 *
 * Iter 14.13 — every empty-prone widget is wrapped in
 * :func:`CollapsibleEmptyCard` so a fresh registry sees compact
 * placeholders rather than a stack of "no X yet" cards.
 */

function riskLevelSx(level: string | undefined): Record<string, unknown> {
  switch (level?.toLowerCase()) {
    case "critical":
      return { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c", border: "1px solid rgba(248, 113, 113, 0.28)" };
    case "high":
      return { bgcolor: "rgba(244, 63, 94, 0.12)", color: "#be123c", border: "1px solid rgba(251, 113, 133, 0.28)" };
    case "medium":
      return { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e", border: "1px solid rgba(251, 191, 36, 0.28)" };
    case "low":
      return { bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", border: "1px solid var(--app-accent)" };
    default:
      return { bgcolor: "rgba(100, 116, 139, 0.12)", color: "var(--app-muted)", border: "1px solid var(--app-border)" };
  }
}

function TrendIndicator({ value, invertColor }: { value: number | undefined; invertColor?: boolean }) {
  const num = Number(value ?? 0);
  if (num === 0) {
    return (
      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
        <Typography component="span" sx={{ fontSize: 14, color: "var(--app-muted)" }}>
          —
        </Typography>
        <Typography component="span" sx={{ fontSize: 11, fontWeight: 600, color: "var(--app-muted)" }}>
          no change
        </Typography>
      </Box>
    );
  }

  // For deny/risk counts, "up" is bad (red) and "down" is good (green).
  // For eval counts, "up" is good — use invertColor to flip.
  const isUp = num > 0;
  const isGood = invertColor ? isUp : !isUp;

  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        fontSize: 11,
        fontWeight: 700,
        color: isGood ? "var(--app-muted)" : "#be123c",
      }}
    >
      <Box
        component="svg"
        viewBox="0 0 12 12"
        sx={{ width: 12, height: 12, transform: isUp ? "none" : "rotate(180deg)" }}
        fill="currentColor"
      >
        <path d="M6 2l4 6H2z" />
      </Box>
      <Box component="span">{isUp ? "+" : ""}{num}</Box>
    </Box>
  );
}

export function MetricsTab({ analytics }: MetricsTabProps) {
  const topDeniedResources = useMemo(() => {
    const auditResources = analytics.blocked?.audit?.top_denied_resources;
    if (Array.isArray(auditResources)) return auditResources as RegistryPayload[];
    const monitorWindow = analytics.blocked?.monitor?.window as RegistryPayload | undefined;
    const monitorResources = monitorWindow?.top_denied_resources;
    if (Array.isArray(monitorResources)) return monitorResources as RegistryPayload[];
    return [] as RegistryPayload[];
  }, [analytics.blocked?.audit?.top_denied_resources, analytics.blocked?.monitor]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Card variant="outlined">
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Policy analytics
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              See what is blocked, changed, and risky
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Live deny patterns, recent changes, and rollout risk at a glance.
            </Typography>
          </Box>

          {/* Key metrics */}
          <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr 1fr" } }}>
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
          </Box>

          {/* Most blocked + version changes */}
          <Box sx={{ mt: 2, display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
            <CollapsibleEmptyCard
              hasData={topDeniedResources.length > 0}
              compactLabel="No deny hot spots recorded yet"
            >
              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Most blocked resources
                  </Typography>
                  <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0, mt: 1.5, display: "grid", gap: 1 }}>
                    {topDeniedResources.slice(0, 4).map((item, index) => (
                      <Card
                        key={`top-denied-${index}`}
                        component="li"
                        variant="outlined"
                        sx={{ bgcolor: "var(--app-surface)" }}
                      >
                        <CardContent sx={{ p: 1.5 }}>
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            {String(item.resource_id ?? "unknown")} · {String(item.count ?? 0)} denials
                          </Typography>
                        </CardContent>
                      </Card>
                    ))}
                    {topDeniedResources.length === 0 ? (
                      <Typography component="li" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        No deny hot spots have been recorded yet.
                      </Typography>
                    ) : null}
                  </Box>
                </CardContent>
              </Card>
            </CollapsibleEmptyCard>

            <CollapsibleEmptyCard
              hasData={
                Boolean(analytics.changes?.latest_version_summary) ||
                (analytics.risks?.length ?? 0) > 0
              }
              compactLabel="No prior version delta or active risks"
            >
              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Recent version change
                  </Typography>
                  {analytics.changes?.latest_version_summary ? (
                    <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        Compared v{analytics.changes.latest_version_from ?? "?"} to v{analytics.changes.latest_version_to ?? "?"}.
                      </Typography>
                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        {String((analytics.changes.latest_version_summary?.changed_count as number | undefined) ?? 0)} changed ·{" "}
                        {String((analytics.changes.latest_version_summary?.added_count as number | undefined) ?? 0)} added ·{" "}
                        {String((analytics.changes.latest_version_summary?.removed_count as number | undefined) ?? 0)} removed
                      </Typography>
                    </Box>
                  ) : (
                    <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
                      No prior version delta is available yet.
                    </Typography>
                  )}
                  {(analytics.risks ?? []).slice(0, 3).map((risk, index) => (
                    <Card
                      key={`risk-${index}`}
                      variant="outlined"
                      sx={{ mt: 1.5, bgcolor: "var(--app-surface)" }}
                    >
                      <CardContent sx={{ p: 1.5 }}>
                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                          <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                            {risk.title}
                          </Typography>
                          <Chip
                            size="small"
                            label={risk.level}
                            sx={{
                              fontSize: 10,
                              fontWeight: 700,
                              letterSpacing: "0.01em",
                              height: 22,
                              ...riskLevelSx(risk.level),
                            }}
                          />
                        </Box>
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          {risk.detail}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </CardContent>
              </Card>
            </CollapsibleEmptyCard>
          </Box>

          {/* Trend history */}
          <Card variant="outlined" sx={{ mt: 2, bgcolor: "var(--app-control-bg)" }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                <Box sx={{ minWidth: 240 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                    Trend history
                  </Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                    Recent analytics snapshots show how the policy set has behaved over time.
                  </Typography>
                </Box>
                <Chip
                  size="small"
                  label={`${String(analytics.history?.sample_count ?? 0)} samples`}
                  sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 11, fontWeight: 700, letterSpacing: "0.01em" }}
                />
              </Box>

              <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr 1fr 1fr" } }}>
                {[
                  { label: "Eval trend", value: analytics.history?.deltas?.evaluation_count, invertColor: true },
                  { label: "Deny trend", value: analytics.history?.deltas?.deny_count, invertColor: false },
                  { label: "Queue trend", value: analytics.history?.deltas?.pending_proposals, invertColor: false },
                  { label: "Risk trend", value: analytics.history?.deltas?.risk_count, invertColor: false },
                ].map((item) => (
                  <Card key={item.label} variant="outlined" sx={{ bgcolor: "var(--app-surface)" }}>
                    <CardContent sx={{ p: 1.5 }}>
                      <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        {item.label}
                      </Typography>
                      <Box sx={{ mt: 1 }}>
                        <TrendIndicator value={item.value as number | undefined} invertColor={item.invertColor} />
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Box>

              <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.2fr) minmax(0,0.8fr)" } }}>
                <CollapsibleEmptyCard
                  hasData={
                    (((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? []).length) > 0
                  }
                  compactLabel="No trend snapshots yet"
                >
                  <Card variant="outlined" sx={{ bgcolor: "var(--app-surface)" }}>
                    <CardContent sx={{ p: 1.5 }}>
                      <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Recent snapshots
                      </Typography>
                      <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
                        {((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? [])
                          .slice(-6)
                          .map((snapshot, index) => (
                            <Card
                              key={`analytics-snapshot-${index}`}
                              variant="outlined"
                              sx={{ bgcolor: "var(--app-control-bg)" }}
                            >
                              <CardContent sx={{ p: 1.5 }}>
                                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                  <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                                    {String(snapshot.captured_at ?? "Unknown time")}
                                  </Typography>
                                  <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                                    v{String(snapshot.current_version ?? "live")}
                                  </Typography>
                                </Box>
                                <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                  {String(snapshot.deny_count ?? 0)} denials · {String(snapshot.pending_proposals ?? 0)} open proposals ·{" "}
                                  {String(snapshot.risk_count ?? 0)} active risks
                                </Typography>
                              </CardContent>
                            </Card>
                          ))}
                        {(((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? []).length === 0) ? (
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            Trend history will start filling in as policy changes are reviewed.
                          </Typography>
                        ) : null}
                      </Box>
                    </CardContent>
                  </Card>
                </CollapsibleEmptyCard>

                <CollapsibleEmptyCard
                  hasData={(analytics.history?.recent_promotions ?? []).length > 0}
                  compactLabel="No environment promotions staged yet"
                >
                  <Card variant="outlined" sx={{ bgcolor: "var(--app-surface)" }}>
                    <CardContent sx={{ p: 1.5 }}>
                      <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Recent promotions
                      </Typography>
                      <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
                        {(analytics.history?.recent_promotions ?? []).slice(0, 4).map((promotion, index) => (
                          <Card
                            key={`analytics-promotion-${promotion.promotion_id ?? index}`}
                            variant="outlined"
                            sx={{ bgcolor: "var(--app-control-bg)" }}
                          >
                            <CardContent sx={{ p: 1.5 }}>
                              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                                <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                                  {promotion.source_environment ?? "source"} -&gt; {promotion.target_environment ?? "target"}
                                </Typography>
                                <Chip
                                  size="small"
                                  label={promotion.status ?? "staged"}
                                  sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 11, fontWeight: 700, letterSpacing: "0.01em" }}
                                />
                              </Box>
                              <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                {promotion.note || "Promotion tracked through the policy workflow."}
                              </Typography>
                            </CardContent>
                          </Card>
                        ))}
                        {((analytics.history?.recent_promotions ?? []).length === 0) ? (
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            No environment promotions have been staged yet.
                          </Typography>
                        ) : null}
                      </Box>
                    </CardContent>
                  </Card>
                </CollapsibleEmptyCard>
              </Box>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </Box>
  );
}

/**
 * Iter 14.13 — Collapsible empty-state wrapper. When a widget would
 * render an empty placeholder, this collapses to a single-line summary
 * with a "Show details" toggle that re-expands to the full content.
 */
function CollapsibleEmptyCard({
  hasData,
  compactLabel,
  children,
}: {
  hasData: boolean;
  compactLabel: string;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  if (hasData || expanded) {
    return <>{children}</>;
  }
  return (
    <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
      <CardContent
        sx={{
          p: 1.25,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1.5,
          "&:last-child": { pb: 1.25 },
        }}
      >
        <Typography sx={{ fontSize: 12, color: "var(--app-muted)", flex: 1, minWidth: 0 }}>
          {compactLabel}
        </Typography>
        <Button
          size="small"
          variant="text"
          onClick={() => setExpanded(true)}
          sx={{
            textTransform: "none",
            fontSize: 11,
            fontWeight: 700,
            color: "var(--app-muted)",
            flexShrink: 0,
            px: 0.75,
            "&:hover": { bgcolor: "transparent", color: "var(--app-fg)" },
          }}
        >
          Show details →
        </Button>
      </CardContent>
    </Card>
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
    <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
      <CardContent sx={{ p: 2 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          {label}
        </Typography>
        <Typography sx={{ mt: 1, fontSize: 24, fontWeight: 800, color: "var(--app-fg)" }}>
          {value}
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
          {subtitle}
        </Typography>
      </CardContent>
    </Card>
  );
}
