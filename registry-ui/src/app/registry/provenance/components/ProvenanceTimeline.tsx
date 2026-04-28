"use client";

import { useCallback, useMemo, useState } from "react";
import type { ProvenanceRecord } from "@/lib/registryClient";
import { Box, Button, ButtonBase, Chip, MenuItem, Select, TextField, Typography } from "@mui/material";

const ACTION_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  tool_called: { dot: "var(--app-accent)", bg: "var(--app-control-active-bg)", text: "var(--app-fg)" },
  tool_result: { dot: "var(--app-accent)", bg: "var(--app-control-active-bg)", text: "var(--app-fg)" },
  resource_read: { dot: "#0284c7", bg: "rgba(14, 165, 233, 0.1)", text: "#0369a1" },
  resource_listed: { dot: "#0284c7", bg: "rgba(14, 165, 233, 0.1)", text: "#0369a1" },
  prompt_rendered: { dot: "#7c3aed", bg: "rgba(124, 58, 237, 0.1)", text: "#6d28d9" },
  prompt_listed: { dot: "#7c3aed", bg: "rgba(124, 58, 237, 0.1)", text: "#6d28d9" },
  policy_evaluated: { dot: "#d97706", bg: "rgba(245, 158, 11, 0.12)", text: "#92400e" },
  contract_created: { dot: "#0d9488", bg: "rgba(13, 148, 136, 0.1)", text: "#0f766e" },
  contract_revoked: { dot: "#e11d48", bg: "rgba(225, 29, 72, 0.1)", text: "#be123c" },
  access_denied: { dot: "#e11d48", bg: "rgba(225, 29, 72, 0.1)", text: "#be123c" },
  error: { dot: "#ef4444", bg: "rgba(239, 68, 68, 0.1)", text: "#b91c1c" },
  model_invoked: { dot: "#0891b2", bg: "rgba(8, 145, 178, 0.1)", text: "#0e7490" },
  dataset_accessed: { dot: "#4f46e5", bg: "rgba(79, 70, 229, 0.1)", text: "#4338ca" },
  outcome_recorded: { dot: "#65a30d", bg: "rgba(101, 163, 13, 0.1)", text: "#4d7c0f" },
  chain_anchored: { dot: "#ca8a04", bg: "rgba(202, 138, 4, 0.1)", text: "#a16207" },
  ledger_verified: { dot: "#16a34a", bg: "rgba(22, 163, 74, 0.1)", text: "#15803d" },
  custom: { dot: "var(--app-muted)", bg: "rgba(100, 116, 139, 0.1)", text: "var(--app-muted)" },
};

function actionColor(action: string) {
  return ACTION_COLORS[action] ?? ACTION_COLORS.custom;
}

/**
 * Iter 14.25 — Compact stat tile for the audit summary header.
 * Three of these render in a row: events / allow / deny. The
 * ``tone`` prop colors the value: ``"ok"`` (allow) sits muted,
 * ``"warn"`` (deny when nonzero) reads red, ``"muted"`` (zero
 * count) fades.
 */
