"use client";

import { Box, Typography } from "@mui/material";

export function RegistryPageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <Box
      component="header"
      sx={{
        display: "flex",
        flexDirection: { xs: "column", md: "row" },
        alignItems: { xs: "flex-start", md: "flex-end" },
        justifyContent: "space-between",
        gap: 2,
      }}
    >
      <Box sx={{ display: "grid", gap: 0.75, maxWidth: 780 }}>
        {eyebrow ? (
          <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
            {eyebrow}
          </Typography>
        ) : null}
        <Typography variant="h4" sx={{ color: "var(--app-fg)" }}>
          {title}
        </Typography>
        {description ? (
          <Typography variant="body2" sx={{ maxWidth: 720, color: "var(--app-muted)" }}>
            {description}
          </Typography>
        ) : null}
      </Box>
      {actions ? <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>{actions}</Box> : null}
    </Box>
  );
}
