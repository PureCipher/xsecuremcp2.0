"use client";

import { useState, useCallback } from "react";
import type {
  ProvenanceRecord,
  ProvenanceChainStatus,
  ProvenanceProofResponse,
} from "@/lib/registryClient";
import { Box, Button, Stack, Typography } from "@mui/material";
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

  const handleSelectRecord = useCallback(async (record: ProvenanceRecord) => {
    setSelectedRecord(record);
    setActiveTab("proof");
    setProofLoading(true);
    setProof(null);

    try {
      const resp = await fetch(`/api/provenance/proof/${encodeURIComponent(record.record_id)}`);
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
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "timeline", label: "Timeline" },
    { key: "integrity", label: "Chain Integrity" },
    { key: "proof", label: "Merkle Proof" },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography
          variant="overline"
          sx={{ mb: 0.5, color: "var(--app-accent)", opacity: 0.85 }}
        >
          Provenance ledger
        </Typography>
        <Typography variant="h5" sx={{ color: "var(--app-fg)" }}>
          Smart provenance & immutable ledgers
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, color: "var(--app-muted)", maxWidth: 720 }}>
          Every model call, dataset usage, and outcome is hashed and chain-linked to prior events. Tamper-evident audit
          trail with Merkle tree verification.
        </Typography>
      </Box>

      <ProvenanceStats records={records} chainStatus={chainStatus} />

      <Stack
        direction="row"
        spacing={0.5}
        sx={{
          flexWrap: "wrap",
          p: 0.5,
          borderRadius: 3,
          bgcolor: "color-mix(in srgb, var(--app-fg) 4%, transparent)",
          border: "1px solid var(--app-border)",
        }}
      >
        {tabs.map((tab) => {
          const selected = activeTab === tab.key;
          return (
            <Button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              sx={{
                borderRadius: 2.5,
                px: 2,
                py: 0.75,
                textTransform: "none",
                fontSize: 12,
                fontWeight: 600,
                color: selected ? "var(--app-accent-contrast)" : "var(--app-muted)",
                bgcolor: selected ? "var(--app-accent)" : "transparent",
                "&:hover": {
                  bgcolor: selected ? "var(--app-accent)" : "color-mix(in srgb, var(--app-fg) 6%, transparent)",
                  color: selected ? "var(--app-accent-contrast)" : "var(--app-fg)",
                },
              }}
            >
              <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
                {tab.label}
                {tab.key === "proof" && selectedRecord ? (
                  <Box
                    component="span"
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor: "currentColor",
                      opacity: 0.55,
                    }}
                  />
                ) : null}
              </Box>
            </Button>
          );
        })}
      </Stack>

      {activeTab === "timeline" ? (
        <ProvenanceTimeline
          records={records}
          onSelectRecord={handleSelectRecord}
          selectedRecordId={selectedRecord?.record_id}
        />
      ) : null}

      {activeTab === "integrity" && chainStatus ? <ChainIntegrityPanel status={chainStatus} /> : null}
      {activeTab === "integrity" && !chainStatus ? (
        <Box
          sx={{
            borderRadius: 3,
            border: "1px solid var(--app-border)",
            bgcolor: "var(--app-control-bg)",
            p: 4,
            textAlign: "center",
          }}
        >
          <Typography sx={{ fontSize: 14, color: "var(--app-muted)" }}>Chain status not available</Typography>
        </Box>
      ) : null}

      {activeTab === "proof" ? (
        <MerkleProofViewer record={selectedRecord} proof={proof} loading={proofLoading} />
      ) : null}
    </Stack>
  );
}
