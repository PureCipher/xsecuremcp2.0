"use client";

import { useState } from "react";
import type { ProvenanceRecord, ProvenanceProofResponse } from "@/lib/registryClient";
import { Box, Button, Chip, Typography } from "@mui/material";

const monoFont = "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";
const proofPanelSx = {
  borderRadius: 3,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-control-bg)",
  p: 2,
};

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
      <Box sx={{ borderRadius: 4, border: "1px solid var(--app-border)", bgcolor: "var(--app-surface)", p: 3, textAlign: "center" }}>
        <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
          Select a record from the timeline to view its Merkle proof
        </Typography>
        <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
          Each record has a cryptographic inclusion proof that verifies it belongs to the ledger
        </Typography>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box sx={{ borderRadius: 4, border: "1px solid var(--app-border)", bgcolor: "var(--app-surface)", p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box sx={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid var(--app-accent)", borderTopColor: "transparent", animation: "spin 1s linear infinite" }} />
          <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
            Loading proof for {truncHash(record.record_id)}…
          </Typography>
        </Box>
      </Box>
    );
  }

  if (!proof || proof.error) {
    return (
      <Box sx={{ borderRadius: 4, border: "1px solid rgba(239, 68, 68, 0.22)", bgcolor: "rgba(239, 68, 68, 0.08)", p: 3 }}>
        <Typography variant="body2" sx={{ color: "#b91c1c" }}>
          Failed to load proof: {proof?.error ?? "Unknown error"}
        </Typography>
      </Box>
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
    <Box sx={{ borderRadius: 4, border: "1px solid var(--app-border)", bgcolor: "var(--app-surface)", p: 2.5, boxShadow: "0 14px 40px rgba(15, 23, 42, 0.05)" }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
          <Box>
            <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Merkle Proof
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "var(--app-muted)",
                fontFamily: monoFont,
              }}
            >
              Record: {truncHash(record.record_id, 24)}
            </Typography>
          </Box>
          <Chip
            size="small"
            label="Verifiable"
            sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-fg)", fontWeight: 700 }}
          />
        </Box>

        <Box sx={proofPanelSx}>
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            Record Details
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 2, rowGap: 0.5, mt: 1 }}>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Action
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-fg)" }}>
              {record.action}
            </Typography>

            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Resource
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-fg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {record.resource_id || "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Actor
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-fg)" }}>
              {record.actor_id || "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Timestamp
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "var(--app-fg)",
                fontFamily: monoFont,
              }}
            >
              {record.timestamp}
            </Typography>
          </Box>
        </Box>

        <Box sx={proofPanelSx}>
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            Chain Position
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1, flexWrap: "wrap" }}>
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid var(--app-control-border)",
                bgcolor: "var(--app-surface)",
                px: 1,
                py: 0.5,
                color: "var(--app-muted)",
                fontSize: 10,
                fontFamily: monoFont,
              }}
            >
              prev {truncHash(chain.predecessor_hash, 12)}
            </Box>
            <Box sx={{ height: 1, width: 16, bgcolor: "var(--app-border)" }} />
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid var(--app-accent)",
                bgcolor: "var(--app-control-active-bg)",
                px: 1,
                py: 0.5,
                color: "var(--app-fg)",
                fontSize: 10,
                fontFamily: monoFont,
              }}
            >
              {truncHash(mp.leaf_hash, 12)}
            </Box>
            <Box sx={{ height: 1, width: 16, bgcolor: "var(--app-border)" }} />
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid var(--app-control-border)",
                bgcolor: "var(--app-surface)",
                px: 1,
                py: 0.5,
                color: "var(--app-muted)",
                fontSize: 10,
                fontFamily: monoFont,
              }}
            >
              {chain.successor_hash ? truncHash(chain.successor_hash, 12) : "HEAD"} next
            </Box>
          </Box>
        </Box>

        <Box sx={proofPanelSx}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, mb: 1 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Proof Path ({mp.proof_hashes.length} levels)
            </Typography>
            <Button
              onClick={() => setShowFull((v) => !v)}
              size="small"
              variant="text"
              sx={{ minWidth: 0, px: 1, fontSize: 11, color: "var(--app-accent)" }}
            >
              {showFull ? "Collapse" : "Expand"}
            </Button>
          </Box>

          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "var(--app-muted)" }}>
                leaf
              </Typography>
              <Box sx={{ height: 1, width: 12, bgcolor: "var(--app-accent)" }} />
              <Box
                component="code"
                sx={{
                  borderRadius: 1,
                  bgcolor: "var(--app-control-active-bg)",
                  px: 1,
                  py: 0.25,
                  fontSize: 10,
                  fontFamily:
                    monoFont,
                  color: "var(--app-fg)",
                }}
              >
                {showFull ? mp.leaf_hash : truncHash(mp.leaf_hash, 20)}
              </Box>
            </Box>

            {mp.proof_hashes.map((h, i) => (
              <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "var(--app-muted)" }}>
                  L{i + 1} {mp.directions[i]}
                </Typography>
                <Box sx={{ height: 1, width: 12, bgcolor: "var(--app-border)" }} />
                <Box
                  component="code"
                  sx={{
                    borderRadius: 1,
                    bgcolor: "var(--app-surface)",
                    px: 1,
                    py: 0.25,
                    fontSize: 10,
                    fontFamily:
                      monoFont,
                    color: "var(--app-muted)",
                  }}
                >
                  {showFull ? h : truncHash(h, 20)}
                </Box>
              </Box>
            ))}

            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "var(--app-muted)" }}>
                root
              </Typography>
              <Box sx={{ height: 1, width: 12, bgcolor: "var(--app-border)" }} />
              <Box
                component="code"
                sx={{
                  borderRadius: 1,
                  bgcolor: "var(--app-control-active-bg)",
                  px: 1,
                  py: 0.25,
                  fontSize: 10,
                  fontFamily:
                    monoFont,
                  color: "var(--app-fg)",
                }}
              >
                {showFull ? mp.root_hash : truncHash(mp.root_hash, 20)}
              </Box>
            </Box>
          </Box>
        </Box>

        <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, color: "var(--app-muted)" }}>
          <Typography variant="caption">
            Ledger root:{" "}
            <Box
              component="code"
              sx={{
                color: "var(--app-accent)",
                fontFamily: monoFont,
              }}
            >
              {truncHash(ledger.root_hash, 16)}
            </Box>
          </Typography>
          <Typography variant="caption">
            Total records: <Box component="span" sx={{ color: "var(--app-fg)" }}>{ledgerRecordCountText}</Box>
          </Typography>
          <Typography variant="caption">
            Exported: <Box component="span" sx={{ color: "var(--app-muted)" }}>{new Date(bundle.exported_at).toLocaleString()}</Box>
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
