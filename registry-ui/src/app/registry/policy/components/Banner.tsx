"use client";

import { Alert, Button } from "@mui/material";

type BannerProps = {
  tone: "success" | "error";
  message: string;
  onDismiss?: () => void;
};

export function Banner({ tone, message, onDismiss }: BannerProps) {
  return (
    <Alert
      severity={tone === "success" ? "success" : "error"}
      action={
        onDismiss ? (
          <Button color="inherit" size="small" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : undefined
      }
      sx={{
        borderRadius: 4,
        "& .MuiAlert-message": { fontSize: 13, fontWeight: 600 },
      }}
    >
      {message}
    </Alert>
  );
}
