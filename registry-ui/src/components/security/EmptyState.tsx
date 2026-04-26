import { Box, Typography } from "@mui/material";

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message?: string;
}) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 4,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-surface)",
        py: 6,
        boxShadow: "0 14px 40px rgba(15, 23, 42, 0.05)",
      }}
    >
      <Typography sx={{ mb: 1, fontSize: 24, color: "var(--app-accent)", opacity: 0.6 }}>
        ∅
      </Typography>
      <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>{title}</Typography>
      {message ? (
        <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)", textAlign: "center", px: 2 }}>
          {message}
        </Typography>
      ) : null}
    </Box>
  );
}
