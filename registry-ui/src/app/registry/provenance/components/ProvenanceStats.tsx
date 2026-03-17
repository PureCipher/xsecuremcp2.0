"use client";

import { useMemo } from "react";
import type { ProvenanceRecord, ProvenanceChainStatus } from "@/lib/registryClient";

type Props = {
  records: ProvenanceRecord[];
  chainStatus: ProvenanceChainStatus | null;
};

export function ProvenanceStats({ records, chainStatus }: Props) {
  const stats = useMemo(() => {
    const actionCounts: Record<string, number> = {};
    const actorCounts: Record<string, number> = {};
    let errorCount = 0;

    for (const r of records) {
      actionCounts[r.action] = (actionCounts[r.action] ?? 0) + 1;
      if (r.actor_id) {
        actorCounts[r.actor_id] = (actorCounts[r.actor_id] ?? 0) + 1;
      }
      if (r.action === "error" || r.action === "access_denied") {
        errorCount++;
      }
    }

    const topActions = Object.entries(actionCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);

    const uniqueActors = Object.keys(actorCounts).length;

    return { actionCounts, topActions, uniqueActors, errorCount };
  }, [records]);

  const totalRecords = chainStatus?.record_count ?? records.length;

  return (
    <div className="grid grid-cols-4 gap-3">
      {/* Total Records */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        <div className="text-2xl font-semibold text-zinc-100 font-mono">
          {totalRecords.toLocaleString()}
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">Total Records</div>
      </div>

      {/* Chain Status */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-3 w-3 rounded-full ${
              chainStatus?.chain_valid ? "bg-emerald-400" : "bg-rose-400"
            }`}
          />
          <span className="text-lg font-semibold text-zinc-100">
            {chainStatus?.chain_valid ? "Valid" : "Broken"}
          </span>
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">Chain Integrity</div>
      </div>

      {/* Unique Actors */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        <div className="text-2xl font-semibold text-zinc-100 font-mono">
          {stats.uniqueActors}
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">Unique Actors</div>
      </div>

      {/* Errors */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        <div className={`text-2xl font-semibold font-mono ${stats.errorCount > 0 ? "text-rose-300" : "text-zinc-100"}`}>
          {stats.errorCount}
        </div>
        <div className="text-[11px] text-zinc-500 mt-0.5">Errors / Denials</div>
      </div>

      {/* Top Actions (spans full width) */}
      <div className="col-span-4 rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        <div className="text-[10px] font-medium uppercase tracking-[0.15em] text-cyan-300/70 mb-2">
          Action Distribution
        </div>
        <div className="flex flex-wrap gap-2">
          {stats.topActions.map(([action, count]) => {
            const pct = totalRecords > 0 ? Math.round((count / totalRecords) * 100) : 0;
            return (
              <div key={action} className="flex items-center gap-1.5">
                <div className="h-1.5 rounded-full bg-cyan-500/60" style={{ width: `${Math.max(pct, 4)}px` }} />
                <span className="text-[11px] text-zinc-300">{action}</span>
                <span className="text-[10px] text-zinc-500 font-mono">{count}</span>
                <span className="text-[10px] text-zinc-600">({pct}%)</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
