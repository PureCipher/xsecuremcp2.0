"use client";

import type { ProvenanceChainStatus } from "@/lib/registryClient";

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className="relative flex h-3 w-3">
      {ok && (
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-40" />
      )}
      <span
        className={`relative inline-flex h-3 w-3 rounded-full ${
          ok ? "bg-emerald-400" : "bg-rose-400"
        }`}
      />
    </span>
  );
}

function HashDisplay({ label, hash }: { label: string; hash: string }) {
  if (!hash) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-zinc-500">{label}:</span>
      <code className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-mono text-cyan-300/80 select-all">
        {hash}
      </code>
    </div>
  );
}

type Props = {
  status: ProvenanceChainStatus;
};

export function ChainIntegrityPanel({ status }: Props) {
  const allValid = status.chain_valid && status.tree_valid;
  const scheme = status.scheme;
  const isAnchored = scheme?.scheme === "blockchain_anchored";
  const recordCountText =
    typeof status.record_count === "number" ? status.record_count.toLocaleString() : "—";

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.02] p-5 space-y-4">
      {/* ── Header ──────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusDot ok={allValid} />
          <div>
            <h3 className="text-sm font-medium text-zinc-200">
              Chain Integrity
            </h3>
            <p className="text-[11px] text-zinc-500">
              Ledger: {status.ledger_id} · {recordCountText} records
            </p>
          </div>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
            allValid
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-rose-500/15 text-rose-300"
          }`}
        >
          {allValid ? "Intact" : "Tamper Detected"}
        </span>
      </div>

      {/* ── Integrity checks ────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`h-2 w-2 rounded-full ${
                status.chain_valid ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span className="text-xs font-medium text-zinc-300">Hash Chain</span>
          </div>
          <p className="text-[11px] text-zinc-500">
            {status.chain_valid
              ? "Every record correctly links to its predecessor via SHA-256"
              : "One or more chain links are broken — possible tampering"}
          </p>
        </div>

        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`h-2 w-2 rounded-full ${
                status.tree_valid ? "bg-emerald-400" : "bg-rose-400"
              }`}
            />
            <span className="text-xs font-medium text-zinc-300">Merkle Tree</span>
          </div>
          <p className="text-[11px] text-zinc-500">
            {status.tree_valid
              ? "All leaf hashes form a consistent Merkle tree"
              : "Merkle tree rebuild does not match expected root"}
          </p>
        </div>
      </div>

      {/* ── Hashes ──────────────────────────────────────── */}
      <div className="space-y-1.5">
        <HashDisplay label="Merkle root" hash={status.root_hash} />
        <HashDisplay label="Chain digest" hash={status.chain_digest} />
      </div>

      {/* ── Ledger scheme info ──────────────────────────── */}
      <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-cyan-300/70">
            Ledger Scheme
          </span>
          <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
            {scheme?.scheme ?? "unknown"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
          <div className="text-zinc-500">Leaf count</div>
          <div className="text-zinc-300 font-mono">{scheme?.leaf_count?.toLocaleString() ?? "—"}</div>

          <div className="text-zinc-500">Tree valid</div>
          <div className={scheme?.tree_valid ? "text-emerald-300" : "text-rose-300"}>
            {scheme?.tree_valid ? "Yes" : "No"}
          </div>

          {isAnchored && (
            <>
              <div className="text-zinc-500">Anchors committed</div>
              <div className="text-zinc-300 font-mono">{scheme.anchor_count ?? 0}</div>

              <div className="text-zinc-500">Anchors valid</div>
              <div className={scheme.anchors_valid ? "text-emerald-300" : "text-rose-300"}>
                {scheme.anchors_valid ? "Yes" : "No"}
              </div>

              <div className="text-zinc-500">Records since anchor</div>
              <div className="text-zinc-300 font-mono">{scheme.records_since_anchor ?? 0}</div>

              <div className="text-zinc-500">Anchor interval</div>
              <div className="text-zinc-300 font-mono">every {scheme.anchor_interval ?? "?"} records</div>

              {scheme.latest_anchor && (
                <>
                  <div className="text-zinc-500">Latest anchor tx</div>
                  <div className="text-cyan-300 font-mono text-[10px] truncate">
                    {String(scheme.latest_anchor.tx_id ?? "—")}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
