"use client";

import { useMemo } from "react";
import type { ProvenanceRecord, ProvenanceChainStatus } from "@/lib/registryClient";
import { Box, Card, CardContent, Typography } from "@mui/material";

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
          gap: 1.5,
        }}
      >
          <Card
            variant="outlined"
            sx={{ borderRadius: 3, borderColor: "rgba(255, 255, 255, 0.10)", bgcolor: "rgba(255, 255, 255, 0.02)", boxShadow: "none" }}
          >
            <CardContent sx={{ p: 2 }}>
              <Typography sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "1.65rem", fontWeight: 700, color: "rgb(244, 244, 245)" }}>
                {totalRecords.toLocaleString()}
              </Typography>
              <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                Total Records
              </Typography>
            </CardContent>
          </Card>

          <Card
            variant="outlined"
            sx={{ borderRadius: 3, borderColor: "rgba(255, 255, 255, 0.10)", bgcolor: "rgba(255, 255, 255, 0.02)", boxShadow: "none" }}
          >
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    bgcolor: chainStatus?.chain_valid ? "var(--app-accent)" : "rgb(251, 113, 133)",
                  }}
                />
                <Typography sx={{ fontSize: "1.1rem", fontWeight: 700, color: "rgb(244, 244, 245)" }}>
                  {chainStatus?.chain_valid ? "Valid" : "Broken"}
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                Chain Integrity
              </Typography>
            </CardContent>
          </Card>

          <Card
            variant="outlined"
            sx={{ borderRadius: 3, borderColor: "rgba(255, 255, 255, 0.10)", bgcolor: "rgba(255, 255, 255, 0.02)", boxShadow: "none" }}
          >
            <CardContent sx={{ p: 2 }}>
              <Typography sx={{ fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: "1.65rem", fontWeight: 700, color: "rgb(244, 244, 245)" }}>
                {stats.uniqueActors}
              </Typography>
              <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                Unique Actors
              </Typography>
            </CardContent>
          </Card>

          <Card
            variant="outlined"
            sx={{ borderRadius: 3, borderColor: "rgba(255, 255, 255, 0.10)", bgcolor: "rgba(255, 255, 255, 0.02)", boxShadow: "none" }}
          >
            <CardContent sx={{ p: 2 }}>
              <Typography
                sx={{
                  fontFamily: "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: "1.65rem",
                  fontWeight: 700,
                  color: stats.errorCount > 0 ? "rgb(253, 164, 175)" : "rgb(244, 244, 245)",
                }}
              >
                {stats.errorCount}
              </Typography>
              <Typography variant="caption" sx={{ color: "rgb(113, 113, 122)" }}>
                Errors / Denials
              </Typography>
            </CardContent>
          </Card>

        <Box sx={{ gridColumn: "1 / -1" }}>
          <Card
            variant="outlined"
            sx={{ borderRadius: 3, borderColor: "rgba(255, 255, 255, 0.10)", bgcolor: "rgba(255, 255, 255, 0.02)", boxShadow: "none" }}
          >
            <CardContent sx={{ p: 2 }}>
              <Typography variant="overline" sx={{ color: "rgba(103, 232, 249, 0.70)" }}>
                Action Distribution
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.25, mt: 1 }}>
                {stats.topActions.map(([action, count]) => {
                  const pct = totalRecords > 0 ? Math.round((count / totalRecords) * 100) : 0;
                  return (
                    <Box key={action} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <Box sx={{ height: 6, borderRadius: 999, bgcolor: "rgba(6, 182, 212, 0.60)", width: Math.max(pct, 4) }} />
                      <Typography variant="body2" sx={{ color: "rgb(212, 212, 216)" }}>
                        {action}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          color: "rgb(113, 113, 122)",
                          fontFamily:
                            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        }}
                      >
                        {count}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "rgb(82, 82, 91)" }}>
                        ({pct}%)
                      </Typography>
                    </Box>
                  );
                })}
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
}
