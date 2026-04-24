"use client";

import type { ProvenanceChainStatus } from "@/lib/registryClient";
import { Box, Chip, Typography } from "@mui/material";

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <Box sx={{ position: "relative", width: 12, height: 12, display: "inline-flex" }}>
      {ok ? (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            bgcolor: "var(--app-accent)",
            opacity: 0.4,
            animation: "ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite",
          }}
        />
      ) : null}
      <Box
        sx={{
          position: "relative",
          width: 12,
          height: 12,
          borderRadius: "50%",
          bgcolor: ok ? "var(--app-accent)" : "rgb(251, 113, 133)",
        }}
      />
    </Box>
  );
}

function HashDisplay({ label, hash }: { label: string; hash: string }) {
  if (!hash) return null;
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
        {label}:
      </Typography>
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
          color: "rgba(103, 232, 249, 0.80)",
          userSelect: "all",
        }}
      >
        {hash}
      </Box>
    </Box>
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
    <Box sx={{ borderRadius: 4, border: "1px solid rgba(255,255,255,0.10)", bgcolor: "rgba(255,255,255,0.02)", p: 2.5 }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <StatusDot ok={allValid} />
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 700, color: "rgb(228, 228, 231)" }}>
                Chain Integrity
              </Typography>
              <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                Ledger: {status.ledger_id} · {recordCountText} records
              </Typography>
            </Box>
          </Box>
          <Chip
            size="small"
            label={allValid ? "Intact" : "Tamper Detected"}
            sx={{
              borderRadius: 999,
              bgcolor: allValid ? "var(--app-control-active-bg)" : "rgba(239, 68, 68, 0.15)",
              color: allValid ? "var(--app-muted)" : "rgb(253, 164, 175)",
              fontWeight: 700,
            }}
          />
        </Box>

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5 }}>
          <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.chain_valid ? "var(--app-accent)" : "rgb(251, 113, 133)" }} />
              <Typography variant="body2" sx={{ fontWeight: 700, color: "rgb(212, 212, 216)" }}>
                Hash Chain
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: "rgb(113, 113, 122)" }}>
              {status.chain_valid
                ? "Every record correctly links to its predecessor via SHA-256"
                : "One or more chain links are broken — possible tampering"}
            </Typography>
          </Box>

          <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.tree_valid ? "var(--app-accent)" : "rgb(251, 113, 133)" }} />
              <Typography variant="body2" sx={{ fontWeight: 700, color: "rgb(212, 212, 216)" }}>
                Merkle Tree
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: "rgb(113, 113, 122)" }}>
              {status.tree_valid ? "All leaf hashes form a consistent Merkle tree" : "Merkle tree rebuild does not match expected root"}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <HashDisplay label="Merkle root" hash={status.root_hash} />
          <HashDisplay label="Chain digest" hash={status.chain_digest} />
        </Box>

        <Box sx={{ borderRadius: 3, border: "1px solid rgba(255,255,255,0.05)", bgcolor: "rgba(255,255,255,0.02)", p: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5, flexWrap: "wrap" }}>
            <Typography variant="overline" sx={{ color: "rgba(103, 232, 249, 0.70)" }}>
              Ledger Scheme
            </Typography>
            <Box
              component="span"
              sx={{
                borderRadius: 999,
                bgcolor: "rgba(6, 182, 212, 0.10)",
                px: 1,
                py: 0.25,
                fontSize: 10,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                color: "rgb(103, 232, 249)",
              }}
            >
              {scheme?.scheme ?? "unknown"}
            </Box>
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: 3, rowGap: 0.75 }}>
            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Leaf count
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "rgb(212, 212, 216)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {scheme?.leaf_count?.toLocaleString() ?? "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
              Tree valid
            </Typography>
            <Typography variant="caption" sx={{ color: scheme?.tree_valid ? "var(--app-muted)" : "rgb(253, 164, 175)" }}>
              {scheme?.tree_valid ? "Yes" : "No"}
            </Typography>

            {isAnchored ? (
              <>
                <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                  Anchors committed
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "rgb(212, 212, 216)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  {scheme.anchor_count ?? 0}
                </Typography>

                <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                  Anchors valid
                </Typography>
                <Typography variant="caption" sx={{ color: scheme.anchors_valid ? "var(--app-muted)" : "rgb(253, 164, 175)" }}>
                  {scheme.anchors_valid ? "Yes" : "No"}
                </Typography>

                <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                  Records since anchor
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "rgb(212, 212, 216)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  {scheme.records_since_anchor ?? 0}
                </Typography>

                <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                  Anchor interval
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "rgb(212, 212, 216)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  every {scheme.anchor_interval ?? "?"} records
                </Typography>

                {scheme.latest_anchor ? (
                  <>
                    <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                      Latest anchor tx
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "rgb(103, 232, 249)",
                        fontFamily:
                          "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {String(scheme.latest_anchor.tx_id ?? "—")}
                    </Typography>
                  </>
                ) : null}
              </>
            ) : null}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
