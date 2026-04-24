"use client";

import { useEffect, useRef, type ReactNode } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from "@mui/material";

type ConfirmModalProps = {
  isOpen: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDangerous?: boolean;
  isLoading?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  children?: ReactNode;
};

export function ConfirmModal({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isDangerous = false,
  isLoading = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    confirmRef.current?.focus();
  }, [isOpen, isLoading, onCancel]);

  if (!isOpen) return null;

  return (
    <Dialog
      open={isOpen}
      onClose={() => {
        if (isLoading) return;
        onCancel();
      }}
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
      <DialogTitle sx={{ color: "var(--app-fg)", fontWeight: 800 }}>{title}</DialogTitle>
      <DialogContent>
        {description ? (
          <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
            {description}
          </Typography>
        ) : null}
        {children ? <div style={{ marginTop: 16 }}>{children}</div> : null}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button
          onClick={onCancel}
          variant="outlined"
          disabled={isLoading}
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
          ref={confirmRef}
          onClick={() => void onConfirm()}
          variant="contained"
          disabled={isLoading}
          sx={{
            borderRadius: 999,
            bgcolor: isDangerous ? "rgba(239, 68, 68, 0.85)" : "var(--app-accent)",
            color: isDangerous ? "#fff" : "var(--app-accent-contrast)",
            "&:hover": { bgcolor: isDangerous ? "rgb(220, 38, 38)" : "var(--app-accent)" },
          }}
        >
          {isLoading ? "Working…" : confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
