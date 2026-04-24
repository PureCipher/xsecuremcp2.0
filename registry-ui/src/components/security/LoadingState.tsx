import { Box, CircularProgress, Typography } from "@mui/material";

export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", py: 8 }}>
      <CircularProgress size={28} sx={{ color: "var(--app-accent)" }} />
      <Typography sx={{ mt: 1.5, fontSize: 13, color: "var(--app-muted)" }}>
        {message}
      </Typography>
    </Box>
  );
}
