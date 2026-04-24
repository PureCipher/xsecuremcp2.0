"use client";

import { Box } from "@mui/material";
import { MetricCard } from "@/components/security";

type StatsBarProps = {
  stats: Array<{ label: string; value: string }>;
};

export function StatsBar({ stats }: StatsBarProps) {
  return (
    <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr", xl: "repeat(5, 1fr)" } }}>
      {stats.map((item) => (
        <MetricCard key={item.label} label={item.label} value={item.value} />
      ))}
    </Box>
  );
}
