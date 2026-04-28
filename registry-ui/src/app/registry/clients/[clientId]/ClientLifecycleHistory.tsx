"use client";

import { useEffect, useMemo, useState } from "react";
import { Box, Card, CardContent, Chip, Typography } from "@mui/material";
import type {
  ClientGovernanceDriftRow,
  ClientGovernanceLedgerRow,
  ClientGovernanceResponse,
  RegistryClientSummary,
  RegistryClientTokenSummary,
} from "@/lib/registryClient";

/**
 * Iter 14.35 — Client lifecycle history.
 *
 * Symmetric to Iter 14.31 on the listing side. Where that component
 * shows a version timeline with manifest-changed indicators, this
 * one shows an event timeline for a registered client: what
 * changed for *this principal* and when, classified by what kind
 * of change it represents.
 *
 * Three event classes, color-coded so the operator can scan the
 * history and immediately spot the moments that warrant a fresh
 * security review:
 *
 *   AUTHZ — anything that changes the client's authorization
 *     surface: token issued, token revoked, suspension, lifecycle
 *     creation. Warning chip.
 *
 *   DRIFT — reflexive-analyzer events plus ledger entries with
 *     deny-style actions. Info / severity chip.
 *
 *   ROUTINE — ordinary call-attribution rows from the ledger. Muted
 *     chip. Surfaced sparingly so the timeline doesn't drown in
 *     noise; the dedicated activity panel is the place for high-
 *     volume call browsing.
 *
 * Three data sources are merged here: the client's tokens (issue/
 * revoke moments), the governance ledger (recent_records), and the
 * reflexive analyzer (recent_drifts). All timestamps are normalized
 * to epoch ms before merging so a numeric-vs-string mismatch
 * doesn't desync the order.
 *
 * Suspension is inferred conservatively. The store stamps a
 * suspended_reason and updates updated_at when an admin suspends
 * — we surface that as one event but don't claim to render every
 * historical suspension/reinstatement (the registry doesn't keep
 * that history yet — a future iter could plumb a dedicated
 * lifecycle ledger).
 */

// ── Event model ───────────────────────────────────────────────

type EventClass = "authz" | "drift" | "routine";
type DriftSeverity = "low" | "medium" | "high" | "critical";

type LifecycleEvent = {
  /** ms since epoch, used for sort order. */
  ts: number;
  /** Pre-formatted absolute timestamp for display. */
  tsLabel: string;
  className: EventClass;
  title: string;
  detail?: string;
  /** Optional severity tag (used for drift events). */
  severity?: DriftSeverity;
  /** Stable React key — combines source kind + identifier. */
  key: string;
};

// ── Helpers ───────────────────────────────────────────────────

function epochSecondsToMs(value: number): number {
  // Heuristic: values < 10**12 are seconds, otherwise already ms.
  // Our backend emits seconds; defend against either.
  return value > 1_000_000_000_000 ? value : value * 1000;
}

function parseTimestamp(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) return null;
    return epochSecondsToMs(value);
  }
  // ISO string / RFC 3339.
  const ms = Date.parse(value);
  if (!Number.isFinite(ms)) return null;
  return ms;
}

function formatAbsolute(ms: number): string {
  try {
    return new Date(ms).toISOString();
  } catch {
    return String(ms);
  }
}

