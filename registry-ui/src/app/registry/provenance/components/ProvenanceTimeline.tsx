"use client";

import { useState, useMemo } from "react";
import type { ProvenanceRecord } from "@/lib/registryClient";
import { Box, ButtonBase, Chip, MenuItem, Select, TextField, Typography } from "@mui/material";

/* ── action → color map ─────────────────────────────────────── */
const ACTION_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  tool_called:       { dot: "bg-[--app-accent]", bg: "bg-[--app-control-active-bg]", text: "text-[--app-muted]" },
  tool_result:       { dot: "bg-[--app-accent]", bg: "bg-[--app-control-active-bg]", text: "text-[--app-muted]" },
  resource_read:     { dot: "bg-sky-400",     bg: "bg-sky-500/10",     text: "text-sky-300" },
  resource_listed:   { dot: "bg-sky-400",     bg: "bg-sky-500/10",     text: "text-sky-300" },
  prompt_rendered:   { dot: "bg-violet-400",  bg: "bg-violet-500/10",  text: "text-violet-300" },
  prompt_listed:     { dot: "bg-violet-400",  bg: "bg-violet-500/10",  text: "text-violet-300" },
  policy_evaluated:  { dot: "bg-amber-400",   bg: "bg-amber-500/10",   text: "text-amber-300" },
  contract_created:  { dot: "bg-teal-400",    bg: "bg-teal-500/10",    text: "text-teal-300" },
  contract_revoked:  { dot: "bg-rose-400",    bg: "bg-rose-500/10",    text: "text-rose-300" },
  access_denied:     { dot: "bg-rose-400",    bg: "bg-rose-500/10",    text: "text-rose-300" },
  error:             { dot: "bg-red-400",     bg: "bg-red-500/10",     text: "text-red-300" },
  model_invoked:     { dot: "bg-cyan-400",    bg: "bg-cyan-500/10",    text: "text-cyan-300" },
  dataset_accessed:  { dot: "bg-indigo-400",  bg: "bg-indigo-500/10",  text: "text-indigo-300" },
  outcome_recorded:  { dot: "bg-lime-400",    bg: "bg-lime-500/10",    text: "text-lime-300" },
  chain_anchored:    { dot: "bg-yellow-400",  bg: "bg-yellow-500/10",  text: "text-yellow-300" },
  ledger_verified:   { dot: "bg-green-400",   bg: "bg-green-500/10",   text: "text-green-300" },
  custom:            { dot: "bg-zinc-400",    bg: "bg-zinc-500/10",    text: "text-zinc-300" },
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
              bgcolor: "rgba(255,255,255,0.05)",
              color: "rgb(228, 228, 231)",
              "& fieldset": { borderColor: "rgba(255,255,255,0.10)" },
              "&:hover fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
              "&.Mui-focused fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
            },
            "& input::placeholder": { color: "rgb(113, 113, 122)", opacity: 1 },
          }}
        />
        <Select
          value={filterAction}
          onChange={(e) => setFilterAction(String(e.target.value))}
          size="small"
          displayEmpty
          sx={{
            borderRadius: 3,
            bgcolor: "rgba(255,255,255,0.05)",
            color: "rgb(212, 212, 216)",
            "& fieldset": { borderColor: "rgba(255,255,255,0.10)" },
            "&:hover fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
            "&.Mui-focused fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
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
            bgcolor: "rgba(255,255,255,0.05)",
            color: "rgb(212, 212, 216)",
            "& fieldset": { borderColor: "rgba(255,255,255,0.10)" },
            "&:hover fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
            "&.Mui-focused fieldset": { borderColor: "rgba(6, 182, 212, 0.50)" },
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
        <Typography variant="caption" sx={{ ml: "auto", color: "rgb(113, 113, 122)" }}>
          {filtered.length} of {records.length} records
        </Typography>
      </Box>

      {/* ── Timeline ────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 4, textAlign: "center" }}>
          <Typography variant="body2" sx={{ color: "rgb(113, 113, 122)" }}>
            No provenance records{records.length > 0 ? " match your filters" : " recorded yet"}
          </Typography>
        </Box>
      ) : (
        <Box sx={{ position: "relative" }}>
          {Array.from(grouped.entries()).map(([date, recs]) => (
            <Box key={date} sx={{ mb: 3 }}>
              <Typography variant="overline" sx={{ mb: 1, color: "rgba(103, 232, 249, 0.80)" }}>
                {date}
              </Typography>
              <Box sx={{ position: "relative", ml: 1.5, borderLeft: "1px solid rgba(255,255,255,0.10)", pl: 3, display: "flex", flexDirection: "column", gap: 1 }}>
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
                        bgcolor: isSelected ? "rgba(6, 182, 212, 0.15)" : "transparent",
                        border: isSelected ? "1px solid rgba(6, 182, 212, 0.30)" : "1px solid transparent",
                        "&:hover": { bgcolor: isSelected ? "rgba(6, 182, 212, 0.15)" : "rgba(255,255,255,0.04)" },
                      }}
                    >
                      {/* Dot on the line */}
                      <span
                        className={`absolute -left-[31px] top-3 h-2.5 w-2.5 rounded-full ring-2 ring-zinc-900 ${c.dot}`}
                      />

                      {/* Time */}
                      <Typography
                        variant="caption"
                        sx={{
                          mt: 0.25,
                          minWidth: 74,
                          color: "rgb(113, 113, 122)",
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
                        className={`${c.bg} ${c.text}`}
                        sx={{ mt: 0.25, height: 22, borderRadius: 999, fontSize: 10, fontWeight: 700 }}
                      />

                      {/* Details */}
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, minWidth: 0 }}>
                          <Typography variant="body2" sx={{ minWidth: 0, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "rgb(228, 228, 231)" }}>
                            {rec.resource_id || "—"}
                          </Typography>
                          {rec.actor_id ? (
                            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                              by {rec.actor_id}
                            </Typography>
                          ) : null}
                        </Box>
                        <Box sx={{ display: "flex", gap: 1.5, mt: 0.5, flexWrap: "wrap" }}>
                          <Typography variant="caption" sx={{ color: "rgb(82, 82, 91)" }} title="Input hash">
                            in:{truncHash(rec.input_hash, 8)}
                          </Typography>
                          <Typography variant="caption" sx={{ color: "rgb(82, 82, 91)" }} title="Output hash">
                            out:{truncHash(rec.output_hash, 8)}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "rgb(82, 82, 91)",
                              fontFamily:
                                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                            }}
                            title="Chain link"
                          >
                            ←{truncHash(rec.previous_hash, 8)}
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
