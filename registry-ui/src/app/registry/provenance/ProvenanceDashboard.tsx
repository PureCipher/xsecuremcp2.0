"use client";

import { useState, useCallback } from "react";
import type {
  ProvenanceRecord,
  ProvenanceChainStatus,
  ProvenanceProofResponse,
} from "@/lib/registryClient";
import { Box, Button, Card, CardContent, Chip, Divider, Stack, Typography } from "@mui/material";
import { ProvenanceTimeline } from "./components/ProvenanceTimeline";
import { ChainIntegrityPanel } from "./components/ChainIntegrityPanel";
import { MerkleProofViewer } from "./components/MerkleProofViewer";
import { ProvenanceStats } from "./components/ProvenanceStats";
import { RegistryPageHeader } from "@/components/security";

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
    // Iter 14.25 — renamed "Timeline" → "Audit log" to reflect the
    // tab's actual purpose for the operator (forensic audit feed
    // with filters + CSV export). The component remains
    // ProvenanceTimeline; only the user-facing label changes.
    { key: "timeline", label: "Audit log" },
    { key: "integrity", label: "Chain Integrity" },
    { key: "proof", label: "Merkle Proof" },
  ];

  const totalRecords = chainStatus?.record_count ?? records.length;
  const chainHealthy = Boolean(chainStatus?.chain_valid && chainStatus?.tree_valid);
  const selectedRecordLabel = selectedRecord
    ? `${selectedRecord.action} / ${selectedRecord.record_id.slice(0, 10)}`
    : "No record selected";

  return (
    <Stack spacing={2.5}>
      <RegistryPageHeader
        eyebrow="Provenance ledger"
        title="Smart provenance & immutable ledgers"
        description="Every model call, dataset usage, and outcome is hashed and chain-linked to prior events. Tamper-evident audit trail with Merkle tree verification."
      />

      <Card variant="outlined" sx={{ overflow: "hidden" }}>
        <CardContent sx={{ p: 0 }}>
          <Box
            sx={{
              p: { xs: 2.5, md: 3 },
              display: "flex",
              flexDirection: { xs: "column", lg: "row" },
              alignItems: { xs: "flex-start", lg: "center" },
              justifyContent: "space-between",
              gap: 2.5,
            }}
          >
            <Box sx={{ display: "grid", gap: 0.75, maxWidth: 760 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Ledger workspace
              </Typography>
              <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
                Verify events from timeline to proof
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Review recorded events, inspect chain health, and open a Merkle proof for any selected record.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Chip
                label={`${totalRecords.toLocaleString()} records`}
                sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }}
              />
              <Chip
                label={chainStatus ? (chainHealthy ? "Chain intact" : "Chain broken") : "Chain unavailable"}
                sx={{
                  bgcolor: chainHealthy ? "var(--app-control-active-bg)" : "rgba(239, 68, 68, 0.12)",
                  color: chainHealthy ? "var(--app-fg)" : "#b91c1c",
                  fontWeight: 700,
                }}
              />
              <Chip
                label={selectedRecordLabel}
                sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }}
              />
            </Box>
          </Box>

          <Box sx={{ px: { xs: 2.5, md: 3 }, pb: { xs: 2.5, md: 3 } }}>
            <ProvenanceStats records={records} chainStatus={chainStatus} />
          </Box>

          <Divider />

          <Box sx={{ px: { xs: 1.5, md: 2 }, bgcolor: "var(--app-control-bg)" }}>
            <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap", py: 1 }}>
              {tabs.map((tab) => {
                const selected = activeTab === tab.key;
                return (
                  <Button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    variant={selected ? "contained" : "text"}
                    sx={{
                      px: 1.5,
                      py: 0.75,
                      textTransform: "none",
                      fontSize: 12,
                      fontWeight: 700,
                      color: selected ? "var(--app-accent-contrast)" : "var(--app-muted)",
                      bgcolor: selected ? "var(--app-accent)" : "transparent",
                      "&:hover": {
                        bgcolor: selected ? "var(--app-accent)" : "var(--app-hover-bg)",
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
                            opacity: 0.6,
                          }}
                        />
                      ) : null}
                    </Box>
                  </Button>
                );
              })}
            </Stack>
          </Box>

          <Divider />

          <Box sx={{ p: { xs: 2, md: 2.5 } }}>
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
          </Box>
        </CardContent>
      </Card>
    </Stack>
  );
}