function formatRelative(ms: number, now: number): string {
  const diffSec = Math.max(0, Math.round((now - ms) / 1000));
  if (diffSec < 5) return "just now";
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}min ago`;
  if (diffSec < 86_400) return `${Math.round(diffSec / 3600)}h ago`;
  if (diffSec < 30 * 86_400) return `${Math.round(diffSec / 86_400)}d ago`;
  if (diffSec < 365 * 86_400) {
    return `${Math.round(diffSec / (30 * 86_400))}mo ago`;
  }
  return `${Math.round(diffSec / (365 * 86_400))}y ago`;
}

/**
 * Tiny child component that owns the "now" tick. We isolate the
 * Date.now() call here (a) so the parent stays a pure render (avoids
 * the react-hooks/purity rule) and (b) so refreshing the relative
 * timestamps doesn't re-render the whole event list — only this leaf.
 */
function RelativeTime({ ms, absolute }: { ms: number; absolute: string }) {
  // Lazy initial state: the function form of useState runs once on
  // first render only, isolating the impure Date.now() call. We
  // tick every 30s so labels age in place without thrashing the
  // page. Setting state inside setInterval is the canonical React
  // pattern for "subscribe to a clock"; eslint's set-state-in-effect
  // rule applies to the synchronous body, which we no longer use.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <Typography
      sx={{
        fontSize: 11,
        color: "var(--app-muted)",
        ml: "auto",
      }}
      title={absolute}
    >
      {formatRelative(ms, now)}
    </Typography>
  );
}

// Ledger actions that signal an authorization decision rather than
// a routine call. Anything matching is bumped from ROUTINE → DRIFT.
const DENY_ACTION_PATTERN = /(deny|denied|revok|reject|block|fail|error)/i;

// ── Class styling ────────────────────────────────────────────

function classSx(className: EventClass) {
  if (className === "authz") {
    return {
      bgcolor: "rgba(245, 158, 11, 0.12)",
      color: "#92400e",
      borderColor: "rgba(251, 191, 36, 0.4)",
    };
  }
  if (className === "drift") {
    return {
      bgcolor: "rgba(59, 130, 246, 0.10)",
      color: "#1e40af",
      borderColor: "rgba(96, 165, 250, 0.4)",
    };
  }
  return {
    bgcolor: "var(--app-control-bg)",
    color: "var(--app-muted)",
    borderColor: "var(--app-border)",
  };
}

function severitySx(severity: DriftSeverity | undefined) {
  if (severity === "critical" || severity === "high") {
    return {
      bgcolor: "rgba(244, 63, 94, 0.10)",
      color: "#b91c1c",
      borderColor: "rgba(248, 113, 113, 0.4)",
    };
  }
  if (severity === "medium") {
    return {
      bgcolor: "rgba(245, 158, 11, 0.12)",
      color: "#92400e",
      borderColor: "rgba(251, 191, 36, 0.4)",
    };
  }
  return null;
}

function classLabel(c: EventClass): string {
  if (c === "authz") return "AUTHZ";
  if (c === "drift") return "DRIFT";
  return "ROUTINE";
}

// ── Builders ──────────────────────────────────────────────────

function buildEventsFromTokens(
  tokens: RegistryClientTokenSummary[],
): LifecycleEvent[] {
  const events: LifecycleEvent[] = [];
  for (const t of tokens) {
    const createdMs = parseTimestamp(t.created_at);
    if (createdMs != null) {
      events.push({
        ts: createdMs,
        tsLabel: formatAbsolute(createdMs),
        className: "authz",
        title: `Token issued — "${t.name}"`,
        detail:
          `${t.secret_prefix}… · issued by ${t.created_by}` +
          (t.active ? " · still active" : " · subsequently revoked"),
        key: `token-issued-${t.token_id}`,
      });
    }
    const revokedMs = parseTimestamp(t.revoked_at);
    if (revokedMs != null) {
      events.push({
        ts: revokedMs,
        tsLabel: formatAbsolute(revokedMs),
        className: "authz",
        title: `Token revoked — "${t.name}"`,
        detail: `${t.secret_prefix}… · existing requests using this token now fail`,
        key: `token-revoked-${t.token_id}`,
      });
    }
  }
  return events;
}

function buildEventsFromClient(
  client: RegistryClientSummary,
): LifecycleEvent[] {
  const events: LifecycleEvent[] = [];

  const createdMs = parseTimestamp(client.created_at);
  if (createdMs != null) {
    events.push({
      ts: createdMs,
      tsLabel: formatAbsolute(createdMs),
      className: "authz",
      title: "Client registered",
      detail: `Owner: ${client.owner_publisher_id} · slug: ${client.slug}`,
      key: `client-created-${client.client_id}`,
    });
  }

  // Conservative inference: if the client is currently suspended,
  // the most recent updated_at is our best timestamp for the
  // suspension event. We label it as such but flag the
  // approximation in the detail string so the operator knows we
  // didn't reconstruct full history.
  if (client.status === "suspended") {
    const ms = parseTimestamp(client.updated_at) ?? parseTimestamp(client.created_at);
    if (ms != null) {
      events.push({
        ts: ms,
        tsLabel: formatAbsolute(ms),
        className: "authz",
        title: "Suspended",
        detail: client.suspended_reason
          ? `Reason: ${client.suspended_reason}`
          : "No reason recorded.",
        key: `client-suspended-${client.client_id}`,
      });
    }
  }

  return events;
}

function normalizeDriftSeverity(value: unknown): DriftSeverity | undefined {
  if (typeof value !== "string") return undefined;
  const v = value.trim().toLowerCase();
  if (v === "critical" || v === "high" || v === "medium" || v === "low") {
    return v;
  }
  return undefined;
}

function buildEventsFromDrifts(
  drifts: ClientGovernanceDriftRow[],
): LifecycleEvent[] {
  const events: LifecycleEvent[] = [];
  for (const [idx, d] of drifts.entries()) {
    const ms = parseTimestamp(d.timestamp);
    if (ms == null) continue;
    events.push({
      ts: ms,
      tsLabel: formatAbsolute(ms),
      className: "drift",
      title: `Drift: ${d.drift_type ?? "unknown drift"}`,
      detail:
        d.observed_value != null && d.baseline_value != null
          ? `Observed ${formatScalar(d.observed_value)} vs baseline ${formatScalar(d.baseline_value)}`
          : undefined,
      severity: normalizeDriftSeverity(d.severity),
      key: `drift-${d.event_id ?? idx}`,
    });
  }
  return events;
}

function buildEventsFromLedger(
  records: ClientGovernanceLedgerRow[],
  /** Cap the number of routine ledger rows so the timeline doesn't
   *  drown in call-tool noise. Drift-style rows are not capped. */
  routineCap: number,
): LifecycleEvent[] {
  const allEvents: LifecycleEvent[] = [];
  for (const [idx, r] of records.entries()) {
    const ms = parseTimestamp(r.timestamp);
    if (ms == null) continue;
    const action = r.action ?? "call";
    const isDeny = DENY_ACTION_PATTERN.test(action);
    allEvents.push({
      ts: ms,
      tsLabel: formatAbsolute(ms),
      className: isDeny ? "drift" : "routine",
      title: isDeny
        ? `Authorization denied — ${action}`
        : `Call: ${action}`,
      detail: r.resource_id
        ? `Resource: ${r.resource_id}` +
          (r.contract_id ? ` · contract ${r.contract_id}` : "")
        : r.contract_id
          ? `Contract ${r.contract_id}`
          : undefined,
      severity: isDeny ? "medium" : undefined,
      key: `ledger-${r.record_id ?? idx}`,
    });
  }
  // Keep all DRIFT-style rows; cap ROUTINE rows.
  const drift = allEvents.filter((e) => e.className === "drift");
  const routine = allEvents.filter((e) => e.className === "routine");
  routine.sort((a, b) => b.ts - a.ts);
  return [...drift, ...routine.slice(0, routineCap)];
}

function formatScalar(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number")
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "true" : "false";
  return JSON.stringify(value);
}

// ── Component ────────────────────────────────────────────────

export function ClientLifecycleHistory({
  client,
  tokens,
  governance,
}: {
  client: RegistryClientSummary;
  tokens: RegistryClientTokenSummary[];
  governance: ClientGovernanceResponse | null;
}) {
  // Build all event sources inside the memo so dependency tracking
  // operates on the stable inputs (tokens / client / governance
  // identity) rather than on intermediate arrays.
  const events = useMemo(() => {
    const tokenEvents = buildEventsFromTokens(tokens);
    const clientEvents = buildEventsFromClient(client);
    const driftEvents = buildEventsFromDrifts(
      governance?.reflexive?.recent_drifts ?? [],
    );
    const ledgerEvents = buildEventsFromLedger(
      governance?.ledger?.recent_records ?? [],
      6, // cap routine ledger rows so the timeline stays scannable
    );
    const merged = [
      ...tokenEvents,
      ...clientEvents,
      ...driftEvents,
      ...ledgerEvents,
    ];
    merged.sort((a, b) => b.ts - a.ts);
    return merged;
  }, [client, tokens, governance]);

  const visible = events.slice(0, 16);
  const hiddenCount = events.length - visible.length;

  return (
    <Card variant="outlined">
      <CardContent>
        <Box
          sx={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
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
            Lifecycle history
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Tokens · suspensions · drift · ledger denials, newest first.
          </Typography>
        </Box>

        {visible.length === 0 ? (
          <Typography
            sx={{
              mt: 2,
              fontSize: 12,
              color: "var(--app-muted)",
              fontStyle: "italic",
            }}
          >
            No lifecycle events recorded for this client yet. Events appear
            here as tokens are issued, suspensions happen, and the reflexive
            analyzer or ledger record decisions involving this slug.
          </Typography>
        ) : (
          <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
            {visible.map((event) => {
              const cls = classSx(event.className);
              const sev = severitySx(event.severity);
              return (
                <Box
                  key={event.key}
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    border: "1px solid var(--app-border)",
                    bgcolor: "var(--app-control-bg)",
                    display: "grid",
                    gap: 0.5,
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: 1,
                      flexWrap: "wrap",
                    }}
                  >
                    <Chip
                      size="small"
                      label={classLabel(event.className)}
                      sx={{
                        fontSize: 10,
                        height: 20,
                        fontWeight: 800,
                        letterSpacing: "0.06em",
                        border: "1px solid",
                        ...cls,
                      }}
                    />
                    {event.severity ? (
                      <Chip
                        size="small"
                        label={event.severity}
                        sx={{
                          fontSize: 10,
                          height: 20,
                          fontWeight: 700,
                          textTransform: "uppercase",
                          border: "1px solid",
                          ...(sev ?? {
                            bgcolor: "var(--app-surface)",
                            color: "var(--app-muted)",
                            borderColor: "var(--app-border)",
                          }),
                        }}
                      />
                    ) : null}
                    <Typography
                      sx={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: "var(--app-fg)",
                        lineHeight: 1.4,
                      }}
                    >
                      {event.title}
                    </Typography>
                    <RelativeTime ms={event.ts} absolute={event.tsLabel} />
                  </Box>
                  {event.detail ? (
                    <Typography
                      sx={{
                        fontSize: 12,
                        color: "var(--app-muted)",
                        lineHeight: 1.5,
                      }}
                    >
                      {event.detail}
                    </Typography>
                  ) : null}
                </Box>
              );
            })}
          </Box>
        )}

        {hiddenCount > 0 ? (
          <Typography
            sx={{
              mt: 1,
              fontSize: 11,
              color: "var(--app-muted)",
              fontStyle: "italic",
            }}
          >
            +{hiddenCount} older event{hiddenCount === 1 ? "" : "s"} (capped
            for readability — older history lives in the audit log).
          </Typography>
        ) : null}

        <Typography
          sx={{
            mt: 1.5,
            fontSize: 11,
            color: "var(--app-muted)",
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          AUTHZ events change the client&apos;s authorization surface.
          DRIFT events are reflexive-analyzer findings or denied requests
          worth a closer look. ROUTINE events are everyday calls — capped
          to keep the timeline scannable; full history lives in the audit
          log.
        </Typography>
      </CardContent>
    </Card>
  );
}
