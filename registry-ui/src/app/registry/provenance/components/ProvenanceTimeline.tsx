"use client";

import { useState, useMemo } from "react";
import type { ProvenanceRecord } from "@/lib/registryClient";
import { Box, ButtonBase, Chip, MenuItem, Select, TextField, Typography } from "@mui/material";

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

export function ProvenanceTimeline({ records, onSelectRecord, selectedRecordId }: Props) {
  const [filterAction, setFilterAction] = useState<string>("");
  const [filterActor, setFilterActor] = useState<string>("");
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

  /* filtered records */
  const filtered = useMemo(() => {
    return records.filter((r) => {
      if (filterAction && r.action !== filterAction) return false;
      if (filterActor && r.actor_id !== filterActor) return false;
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
  }, [records, filterAction, filterActor, searchQuery]);

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
