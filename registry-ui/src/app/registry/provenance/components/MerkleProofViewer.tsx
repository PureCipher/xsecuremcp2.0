"use client";

import { useState } from "react";
import type { ProvenanceRecord, ProvenanceProofResponse } from "@/lib/registryClient";

function truncHash(hash: string, len = 16): string {
  if (!hash) return "—";
  return hash.length > len ? hash.slice(0, len) + "…" : hash;
}

type Props = {
  record: ProvenanceRecord | null;
  proof: ProvenanceProofResponse | null;
  loading: boolean;
};

export function MerkleProofViewer({ record, proof, loading }: Props) {
  const [showFull, setShowFull] = useState(false);

  if (!record) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/[0.02] p-6 text-center">
        <div className="text-zinc-500 text-sm">
          Select a record from the timeline to view its Merkle proof
        </div>
        <p className="mt-1 text-[11px] text-zinc-600">
          Each record has a cryptographic inclusion proof that verifies it belongs to the ledger
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/[0.02] p-6">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
          Loading proof for {truncHash(record.record_id)}…
        </div>
      </div>
    );
  }

  if (!proof || proof.error) {
    return (
      <div className="rounded-3xl border border-rose-500/20 bg-rose-500/5 p-6">
        <div className="text-sm text-rose-300">
          Failed to load proof: {proof?.error ?? "Unknown error"}
        </div>
      </div>
    );
  }

  const bundle = proof.bundle;
  if (!bundle) return null;

  const mp = bundle.merkle_proof;
  const chain = bundle.chain_context;
  const ledger = bundle.ledger_state;
  const ledgerRecordCountText =
    typeof ledger.record_count === "number" ? ledger.record_count.toLocaleString() : "—";

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.02] p-5 space-y-4">
      {/* ── Header ──────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-zinc-200">
            Merkle Proof
          </h3>
          <p className="text-[11px] text-zinc-500 font-mono">
            Record: {truncHash(record.record_id, 24)}
          </p>
        </div>
        <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300">
          Verifiable
        </span>
      </div>

      {/* ── Record summary ──────────────────────────────── */}
      <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3 space-y-1">
        <div className="text-[10px] font-medium uppercase tracking-[0.15em] text-cyan-300/70 mb-1">
          Record Details
        </div>
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px]">
          <span className="text-zinc-500">Action</span>
          <span className="text-zinc-300">{record.action}</span>
          <span className="text-zinc-500">Resource</span>
          <span className="text-zinc-300 truncate">{record.resource_id || "—"}</span>
          <span className="text-zinc-500">Actor</span>
          <span className="text-zinc-300">{record.actor_id || "—"}</span>
          <span className="text-zinc-500">Timestamp</span>
          <span className="text-zinc-300 font-mono">{record.timestamp}</span>
        </div>
      </div>

      {/* ── Chain context (visual) ──────────────────────── */}
      <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
        <div className="text-[10px] font-medium uppercase tracking-[0.15em] text-cyan-300/70 mb-2">
          Chain Position
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono">
          {/* predecessor */}
          <div className="rounded-lg border border-white/5 bg-zinc-800/50 px-2 py-1 text-zinc-500">
            ← {truncHash(chain.predecessor_hash, 12)}
          </div>
          {/* connector */}
          <div className="h-px w-4 bg-cyan-500/30" />
          {/* current record */}
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-cyan-300">
            {truncHash(mp.leaf_hash, 12)}
          </div>
          {/* connector */}
          <div className="h-px w-4 bg-cyan-500/30" />
          {/* successor */}
          <div className="rounded-lg border border-white/5 bg-zinc-800/50 px-2 py-1 text-zinc-500">
            {chain.successor_hash ? truncHash(chain.successor_hash, 12) : "HEAD"} →
          </div>
        </div>
      </div>

      {/* ── Merkle proof path ───────────────────────────── */}
      <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] font-medium uppercase tracking-[0.15em] text-cyan-300/70">
            Proof Path ({mp.proof_hashes.length} levels)
          </div>
          <button
            onClick={() => setShowFull((v) => !v)}
            className="text-[10px] text-cyan-400 hover:text-cyan-300"
          >
            {showFull ? "Collapse" : "Expand"}
          </button>
        </div>

        {/* Visual tree path */}
        <div className="space-y-1">
          {/* Leaf */}
          <div className="flex items-center gap-2">
            <span className="w-12 text-right text-[10px] text-zinc-600">leaf</span>
            <span className="h-px w-3 bg-emerald-500/30" />
            <code className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-mono text-emerald-300">
              {showFull ? mp.leaf_hash : truncHash(mp.leaf_hash, 20)}
            </code>
          </div>

          {/* Sibling levels */}
          {mp.proof_hashes.map((h, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-12 text-right text-[10px] text-zinc-600">
                L{i + 1} {mp.directions[i]}
              </span>
              <span className="h-px w-3 bg-white/10" />
              <code className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
                {showFull ? h : truncHash(h, 20)}
              </code>
            </div>
          ))}

          {/* Root */}
          <div className="flex items-center gap-2">
            <span className="w-12 text-right text-[10px] text-zinc-600">root</span>
            <span className="h-px w-3 bg-cyan-500/30" />
            <code className="rounded bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-mono text-cyan-300">
              {showFull ? mp.root_hash : truncHash(mp.root_hash, 20)}
            </code>
          </div>
        </div>
      </div>

      {/* ── Ledger state ────────────────────────────────── */}
      <div className="flex items-center gap-4 text-[11px] text-zinc-500">
        <span>
          Ledger root: <code className="text-cyan-300/60 font-mono">{truncHash(ledger.root_hash, 16)}</code>
        </span>
        <span>
          Total records: <span className="text-zinc-300">{ledgerRecordCountText}</span>
        </span>
        <span>
          Exported: <span className="text-zinc-400">{new Date(bundle.exported_at).toLocaleString()}</span>
        </span>
      </div>
    </div>
  );
}
