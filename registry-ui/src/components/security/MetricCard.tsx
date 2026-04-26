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
    <Card variant="outlined">
      <CardContent>
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {label}
        </Typography>

        <Typography
          sx={{
            mt: 1,
            fontSize: 24,
            lineHeight: 1.15,
            fontWeight: 750,
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
