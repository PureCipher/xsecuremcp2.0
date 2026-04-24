"use client";

import { Dialog, DialogActions, DialogContent, DialogTitle, Button, Typography } from "@mui/material";

export function ConfirmationModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      fullWidth
      maxWidth="sm"
      slotProps={{
        paper: {
          sx: {
            borderRadius: 4,
            bgcolor: "var(--app-chrome-bg)",
            border: "1px solid var(--app-border)",
            backgroundImage: "none",
          },
        },
      }}
    >
      <DialogTitle sx={{ color: "var(--app-fg)", fontWeight: 700 }}>{title}</DialogTitle>
      <DialogContent>
        <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>{message}</Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button
          onClick={onCancel}
          variant="outlined"
          sx={{
            borderRadius: 999,
            borderColor: "var(--app-border)",
            color: "var(--app-muted)",
            "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
          }}
        >
          {cancelLabel}
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          sx={{
            borderRadius: 999,
            bgcolor: danger ? "rgba(239, 68, 68, 0.85)" : "var(--app-accent)",
            color: danger ? "#fff" : "var(--app-accent-contrast)",
            "&:hover": { bgcolor: danger ? "rgb(220, 38, 38)" : "var(--app-accent)" },
          }}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
