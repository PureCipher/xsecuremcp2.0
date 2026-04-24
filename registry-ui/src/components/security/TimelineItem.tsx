"use client";

import { StatusBadge } from "./StatusBadge";
import { Box, Typography } from "@mui/material";

export function TimelineItem({
  timestamp,
  title,
  detail,
  status,
}: {
  timestamp: string;
  title: string;
  detail?: string;
  status?: string;
}) {
  const timeStr = (() => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  })();

  return (
    <Box sx={{ position: "relative", borderLeft: "2px solid var(--app-border)", py: 1, pl: 2 }}>
      <Box
        sx={{
          position: "absolute",
          left: -5,
          top: 12,
          width: 8,
          height: 8,
          borderRadius: 999,
          bgcolor: "var(--app-accent)",
        }}
      />
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
          {title}
        </Typography>
        {status ? <StatusBadge status={status} /> : null}
      </Box>
      {detail ? (
        <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
          {detail}
        </Typography>
      ) : null}
      <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
        {timeStr}
      </Typography>
    </Box>
  );
}