function SummaryStat({
  label,
  value,
  tone = "ok",
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "muted";
}) {
  const valueColor =
    tone === "warn"
      ? "#b91c1c"
      : tone === "muted"
        ? "var(--app-muted)"
        : "var(--app-fg)";
  return (
    <Box
      sx={{
        display: "inline-flex",
        flexDirection: "column",
        gap: 0,
        px: 1.5,
        py: 0.5,
        borderRight: "1px solid var(--app-border)",
        "&:last-of-type": { borderRight: "none" },
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
          fontSize: 18,
          fontWeight: 800,
          lineHeight: 1.1,
          color: valueColor,
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return iso;
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

function truncHash(hash: string, len = 12): string {
  if (!hash) return "—";
  return hash.length > len ? hash.slice(0, len) + "…" : hash;
}

/* ── Main component ─────────────────────────────────────────── */

type Props = {
  records: ProvenanceRecord[];
  onSelectRecord?: (record: ProvenanceRecord) => void;
  selectedRecordId?: string;
};

// Iter 14.25 — actions whose semantics indicate a *deny* outcome.
// Used by the audit summary header to split records into
// allow-shaped vs deny-shaped buckets so an admin can answer
// "how many deny events are in this window?" at a glance.
const DENY_ACTION_NAMES: ReadonlySet<string> = new Set([
  "access_denied",
  "contract_revoked",
  "error",
]);

export function ProvenanceTimeline({ records, onSelectRecord, selectedRecordId }: Props) {
  const [filterAction, setFilterAction] = useState<string>("");
  const [filterActor, setFilterActor] = useState<string>("");
  // Iter 14.25 — explicit resource (tool) dropdown alongside the
  // free-text search. Reviewers/admins doing forensics frequently
  // narrow to "everything that touched this tool" before drilling in.
  const [filterResource, setFilterResource] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  /* unique actions and actors for filter dropdowns */
  const actions = useMemo(() => {
    const s = new Set(records.map((r) => r.action));
    return Array.from(s).sort();
  }, [records]);

  const actors = useMemo(() => {
    const s = new Set(records.map((r) => r.actor_id).filter(Boolean));
    return Array.from(s).sort();
  }, [records]);

  // Iter 14.25 — resource list, deduped + sorted. Empty resources
  // (e.g. metadata-only events) are filtered out so the dropdown
  // doesn't carry a meaningless "" entry.
  const resources = useMemo(() => {
    const s = new Set(records.map((r) => r.resource_id).filter(Boolean));
    return Array.from(s).sort();
  }, [records]);

  /* filtered records */
  const filtered = useMemo(() => {
    return records.filter((r) => {
      if (filterAction && r.action !== filterAction) return false;
      if (filterActor && r.actor_id !== filterActor) return false;
      if (filterResource && r.resource_id !== filterResource) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          r.resource_id.toLowerCase().includes(q) ||
          r.actor_id.toLowerCase().includes(q) ||
          r.record_id.toLowerCase().includes(q) ||
          r.action.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [records, filterAction, filterActor, filterResource, searchQuery]);

  // Iter 14.25 — deny / allow split across the *filtered* set.
  // Surfaces in the summary header so an admin running a filter to
  // "everything client X did" sees the deny count for that scope
  // without scrolling the timeline.
  const summary = useMemo(() => {
    let denyCount = 0;
    for (const r of filtered) {
      if (DENY_ACTION_NAMES.has(r.action)) denyCount += 1;
    }
    return {
      total: filtered.length,
      deny: denyCount,
      allow: filtered.length - denyCount,
    };
  }, [filtered]);

  // Iter 14.25 — CSV export. Audit reviews and compliance handoffs
  // routinely need a flat file for evidence; without this, an admin
  // copies cells out of the page DOM. The export honors the active
  // filters so the file matches what's on screen — that's the
  // semantics auditors expect.
  const handleExportCsv = useCallback(() => {
    if (filtered.length === 0) return;
    const headers = [
      "timestamp",
      "action",
      "actor_id",
      "resource_id",
      "record_id",
      "input_hash",
      "output_hash",
      "previous_hash",
    ];
    const escape = (value: unknown) => {
      const str = value == null ? "" : String(value);
      if (
        str.includes(",") ||
        str.includes("\n") ||
        str.includes('"')
      ) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };
    const lines = [headers.join(",")];
    for (const r of filtered) {
      lines.push(
        [
          r.timestamp,
          r.action,
          r.actor_id,
          r.resource_id,
          r.record_id,
          r.input_hash,
          r.output_hash,
          r.previous_hash,
        ]
          .map(escape)
          .join(","),
      );
    }
    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    a.href = url;
    a.download = `audit-log-${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [filtered]);

  const isFiltering =
    Boolean(filterAction) ||
    Boolean(filterActor) ||
    Boolean(filterResource) ||
    Boolean(searchQuery);
  const handleClearFilters = useCallback(() => {
    setFilterAction("");
    setFilterActor("");
    setFilterResource("");
    setSearchQuery("");
  }, []);

  /* group by date */
  const grouped = useMemo(() => {
    const map = new Map<string, ProvenanceRecord[]>();
    for (const r of filtered) {
      const key = formatDate(r.timestamp);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return map;
  }, [filtered]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Iter 14.25 — Audit summary header. Three quick stats give
          an admin the shape of the (filtered) window before they
          scroll the timeline: total events, deny count, allow count.
          The deny number is colored red when nonzero so a window
          containing rejections jumps out visually. */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 1.5,
          p: 1.5,
          borderRadius: 3,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
        }}
      >
        <SummaryStat label="Events" value={String(summary.total)} />
        <SummaryStat
          label="Allow"
          value={String(summary.allow)}
          tone={summary.allow > 0 ? "ok" : "muted"}
        />
        <SummaryStat
          label="Deny"
          value={String(summary.deny)}
          tone={summary.deny > 0 ? "warn" : "muted"}
        />
        {isFiltering ? (
          <Typography
            variant="caption"
            sx={{ color: "var(--app-muted)", fontStyle: "italic" }}
          >
            (filtered from {records.length})
          </Typography>
        ) : null}
        <Box sx={{ ml: "auto", display: "flex", gap: 0.5, flexWrap: "wrap" }}>
          {isFiltering ? (
            <Button
              size="small"
              variant="text"
              onClick={handleClearFilters}
              sx={{
                textTransform: "none",
                color: "var(--app-muted)",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              Clear filters
            </Button>
          ) : null}
          <Button
            size="small"
            variant="outlined"
            onClick={handleExportCsv}
            disabled={filtered.length === 0}
            sx={{
              textTransform: "none",
              borderColor: "var(--app-border)",
              color: "var(--app-fg)",
              fontSize: 12,
            }}
          >
            Export CSV ({filtered.length})
          </Button>
        </Box>
      </Box>

      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <TextField
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search records…"
          size="small"
          sx={{
            minWidth: 220,
            "& .MuiOutlinedInput-root": {
              borderRadius: 3,
              bgcolor: "var(--app-control-bg)",
              color: "var(--app-fg)",
              "& fieldset": { borderColor: "var(--app-control-border)" },
              "&:hover fieldset": { borderColor: "var(--app-accent)" },
              "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
            },
            "& input::placeholder": { color: "var(--app-muted)", opacity: 1 },
          }}
        />
        <Select
          value={filterAction}
          onChange={(e) => setFilterAction(String(e.target.value))}
          size="small"
          displayEmpty
          sx={{
            borderRadius: 3,
            bgcolor: "var(--app-control-bg)",
            color: "var(--app-fg)",
            "& fieldset": { borderColor: "var(--app-control-border)" },
            "&:hover fieldset": { borderColor: "var(--app-accent)" },
            "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
            minWidth: 160,
          }}
        >
          <MenuItem value="">All actions</MenuItem>
          {actions.map((a) => (
            <MenuItem key={a} value={a}>
              {a}
            </MenuItem>
          ))}
        </Select>
        <Select
          value={filterActor}
          onChange={(e) => setFilterActor(String(e.target.value))}
          size="small"
          displayEmpty
          sx={{
            borderRadius: 3,
            bgcolor: "var(--app-control-bg)",
            color: "var(--app-fg)",
            "& fieldset": { borderColor: "var(--app-control-border)" },
            "&:hover fieldset": { borderColor: "var(--app-accent)" },
            "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
            minWidth: 160,
          }}
        >
          <MenuItem value="">All actors</MenuItem>
          {actors.map((a) => (
            <MenuItem key={a} value={a}>
              {a}
            </MenuItem>
          ))}
        </Select>
        {/* Iter 14.25 — resource (tool) filter. Hidden when the
            ledger has fewer than two distinct resources to filter
            against — a single-resource dropdown is just chrome. */}
        {resources.length > 1 ? (
          <Select
            value={filterResource}
            onChange={(e) => setFilterResource(String(e.target.value))}
            size="small"
            displayEmpty
            sx={{
              borderRadius: 3,
              bgcolor: "var(--app-control-bg)",
              color: "var(--app-fg)",
              "& fieldset": { borderColor: "var(--app-control-border)" },
              "&:hover fieldset": { borderColor: "var(--app-accent)" },
              "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
              minWidth: 200,
              maxWidth: 320,
            }}
          >
            <MenuItem value="">All resources</MenuItem>
            {resources.map((r) => (
              <MenuItem key={r} value={r}>
                {r}
              </MenuItem>
            ))}
          </Select>
        ) : null}
        <Typography variant="caption" sx={{ ml: "auto", color: "var(--app-muted)" }}>
          {filtered.length} of {records.length} records
        </Typography>
      </Box>

      {/* ── Timeline ────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 4, textAlign: "center" }}>
          <Typography sx={{ fontSize: 15, fontWeight: 700, color: "var(--app-fg)" }}>
            {records.length > 0 ? "No matching provenance records" : "No provenance records yet"}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.75, color: "var(--app-muted)" }}>
            {records.length > 0
              ? "Try clearing filters or searching by a shorter id, actor, resource, or action."
              : "Ledger events will appear here after approved tools, policies, contracts, or clients write auditable activity."}
          </Typography>
        </Box>
      ) : (
        <Box sx={{ position: "relative" }}>
          {Array.from(grouped.entries()).map(([date, recs]) => (
            <Box key={date} sx={{ mb: 3 }}>
              <Typography variant="overline" sx={{ mb: 1, color: "var(--app-muted)" }}>
                {date}
              </Typography>
              <Box sx={{ position: "relative", ml: 1.5, borderLeft: "1px solid var(--app-border)", pl: 3, display: "flex", flexDirection: "column", gap: 1 }}>
                {recs.map((rec) => {
                  const c = actionColor(rec.action);
                  const isSelected = rec.record_id === selectedRecordId;
                  return (
                    <ButtonBase
                      key={rec.record_id}
                      onClick={() => onSelectRecord?.(rec)}
                      sx={{
                        position: "relative",
                        width: "100%",
                        alignItems: "flex-start",
                        justifyContent: "flex-start",
                        gap: 1.5,
                        borderRadius: 3,
                        px: 2,
                        py: 1.5,
                        textAlign: "left",
                        bgcolor: isSelected ? "var(--app-control-active-bg)" : "transparent",
                        border: isSelected ? "1px solid var(--app-accent)" : "1px solid transparent",
                        "&:hover": { bgcolor: isSelected ? "var(--app-control-active-bg)" : "var(--app-hover-bg)" },
                      }}
                    >
                      {/* Dot on the line */}
                      <Box
                        aria-hidden
                        sx={{
                          position: "absolute",
                          left: -31,
                          top: 12,
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          bgcolor: c.dot,
                          border: "2px solid var(--app-bg)",
                        }}
                      />

                      {/* Time */}
                      <Typography
                        variant="caption"
                        sx={{
                          mt: 0.25,
                          minWidth: 74,
                          color: "var(--app-muted)",
                          fontFamily:
                            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        }}
                      >
                        {formatTime(rec.timestamp)}
                      </Typography>

                      {/* Action badge */}
                      <Chip
                        size="small"
                        label={rec.action}
                        sx={{ mt: 0.25, height: 24, bgcolor: c.bg, color: c.text, fontSize: 11, fontWeight: 700 }}
                      />

                      {/* Details */}
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, minWidth: 0 }}>
                          <Typography variant="body2" sx={{ minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--app-fg)" }}>
                            {rec.resource_id || "—"}
                          </Typography>
                          {rec.actor_id ? (
                            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                              by {rec.actor_id}
                            </Typography>
                          ) : null}
                        </Box>
                        <Box sx={{ display: "flex", gap: 1.5, mt: 0.5, flexWrap: "wrap" }}>
                          <Typography variant="caption" sx={{ color: "var(--app-muted)" }} title="Input hash">
                            in:{truncHash(rec.input_hash, 8)}
                          </Typography>
                          <Typography variant="caption" sx={{ color: "var(--app-muted)" }} title="Output hash">
                            out:{truncHash(rec.output_hash, 8)}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "var(--app-muted)",
                              fontFamily:
                                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                            }}
                            title="Chain link"
                          >
                            prev:{truncHash(rec.previous_hash, 8)}
                          </Typography>
                        </Box>
                      </Box>
                    </ButtonBase>
                  );
                })}
              </Box>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
