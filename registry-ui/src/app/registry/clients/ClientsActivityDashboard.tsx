"use client";

import { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Tooltip,
  Typography,
} from "@mui/material";
import type { ClientsActivitySummaryResponse } from "@/lib/registryClient";

const REFRESH_INTERVAL_MS = 30_000;

const KIND_LABELS: Record<string, string> = {
  agent: "Agent",
  service: "Service",
  framework: "Framework",
  tooling: "Tooling",
  other: "Other",
};

/**
 * Iter 14.24 — Clients activity dashboard panel.
 *
 * Renders above the directory at ``/registry/clients`` and shows a
 * single glance view of "what's happening with my clients right now":
 *
 * - Total count, with active vs suspended split
 * - Live / recent / idle / dormant / never-seen counts based on the
 *   same status thresholds the per-client ActivityPanel uses
 * - 24-hour rollup of total calls across every client
 * - Recently-onboarded badge (last 7 days)
 * - Kind histogram (agent / service / framework / tooling / other)
 *
 * Backed by GET /registry/clients/activity-summary which loops
 * every client's ledger window once. Auto-refreshes every 30s so a
 * curator can leave the page open during an incident and watch the
 * idle/dormant counts move.
 */
export function ClientsActivityDashboard({
  initialSummary,
}: {
  initialSummary: ClientsActivitySummaryResponse | null;
}) {
  const [summary, setSummary] = useState<ClientsActivitySummaryResponse | null>(
    initialSummary,
  );
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      setRefreshing(true);
      try {
        const response = await fetch("/api/clients/activity-summary", {
          cache: "no-store",
        });
        if (!cancelled && response.ok) {
          const payload = (await response.json()) as ClientsActivitySummaryResponse;
          setSummary(payload);
        }
      } catch {
        // Silent — keep the previous payload visible. The refreshing
        // indicator will turn off so the user knows the timer ticked.
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    }
    const timer = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (!summary || summary.error || (summary.total ?? 0) === 0) {
    return null;
  }

  const total = summary.total ?? 0;
  const activity = summary.by_activity_status ?? {};
  const live = activity.live ?? 0;
  const recent = activity.recent ?? 0;
  const idle = activity.idle ?? 0;
  const dormant = activity.dormant ?? 0;
  const never = activity.never ?? 0;
  const admin = summary.by_admin_status ?? {};
  const active = admin.active ?? 0;
  const suspended = admin.suspended ?? 0;
  const recentlyOnboarded = summary.recently_onboarded_count ?? 0;
  const callsLast24h = summary.calls_last_24h_total ?? 0;
  const byKind = summary.by_kind ?? {};

  // The "active right now" rollup: live + recent. This is the number
  // an admin glances at during an incident — "is anything actually
  // talking to us right now" — separate from the broader "active"
  // admin lifecycle status.
  const activeNow = live + recent;

  return (
    <Card variant="outlined" sx={{ bgcolor: "var(--app-surface)" }}>
      <CardContent sx={{ p: 2.5 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            mb: 2,
            gap: 1,
            flexWrap: "wrap",
          }}
        >
          <Box>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Activity overview
            </Typography>
            <Typography
              variant="h6"
              sx={{ fontWeight: 700, color: "var(--app-fg)" }}
            >
              {total} client{total === 1 ? "" : "s"} registered
            </Typography>
          </Box>
          <Tooltip
            title={
              refreshing
                ? "Refreshing…"
                : `Auto-refresh every ${REFRESH_INTERVAL_MS / 1000}s · last update ${
                    summary.generated_at
                      ? new Date(summary.generated_at).toLocaleTimeString()
                      : "—"
                  }`
            }
          >
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                gap: 0.5,
                fontSize: 11,
                color: "var(--app-muted)",
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  bgcolor: refreshing
                    ? "var(--app-accent)"
                    : "var(--app-muted)",
                  opacity: refreshing ? 1 : 0.4,
                  transition: "opacity 200ms ease",
                }}
              />
              {refreshing ? "Refreshing…" : "Live"}
            </Box>
          </Tooltip>
        </Box>

        {/* Headline metric cards — five columns on wide screens. The
            first card calls out the "active now" rollup which is the
            most-asked question during operator review. */}
        <Box
          sx={{
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: {
              xs: "1fr 1fr",
              md: "repeat(5, minmax(0, 1fr))",
            },
          }}
        >
          <StatCard
            label="Active now"
            value={String(activeNow)}
            sub={
              activeNow === 0
                ? "no live or recent traffic"
                : `${live} live · ${recent} recent`
            }
            emphasis={activeNow > 0}
          />
          <StatCard
            label="Idle"
            value={String(idle)}
            sub="last hit ≤24h ago"
          />
          <StatCard
            label="Dormant"
            value={String(dormant)}
            sub="last hit >24h ago"
            warning={dormant > 0}
          />
          <StatCard
            label="Never seen"
            value={String(never)}
            sub="onboarded but no signal"
          />
          <StatCard
            label="Calls (24h)"
            value={callsLast24h.toLocaleString()}
            sub="ledger total across clients"
          />
        </Box>

        {/* Secondary row: admin lifecycle + recent onboards + kind chips */}
        <Box
          sx={{
            mt: 2,
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 2,
          }}
        >
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center" }}>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
                mr: 0.5,
              }}
            >
              Lifecycle
            </Typography>
            <Chip
              size="small"
              label={`${active} active`}
              sx={{
                bgcolor: "var(--app-control-active-bg)",
                color: "var(--app-fg)",
                fontSize: 11,
                fontWeight: 700,
              }}
            />
            {suspended > 0 ? (
              <Chip
                size="small"
                label={`${suspended} suspended`}
                sx={{
                  bgcolor: "rgba(244, 63, 94, 0.10)",
                  color: "#b91c1c",
                  fontSize: 11,
                  fontWeight: 700,
                }}
              />
            ) : null}
            {recentlyOnboarded > 0 ? (
              <Chip
                size="small"
                label={`+${recentlyOnboarded} this week`}
                sx={{
                  bgcolor: "var(--app-surface)",
                  color: "var(--app-muted)",
                  fontSize: 11,
                  fontWeight: 700,
                  border: "1px solid var(--app-border)",
                }}
              />
            ) : null}
          </Box>

          {Object.keys(byKind).length > 0 ? (
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center" }}>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                  mr: 0.5,
                }}
              >
                By kind
              </Typography>
              {Object.entries(byKind)
                .sort(([, a], [, b]) => b - a)
                .map(([kind, count]) => (
                  <Chip
                    key={kind}
                    size="small"
                    label={`${KIND_LABELS[kind] ?? kind} · ${count}`}
                    sx={{
                      bgcolor: "var(--app-surface)",
                      color: "var(--app-muted)",
                      fontSize: 11,
                      fontWeight: 600,
                      border: "1px solid var(--app-border)",
                    }}
                  />
                ))}
            </Box>
          ) : null}
        </Box>
      </CardContent>
    </Card>
  );
}

function StatCard({
  label,
  value,
  sub,
  emphasis,
  warning,
}: {
  label: string;
  value: string;
  sub: string;
  emphasis?: boolean;
  warning?: boolean;
}) {
  const valueColor = warning
    ? "#b91c1c"
    : emphasis
      ? "var(--app-fg)"
      : "var(--app-fg)";
  return (
    <Box
      sx={{
        p: 1.75,
        borderRadius: 2.5,
        border: "1px solid",
        borderColor: emphasis
          ? "var(--app-accent)"
          : warning
            ? "rgba(248, 113, 113, 0.4)"
            : "var(--app-border)",
        bgcolor: emphasis
          ? "var(--app-control-active-bg)"
          : warning
            ? "rgba(244, 63, 94, 0.06)"
            : "var(--app-control-bg)",
      }}
    >
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{
          mt: 0.5,
          fontSize: 26,
          lineHeight: 1.1,
          fontWeight: 800,
          color: valueColor,
        }}
      >
        {value}
      </Typography>
      <Typography sx={{ mt: 0.25, fontSize: 11, color: "var(--app-muted)" }}>
        {sub}
      </Typography>
    </Box>
  );
}

