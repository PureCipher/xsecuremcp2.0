"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from "@mui/material";

/**
 * Iter 14.11 — admin "Deregister" affordance on the listing detail page.
 *
 * Renders a destructive button that opens a confirmation dialog with
 * a required reason field. Submission POSTs to
 * ``/api/review/{listing_id}/deregister``; the backend records the
 * decision in the listing's moderation log, transitions the listing
 * to ``DEREGISTERED`` status, and broadcasts a platform-wide
 * notification to every role.
 *
 * Why a separate client component? The listing detail page is a
 * server component (it fetches data server-side), so any interactive
 * state — modal open/closed, reason text, in-flight request — has to
 * live in a "use client" island. This is that island.
 */
export function DeregisterListingButton({
  listingId,
  toolName,
  displayName,
  status,
}: {
  listingId: string;
  toolName: string;
  displayName: string;
  status: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Already-deregistered listings have nothing to deregister.
  // Drafts/rejections never reached the catalog so there's nothing
  // to remove from clients. Everything else (published, suspended,
  // deprecated, pending review) gets the affordance.
  const eligibleStatuses = new Set([
    "published",
    "suspended",
    "deprecated",
    "pending_review",
  ]);
  if (!eligibleStatuses.has(status.toLowerCase())) {
    return null;
  }

  const handleConfirm = async () => {
    setError(null);
    setBusy(true);
    try {
      const response = await fetch(
        `/api/review/${encodeURIComponent(listingId)}/deregister`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: reason.trim() }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload?.error) {
        setError(
          payload?.error ?? `Deregister failed (${response.status}).`,
        );
        return;
      }
      // Success — close the modal and refresh the page so the new
      // DEREGISTERED banner + status take effect immediately.
      setOpen(false);
      setReason("");
      router.refresh();
    } catch {
      setError("Network error. Try again or refresh the page.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        variant="outlined"
        size="small"
        sx={{
          borderColor: "rgba(244, 63, 94, 0.55)",
          color: "#b91c1c",
          textTransform: "none",
          fontWeight: 700,
          fontSize: 12,
          letterSpacing: "0.01em",
          "&:hover": {
            borderColor: "#b91c1c",
            bgcolor: "rgba(244, 63, 94, 0.06)",
          },
        }}
      >
        Deregister server
      </Button>

      <Dialog
        open={open}
        onClose={() => (busy ? null : setOpen(false))}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          Deregister {displayName}?
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: 13, color: "var(--app-muted)", mb: 2 }}>
            This is a <strong>terminal</strong> action. The listing
            will be removed from the public catalog, proxy-mode calls
            will be rejected with HTTP 410, and a notification will be
            broadcast to every user of the platform. The decision is
            recorded permanently in the listing&apos;s moderation log.
          </Typography>
          <Box
            sx={{
              p: 1.5,
              mb: 2,
              border: "1px solid var(--app-border)",
              borderRadius: 2,
              bgcolor: "var(--app-control-bg)",
              fontFamily:
                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 12,
              color: "var(--app-fg)",
            }}
          >
            {toolName}
          </Box>
          <TextField
            autoFocus
            fullWidth
            multiline
            minRows={3}
            label="Reason (required)"
            placeholder="Why is this listing being deregistered? Curator users will see this in the notification."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
            slotProps={{ htmlInput: { maxLength: 500 } }}
            helperText={`${reason.length}/500 — included in the platform-wide notification.`}
          />
          {error ? (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setOpen(false)}
            disabled={busy}
            sx={{ textTransform: "none" }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={busy || reason.trim().length === 0}
            variant="contained"
            color="error"
            sx={{ textTransform: "none", minWidth: 160 }}
          >
            {busy ? (
              <CircularProgress size={18} sx={{ color: "#fff" }} />
            ) : (
              "Deregister permanently"
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
