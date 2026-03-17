"use client";

import { useState, useCallback } from "react";
import type {
  ProvenanceRecord,
  ProvenanceChainStatus,
  ProvenanceProofResponse,
} from "@/lib/registryClient";
import { ProvenanceTimeline } from "./components/ProvenanceTimeline";
import { ChainIntegrityPanel } from "./components/ChainIntegrityPanel";
import { MerkleProofViewer } from "./components/MerkleProofViewer";
import { ProvenanceStats } from "./components/ProvenanceStats";

type Tab = "timeline" | "integrity" | "proof";

type Props = {
  records: ProvenanceRecord[];
  chainStatus: ProvenanceChainStatus | null;
};

export function ProvenanceDashboard({ records, chainStatus }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("timeline");
  const [selectedRecord, setSelectedRecord] = useState<ProvenanceRecord | null>(null);
  const [proof, setProof] = useState<ProvenanceProofResponse | null>(null);
  const [proofLoading, setProofLoading] = useState(false);

  const handleSelectRecord = useCallback(
    async (record: ProvenanceRecord) => {
      setSelectedRecord(record);
      setActiveTab("proof");
      setProofLoading(true);
      setProof(null);

      try {
        const resp = await fetch(
          `/api/provenance/proof/${encodeURIComponent(record.record_id)}`,
        );
        if (resp.ok) {
          const data = await resp.json();
          setProof(data);
        } else {
          setProof({ error: `HTTP ${resp.status}`, status: String(resp.status) } as unknown as ProvenanceProofResponse);
        }
      } catch (err) {
        setProof({ error: String(err) } as unknown as ProvenanceProofResponse);
      } finally {
        setProofLoading(false);
      }
    },
    [],
  );

  const tabs: { key: Tab; label: string }[] = [
    { key: "timeline", label: "Timeline" },
    { key: "integrity", label: "Chain Integrity" },
    { key: "proof", label: "Merkle Proof" },
  ];

  return (
    <div className="space-y-6">
      {/* ── Architecture label ────────────────────────── */}
      <div>
        <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-cyan-300/70 mb-1">
          PROVENANCE LEDGER
        </div>
        <h1 className="text-xl font-semibold text-zinc-100">
          Smart Provenance & Immutable Ledgers
        </h1>
        <p className="text-sm text-zinc-400 mt-1">
          Every model call, dataset usage, and outcome is hashed and chain-linked to prior events.
          Tamper-evident audit trail with Merkle tree verification.
        </p>
      </div>

      {/* ── Stats bar ────────────────────────────────── */}
      <ProvenanceStats records={records} chainStatus={chainStatus} />

      {/* ── Tab navigation ───────────────────────────── */}
      <div className="flex gap-1 rounded-2xl bg-white/[0.03] p-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-xl px-4 py-1.5 text-xs font-medium transition ${
              activeTab === tab.key
                ? "bg-cyan-500 text-cyan-950"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05]"
            }`}
          >
            {tab.label}
            {tab.key === "proof" && selectedRecord && (
              <span className="ml-1.5 inline-flex h-1.5 w-1.5 rounded-full bg-current opacity-60" />
            )}
          </button>
        ))}
      </div>

      {/* ── Tab content ──────────────────────────────── */}
      {activeTab === "timeline" && (
        <ProvenanceTimeline
          records={records}
          onSelectRecord={handleSelectRecord}
          selectedRecordId={selectedRecord?.record_id}
        />
      )}

      {activeTab === "integrity" && chainStatus && (
        <ChainIntegrityPanel status={chainStatus} />
      )}
      {activeTab === "integrity" && !chainStatus && (
        <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-8 text-center text-sm text-zinc-500">
          Chain status not available
        </div>
      )}

      {activeTab === "proof" && (
        <MerkleProofViewer
          record={selectedRecord}
          proof={proof}
          loading={proofLoading}
        />
      )}
    </div>
  );
}
