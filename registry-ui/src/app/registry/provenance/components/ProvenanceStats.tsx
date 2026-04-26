"use client";

import { useMemo } from "react";
import type { ProvenanceRecord, ProvenanceChainStatus } from "@/lib/registryClient";
import { Box, Card, CardContent, Chip, Typography } from "@mui/material";

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
    <Box>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" },
          gap: 1.25,
        }}
      >
          <Card variant="outlined">
            <CardContent sx={{ p: 2 }}>
              <Typography sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "1.5rem", lineHeight: 1.15, fontWeight: 750, color: "var(--app-fg)" }}>
                {totalRecords.toLocaleString()}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Total Records
              </Typography>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    bgcolor: chainStatus?.chain_valid ? "var(--app-accent)" : "#ef4444",
                  }}
                />
                <Typography sx={{ fontSize: "1rem", fontWeight: 750, color: "var(--app-fg)" }}>
                  {chainStatus?.chain_valid ? "Valid" : "Broken"}
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Chain Integrity
              </Typography>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent sx={{ p: 2 }}>
              <Typography sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "1.5rem", lineHeight: 1.15, fontWeight: 750, color: "var(--app-fg)" }}>
                {stats.uniqueActors}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Unique Actors
              </Typography>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent sx={{ p: 2 }}>
              <Typography
                sx={{
                  fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: "1.5rem",
                  lineHeight: 1.15,
                  fontWeight: 750,
                  color: stats.errorCount > 0 ? "#b91c1c" : "var(--app-fg)",
                }}
              >
                {stats.errorCount}
              </Typography>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                Errors / Denials
              </Typography>
            </CardContent>
          </Card>

        <Box sx={{ gridColumn: "1 / -1" }}>
          <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, flexWrap: "wrap" }}>
                <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                  Action distribution
                </Typography>
                <Chip size="small" label={`${stats.topActions.length} action types`} sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)" }} />
              </Box>
              {stats.topActions.length === 0 ? (
                <Typography sx={{ mt: 1, fontSize: 13, color: "var(--app-muted)" }}>
                  No actions recorded yet. Events will appear here after tools, policies, contracts, or clients write to the ledger.
                </Typography>
              ) : (
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 1 }}>
                  {stats.topActions.map(([action, count]) => {
                    const pct = totalRecords > 0 ? Math.round((count / totalRecords) * 100) : 0;
                    return (
                      <Box key={action} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Box sx={{ height: 6, borderRadius: 1, bgcolor: "var(--app-accent)", width: Math.max(pct, 4) }} />
                        <Typography variant="body2" sx={{ color: "var(--app-fg)" }}>
                          {action}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color: "var(--app-muted)",
                            fontFamily:
                              "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                          }}
                        >
                          {count}
                        </Typography>
                        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                          ({pct}%)
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
              )}
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
}
