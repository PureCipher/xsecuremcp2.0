"use client";

import { useState, useMemo } from "react";
import type { ProvenanceRecord } from "@/lib/registryClient";

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
    <div className="flex flex-col gap-4">
      {/* ── Filter bar ─────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search records…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-cyan-500/50"
        />
        <select
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/5 px-2 py-1.5 text-xs text-zinc-300 outline-none focus:border-cyan-500/50"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select
          value={filterActor}
          onChange={(e) => setFilterActor(e.target.value)}
          className="rounded-xl border border-white/10 bg-white/5 px-2 py-1.5 text-xs text-zinc-300 outline-none focus:border-cyan-500/50"
        >
          <option value="">All actors</option>
          {actors.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <span className="ml-auto text-[11px] text-zinc-500">
          {filtered.length} of {records.length} records
        </span>
      </div>

      {/* ── Timeline ────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-8 text-center text-sm text-zinc-500">
          No provenance records{records.length > 0 ? " match your filters" : " recorded yet"}
        </div>
      ) : (
        <div className="relative space-y-6">
          {Array.from(grouped.entries()).map(([date, recs]) => (
            <div key={date}>
              <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.18em] text-cyan-300/80">
                {date}
              </div>
              <div className="relative ml-3 border-l border-white/10 pl-6 space-y-1">
                {recs.map((rec) => {
                  const c = actionColor(rec.action);
                  const isSelected = rec.record_id === selectedRecordId;
                  return (
                    <button
                      key={rec.record_id}
                      onClick={() => onSelectRecord?.(rec)}
                      className={`group relative flex w-full items-start gap-3 rounded-xl px-3 py-2 text-left transition
                        ${isSelected ? "bg-cyan-500/15 ring-1 ring-cyan-500/30" : "hover:bg-white/[0.04]"}`}
                    >
                      {/* Dot on the line */}
                      <span
                        className={`absolute -left-[31px] top-3 h-2.5 w-2.5 rounded-full ring-2 ring-zinc-900 ${c.dot}`}
                      />

                      {/* Time */}
                      <span className="mt-0.5 min-w-[60px] text-[11px] font-mono text-zinc-500">
                        {formatTime(rec.timestamp)}
                      </span>

                      {/* Action badge */}
                      <span
                        className={`mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-medium ${c.bg} ${c.text}`}
                      >
                        {rec.action}
                      </span>

                      {/* Details */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-xs text-zinc-200">
                            {rec.resource_id || "—"}
                          </span>
                          {rec.actor_id && (
                            <span className="text-[10px] text-zinc-500">
                              by {rec.actor_id}
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 flex gap-3 text-[10px] text-zinc-600">
                          <span title="Input hash">
                            in:{truncHash(rec.input_hash, 8)}
                          </span>
                          <span title="Output hash">
                            out:{truncHash(rec.output_hash, 8)}
                          </span>
                          <span title="Chain link" className="font-mono">
                            ←{truncHash(rec.previous_hash, 8)}
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
