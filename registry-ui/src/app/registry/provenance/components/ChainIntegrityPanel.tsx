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
          bgcolor: ok ? "var(--app-accent)" : "#ef4444",
        }}
      />
    </Box>
  );
}

function HashDisplay({ label, hash }: { label: string; hash: string }) {
  if (!hash) return null;
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
        {label}:
      </Typography>
      <Box
        component="code"
        sx={{
          borderRadius: 1,
          bgcolor: "var(--app-control-bg)",
          px: 1,
          py: 0.25,
          fontSize: 10,
          fontFamily:
            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          color: "var(--app-accent)",
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
    <Box sx={{ borderRadius: 4, border: "1px solid var(--app-border)", bgcolor: "var(--app-surface)", p: 2.5 }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <StatusDot ok={allValid} />
            <Box>
              <Typography variant="body1" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Chain Integrity
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Ledger: {status.ledger_id} · {recordCountText} records
              </Typography>
            </Box>
          </Box>
          <Chip
            size="small"
            label={allValid ? "Intact" : "Tamper Detected"}
            sx={{
              bgcolor: allValid ? "var(--app-control-active-bg)" : "rgba(239, 68, 68, 0.15)",
              color: allValid ? "var(--app-muted)" : "#b91c1c",
              fontWeight: 700,
            }}
          />
        </Box>

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5 }}>
          <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.chain_valid ? "var(--app-accent)" : "#ef4444" }} />
              <Typography variant="body2" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Hash Chain
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {status.chain_valid
                ? "Every record correctly links to its predecessor via SHA-256"
                : "One or more chain links are broken — possible tampering"}
            </Typography>
          </Box>

          <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: status.tree_valid ? "var(--app-accent)" : "#ef4444" }} />
              <Typography variant="body2" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Merkle Tree
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {status.tree_valid ? "All leaf hashes form a consistent Merkle tree" : "Merkle tree rebuild does not match expected root"}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <HashDisplay label="Merkle root" hash={status.root_hash} />
          <HashDisplay label="Chain digest" hash={status.chain_digest} />
        </Box>

        <Box sx={{ borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)", p: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5, flexWrap: "wrap" }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Ledger Scheme
            </Typography>
            <Box
              component="span"
              sx={{
                borderRadius: 2,
                bgcolor: "rgba(6, 182, 212, 0.10)",
                px: 1,
                py: 0.25,
                fontSize: 10,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                color: "var(--app-accent)",
              }}
            >
              {scheme?.scheme ?? "unknown"}
            </Box>
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", columnGap: 3, rowGap: 0.75 }}>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Leaf count
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "var(--app-fg)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              }}
            >
              {scheme?.leaf_count?.toLocaleString() ?? "—"}
            </Typography>

            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Tree valid
            </Typography>
            <Typography variant="caption" sx={{ color: scheme?.tree_valid ? "var(--app-muted)" : "#b91c1c" }}>
              {scheme?.tree_valid ? "Yes" : "No"}
            </Typography>

            {isAnchored ? (
              <>
                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  Anchors committed
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "var(--app-fg)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  {scheme.anchor_count ?? 0}
                </Typography>

                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  Anchors valid
                </Typography>
                <Typography variant="caption" sx={{ color: scheme.anchors_valid ? "var(--app-muted)" : "#b91c1c" }}>
                  {scheme.anchors_valid ? "Yes" : "No"}
                </Typography>

                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  Records since anchor
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "var(--app-fg)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  {scheme.records_since_anchor ?? 0}
                </Typography>

                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  Anchor interval
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: "var(--app-fg)",
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  }}
                >
                  every {scheme.anchor_interval ?? "?"} records
                </Typography>

                {scheme.latest_anchor ? (
                  <>
                    <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                      Latest anchor tx
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "var(--app-accent)",
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
