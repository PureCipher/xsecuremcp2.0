"use client";

import { Box, Card, CardContent, Typography } from "@mui/material";

export function KeyValuePanel({
  title,
  entries,
}: {
  title?: string;
  entries: { label: string; value: React.ReactNode }[];
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
        {title ? (
          <Typography
            sx={{
              mb: 2,
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            {title}
          </Typography>
        ) : null}

        <Box component="dl" sx={{ display: "grid", gap: 1 }}>
          {entries.map((e) => (
            <Box
              key={e.label}
              sx={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: 2,
              }}
            >
              <Typography component="dt" sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                {e.label}
              </Typography>
              <Typography component="dd" sx={{ m: 0, textAlign: "right", fontSize: 12, fontWeight: 700, color: "var(--app-fg)" }}>
                {e.value}
              </Typography>
            </Box>
          ))}
        </Box>
      </CardContent>
    </Card>
  );
}
