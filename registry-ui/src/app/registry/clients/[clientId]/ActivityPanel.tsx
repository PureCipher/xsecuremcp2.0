"use client";

import { useEffect, useMemo, useState } from "react";

import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  IconButton,
  Tooltip,
  Typography,
} from "@mui/material";

import type {
  ClientActivitySummary,
  ClientGovernanceResponse,
} from "@/lib/registryClient";

type Props = {
  slug: string;
  initialGovernance: ClientGovernanceResponse | null;
};

const REFRESH_INTERVAL_MS = 10_000;

const STATUS_COPY: Record<
  string,
  { label: string; color: "success" | "info" | "warning" | "default" }
> = {
  live: { label: "Live", color: "success" },
  recent: { label: "Recent", color: "info" },
  idle: { label: "Idle", color: "warning" },
  dormant: { label: "Dormant", color: "default" },
  never: { label: "Never seen", color: "default" },
};

function formatRelative(iso?: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return iso;
  const diffSec = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}min ago`;
  if (diffSec < 86_400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86_400)}d ago`;
}

function formatIdle(seconds?: number | null): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}min`;
  if (s < 86_400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86_400)}d`;
}

export function ActivityPanel({ slug, initialGovernance }: Props) {
  const [governance, setGovernance] = useState<ClientGovernanceResponse | null>(
    initialGovernance,
  );
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [tick, setTick] = useState(0); // forces re-render of relative timestamps

  // Poll the governance route every REFRESH_INTERVAL_MS to keep the
  // activity feed live without making the operator hit reload. We
  // hit the same route the page first rendered with — the
  // sanitization that was applied server-side stays consistent
  // across refreshes.
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function refresh() {
      setRefreshing(true);
      setRefreshError(null);
      try {
        const res = await fetch(
          `/api/clients/${encodeURIComponent(slug)}/governance`,
          { cache: "no-store" },
        );
        if (!res.ok) {
          if (!cancelled) {
            setRefreshError(`refresh failed (${res.status})`);
          }
          return;
        }
        const data = (await res.json()) as ClientGovernanceResponse;
        if (!cancelled) setGovernance(data);
      } catch (err) {
        if (!cancelled) {
          setRefreshError(
            err instanceof Error ? err.message : "refresh failed",
          );
        }
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    }

    timer = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (timer != null) clearInterval(timer);
    };
  }, [slug]);

  // Bump a tick every 5s so the relative timestamps re-format
  // ("3s ago" → "8s ago") even when no new data has arrived.
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 5_000);
    return () => clearInterval(t);
  }, []);

  const activity: ClientActivitySummary | undefined = governance?.activity;
  const recentRecords = governance?.ledger?.recent_records ?? [];

  const statusKey = activity?.status_label ?? "never";
  const statusCopy = STATUS_COPY[statusKey] ?? STATUS_COPY.never;

  const buckets = useMemo(
    () => activity?.hourly_buckets ?? [],
    [activity?.hourly_buckets],
  );
  const maxBucket = useMemo(
    () => buckets.reduce((m, b) => Math.max(m, b.count), 0),
    [buckets],
  );

  return (
    <Card variant="outlined">
      <CardContent>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 1,
            flexWrap: "wrap",
          }}
        >
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Activity
          </Typography>

          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Tooltip title={refreshError || "Auto-refreshes every 10s"}>
              <Chip
                size="small"
                label={
                  refreshing
                    ? "Refreshing…"
                    : refreshError
                      ? "Stale"
                      : `Updated ${formatRelative(governance?.generated_at)}`
                }
                color={refreshError ? "warning" : "default"}
                variant="outlined"
              />
            </Tooltip>
            <RefreshButton
              busy={refreshing}
              onClick={async () => {
                setRefreshing(true);
                setRefreshError(null);
                try {
                  const res = await fetch(
                    `/api/clients/${encodeURIComponent(slug)}/governance`,
                    { cache: "no-store" },
                  );
                  if (res.ok) {
                    const data =
                      (await res.json()) as ClientGovernanceResponse;
                    setGovernance(data);
                  } else {
                    setRefreshError(`refresh failed (${res.status})`);
                  }
                } catch (err) {
                  setRefreshError(
                    err instanceof Error ? err.message : "refresh failed",
                  );
                } finally {
                  setRefreshing(false);
                }
              }}
            />
          </Box>
        </Box>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 2,
            gridTemplateColumns: {
              xs: "1fr",
              md: "minmax(0, 0.9fr) minmax(0, 1.1fr)",
            },
          }}
        >
          <Box sx={{ display: "grid", gap: 1.5 }}>
            <Box
              sx={{
                p: 2,
                borderRadius: 2,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                display: "grid",
                gap: 1,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Chip
                  label={statusCopy.label}
                  color={statusCopy.color}
                  sx={{ fontWeight: 800 }}
                />
                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  {activity?.last_seen_at
                    ? `last seen ${formatRelative(activity.last_seen_at)}` +
                      (activity.last_seen_source
                        ? ` · via ${activity.last_seen_source}`
                        : "")
                    : "no activity recorded yet"}
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                {`Idle ${formatIdle(activity?.idle_seconds)} · ` +
                  `${activity?.calls_last_hour ?? 0} call(s) in last hour · ` +
                  `${activity?.calls_last_24h ?? 0} in last 24h`}
              </Typography>
              {/* Tick read so React keeps this block subscribed to the
                  5s timer for relative-timestamp re-rendering. */}
              <Box sx={{ display: "none" }}>{tick}</Box>
            </Box>

            <Sparkline buckets={buckets} max={maxBucket} />

            <Box>
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  fontWeight: 800,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Top resources (last 24h)
              </Typography>
              {(activity?.top_resources ?? []).length === 0 ? (
                <Typography
                  variant="caption"
                  sx={{ color: "var(--app-muted)" }}
                >
                  No resource calls observed.
                </Typography>
              ) : (
                <Box sx={{ mt: 0.5, display: "grid", gap: 0.5 }}>
                  {(activity?.top_resources ?? []).map((row) => (
                    <Box
                      key={row.resource_id}
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 1,
                        py: 0.5,
                        px: 1,
                        borderRadius: 1.5,
                        bgcolor: "var(--app-control-bg)",
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ fontFamily: "monospace" }}
                      >
                        {row.resource_id}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 700, color: "var(--app-fg)" }}
                      >
                        {row.count}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          </Box>

          <Box>
            <Typography
              variant="caption"
              sx={{
                display: "block",
                fontWeight: 800,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Recent calls
            </Typography>
            {recentRecords.length === 0 ? (
              <Typography
                variant="caption"
                sx={{ color: "var(--app-muted)" }}
              >
                No ledger records for this client yet. Records appear here once
                the client makes its first authenticated call.
              </Typography>
            ) : (
              <Box
                sx={{
                  mt: 1,
                  display: "grid",
                  gap: 0.5,
                  maxHeight: 360,
                  overflowY: "auto",
                  pr: 0.5,
                }}
              >
                {recentRecords.slice(0, 50).map((row, idx) => (
                  <Box
                    key={row.record_id ?? `record-${idx}`}
                    sx={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr auto",
                      gap: 1,
                      alignItems: "baseline",
                      py: 0.5,
                      px: 1,
                      borderRadius: 1.5,
                      bgcolor: "var(--app-control-bg)",
                    }}
                  >
                    <Chip
                      size="small"
                      label={row.action ?? "call"}
                      sx={{ fontSize: 10, height: 18 }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontFamily: "monospace",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {row.resource_id ?? "—"}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ color: "var(--app-muted)" }}
                    >
                      {formatRelative(row.timestamp)}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        </Box>

        <Divider sx={{ mt: 2, borderColor: "var(--app-border)" }} />
        <Typography
          variant="caption"
          sx={{
            display: "block",
            mt: 1.5,
            color: "var(--app-muted)",
            fontSize: 10,
          }}
        >
          Activity is recomputed from the provenance ledger every poll —
          there&apos;s no separate metrics store. Suspended clients keep
          their history visible; revoking tokens stops new records but
          doesn&apos;t erase old ones.
        </Typography>
      </CardContent>
    </Card>
  );
}

function RefreshButton({
  busy,
  onClick,
}: {
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <Tooltip title="Refresh now">
      <span>
        <IconButton size="small" onClick={onClick} disabled={busy}>
          <RefreshIcon spinning={busy} />
        </IconButton>
      </span>
    </Tooltip>
  );
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <Box
      component="svg"
      viewBox="0 0 24 24"
      sx={{
        width: 16,
        height: 16,
        fill: "currentColor",
        animation: spinning ? "spin 0.9s linear infinite" : "none",
        "@keyframes spin": { to: { transform: "rotate(360deg)" } },
      }}
    >
      <path d="M17.65 6.35A8 8 0 1 0 19.32 15h-2.1a6 6 0 1 1-1.05-7.95L13 10h7V3l-2.35 3.35Z" />
    </Box>
  );
}

function Sparkline({
  buckets,
  max,
}: {
  buckets: { hour_offset: number; count: number }[];
  max: number;
}) {
  // Buckets come oldest-last in our payload (offset 0 = current hour,
  // 23 = 23h ago). For a left-to-right "older → newer" sparkline we
  // reverse them.
  const ordered = [...buckets].sort((a, b) => b.hour_offset - a.hour_offset);
  const width = 240;
  const height = 60;
  const stepX = ordered.length > 1 ? width / (ordered.length - 1) : width;
  const safeMax = Math.max(1, max);

  const points = ordered
    .map((b, i) => {
      const x = i * stepX;
      const y = height - (b.count / safeMax) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <Box>
      <Typography
        variant="caption"
        sx={{
          display: "block",
          fontWeight: 800,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        Calls per hour (last 24h)
      </Typography>
      <Box
        sx={{
          mt: 0.75,
          p: 1,
          borderRadius: 2,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
        }}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height="60"
          preserveAspectRatio="none"
          aria-label="hourly call count sparkline"
        >
          <polyline
            points={points}
            fill="none"
            stroke="var(--app-accent)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {ordered.map((b, i) => {
            if (b.count === 0) return null;
            const x = i * stepX;
            const y = height - (b.count / safeMax) * (height - 4) - 2;
            return (
              <circle
                key={b.hour_offset}
                cx={x}
                cy={y}
                r={1.5}
                fill="var(--app-accent)"
              />
            );
          })}
        </svg>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            mt: 0.5,
          }}
        >
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            -24h
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            now
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
