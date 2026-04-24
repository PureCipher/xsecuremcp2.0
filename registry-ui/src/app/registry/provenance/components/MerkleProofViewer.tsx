"use client";

import { useState } from "react";
import type { ProvenanceRecord, ProvenanceProofResponse } from "@/lib/registryClient";
import { Box, Button, Chip, Typography } from "@mui/material";

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
      <Box sx={{ borderRadius: 4, border: "1px solid rgba(255,255,255,0.10)", bgcolor: "rgba(255,255,255,0.02)", p: 3, textAlign: "center" }}>
        <Typography variant="body2" sx={{ color: "rgb(113, 113, 122)" }}>
          Select a record from the timeline to view its Merkle proof
        </Typography>
        <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "rgb(82, 82, 91)" }}>
          Each record has a cryptographic inclusion proof that verifies it belongs to the ledger
        </Typography>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box sx={{ borderRadius: 4, border: "1px solid rgba(255,255,255,0.10)", bgcolor: "rgba(255,255,255,0.02)", p: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box sx={{ width: 16, height: 16, borderRadius: "50%", border: "2px solid rgb(34, 211, 238)", borderTopColor: "transparent", animation: "spin 1s linear infinite" }} />
          <Typography variant="body2" sx={{ color: "rgb(161, 161, 170)" }}>
            Loading proof for {truncHash(record.record_id)}…
          </Typography>
        </Box>
      </Box>
    );
  }

  if (!proof || proof.error) {
    return (
      <Box sx={{ borderRadius: 4, border: "1px solid rgba(244, 63, 94, 0.20)", bgcolor: "rgba(244, 63, 94, 0.05)", p: 3 }}>
        <Typography variant="body2" sx={{ color: "rgb(253, 164, 175)" }}>
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
    <Box sx={{ borderRadius: 4, border: "1px solid rgba(255,255,255,0.10)", bgcolor: "rgba(255,255,255,0.02)", p: 2.5 }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
          <Box>
            <Typography variant="body1" sx={{ fontWeight: 700, color: "rgb(228, 228, 231)" }}>
              Merkle Proof
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "rgb(113, 113, 122)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              Record: {truncHash(record.record_id, 24)}
            </Typography>
          </Box>
          <Chip
            size="small"
            label="Verifiable"
            sx={{ borderRadius: 999, bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700 }}
          />
        </Box>

        <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
          <Typography variant="overline" sx={{ color: "rgba(103, 232, 249, 0.70)" }}>
            Record Details
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 2, rowGap: 0.5, mt: 1 }}>
            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Action
            </Typography>
            <Typography variant="caption" sx={{ color: "rgb(212, 212, 216)" }}>
              {record.action}
            </Typography>

            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Resource
            </Typography>
            <Typography variant="caption" sx={{ color: "rgb(212, 212, 216)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {record.resource_id || "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Actor
            </Typography>
            <Typography variant="caption" sx={{ color: "rgb(212, 212, 216)" }}>
              {record.actor_id || "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Timestamp
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "rgb(212, 212, 216)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {record.timestamp}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
          <Typography variant="overline" sx={{ color: "rgba(103, 232, 249, 0.70)" }}>
            Chain Position
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1, flexWrap: "wrap" }}>
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid rgba(255,255,255,0.05)",
                bgcolor: "rgba(39, 39, 42, 0.50)",
                px: 1,
                py: 0.5,
                color: "rgb(113, 113, 122)",
                fontSize: 10,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              ← {truncHash(chain.predecessor_hash, 12)}
            </Box>
            <Box sx={{ height: 1, width: 16, bgcolor: "rgba(6, 182, 212, 0.30)" }} />
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid rgba(6, 182, 212, 0.30)",
                bgcolor: "rgba(6, 182, 212, 0.10)",
                px: 1,
                py: 0.5,
                color: "rgb(103, 232, 249)",
                fontSize: 10,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {truncHash(mp.leaf_hash, 12)}
            </Box>
            <Box sx={{ height: 1, width: 16, bgcolor: "rgba(6, 182, 212, 0.30)" }} />
            <Box
              sx={{
                borderRadius: 2,
                border: "1px solid rgba(255,255,255,0.05)",
                bgcolor: "rgba(39, 39, 42, 0.50)",
                px: 1,
                py: 0.5,
                color: "rgb(113, 113, 122)",
                fontSize: 10,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {chain.successor_hash ? truncHash(chain.successor_hash, 12) : "HEAD"} →
            </Box>
          </Box>
        </Box>

        <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, mb: 1 }}>
            <Typography variant="overline" sx={{ color: "rgba(103, 232, 249, 0.70)" }}>
              Proof Path ({mp.proof_hashes.length} levels)
            </Typography>
            <Button
              onClick={() => setShowFull((v) => !v)}
              size="small"
              variant="text"
              sx={{ minWidth: 0, px: 1, fontSize: 10, textTransform: "none", color: "rgb(34, 211, 238)" }}
            >
              {showFull ? "Collapse" : "Expand"}
            </Button>
          </Box>

          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "rgb(82, 82, 91)" }}>
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
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  color: "var(--app-muted)",
                }}
              >
                {showFull ? mp.leaf_hash : truncHash(mp.leaf_hash, 20)}
              </Box>
            </Box>

            {mp.proof_hashes.map((h, i) => (
              <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "rgb(82, 82, 91)" }}>
                  L{i + 1} {mp.directions[i]}
                </Typography>
                <Box sx={{ height: 1, width: 12, bgcolor: "rgba(255,255,255,0.10)" }} />
                <Box
                  component="code"
                  sx={{
                    borderRadius: 1,
                    bgcolor: "rgba(255,255,255,0.05)",
                    px: 1,
                    py: 0.25,
                    fontSize: 10,
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    color: "rgb(161, 161, 170)",
                  }}
                >
                  {showFull ? h : truncHash(h, 20)}
                </Box>
              </Box>
            ))}

            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="caption" sx={{ width: 52, textAlign: "right", color: "rgb(82, 82, 91)" }}>
                root
              </Typography>
              <Box sx={{ height: 1, width: 12, bgcolor: "rgba(6, 182, 212, 0.30)" }} />
              <Box
                component="code"
                sx={{
                  borderRadius: 1,
                  bgcolor: "rgba(6, 182, 212, 0.10)",
                  px: 1,
                  py: 0.25,
                  fontSize: 10,
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  color: "rgb(103, 232, 249)",
                }}
              >
                {showFull ? mp.root_hash : truncHash(mp.root_hash, 20)}
              </Box>
            </Box>
          </Box>
        </Box>

        <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 2, color: "rgb(113, 113, 122)" }}>
          <Typography variant="caption">
            Ledger root:{" "}
            <Box
              component="code"
              sx={{
                color: "rgba(103, 232, 249, 0.60)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {truncHash(ledger.root_hash, 16)}
            </Box>
          </Typography>
          <Typography variant="caption">
            Total records: <Box component="span" sx={{ color: "rgb(212, 212, 216)" }}>{ledgerRecordCountText}</Box>
          </Typography>
          <Typography variant="caption">
            Exported: <Box component="span" sx={{ color: "rgb(161, 161, 170)" }}>{new Date(bundle.exported_at).toLocaleString()}</Box>
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
