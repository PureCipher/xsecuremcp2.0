"use client";

import { Card, CardContent, Typography } from "@mui/material";

export function MetricCard({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: string | number;
  detail?: string;
  accent?: boolean;
}) {
  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 4,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {label}
        </Typography>

        <Typography
          sx={{
            mt: 1,
            fontSize: 20,
            fontWeight: 900,
            color: accent ? "var(--app-accent)" : "var(--app-fg)",
          }}
        >
          {value}
        </Typography>

        {detail ? (
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            {detail}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}
