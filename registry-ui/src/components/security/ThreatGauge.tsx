"use client";

import { Box, Typography } from "@mui/material";

const LEVEL_CONFIG: Record<
  string,
  { labelColor: string; arcColor: string; pct: number }
> = {
  none: { labelColor: "var(--app-accent)", arcColor: "var(--app-accent)", pct: 5 },
  low: { labelColor: "rgb(56, 189, 248)", arcColor: "rgb(14, 165, 233)", pct: 25 },
  medium: { labelColor: "rgb(251, 191, 36)", arcColor: "rgb(245, 158, 11)", pct: 50 },
  high: { labelColor: "rgb(251, 146, 60)", arcColor: "rgb(249, 115, 22)", pct: 75 },
  critical: { labelColor: "rgb(248, 113, 113)", arcColor: "rgb(239, 68, 68)", pct: 95 },
};

export function ThreatGauge({
  level,
  score,
  size = "md",
}: {
  level: string;
  score?: number;
  size?: "sm" | "md" | "lg";
}) {
  const config = LEVEL_CONFIG[level.toLowerCase()] || LEVEL_CONFIG.none;
  const dims = size === "sm" ? 80 : size === "lg" ? 160 : 120;
  const strokeWidth = size === "sm" ? 6 : size === "lg" ? 10 : 8;
  const radius = (dims - strokeWidth) / 2;
  const circumference = Math.PI * radius; // semicircle
  const offset = circumference * (1 - config.pct / 100);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
      <svg width={dims} height={dims / 2 + 10} viewBox={`0 0 ${dims} ${dims / 2 + 10}`}>
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
          fill="none"
          stroke="currentColor"
          style={{ color: "var(--app-surface-ring)" }}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M ${strokeWidth / 2} ${dims / 2} A ${radius} ${radius} 0 0 1 ${dims - strokeWidth / 2} ${dims / 2}`}
          fill="none"
          stroke={config.arcColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <Typography
        sx={{
          fontSize: 12,
          fontWeight: 900,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: config.labelColor,
        }}
      >
        {level}
      </Typography>
      {score !== undefined ? (
        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
          Score: {score.toFixed(1)}
        </Typography>
      ) : null}
    </Box>
  );
}
