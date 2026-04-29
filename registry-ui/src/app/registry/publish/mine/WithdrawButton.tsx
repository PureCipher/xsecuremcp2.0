"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField } from "@mui/material";

export function WithdrawButton({
  listingId,
  displayName,
}: {
  listingId: string;
  displayName: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleWithdraw = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/review/${encodeURIComponent(listingId)}/withdraw`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: reason.trim() || "Withdrawn by publisher." }),
        },
      );
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Withdraw failed.");
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Withdraw failed.");
    } finally {
      setBusy(false);
    }
  }, [listingId, reason, router]);

  return (
    <>
      <Button
        size="small"
        variant="outlined"
        onClick={() => setOpen(true)}
        sx={{
          borderColor: "rgba(239, 68, 68, 0.4)",
          color: "#b91c1c",
          "&:hover": { bgcolor: "rgba(239, 68, 68, 0.08)", borderColor: "rgba(239, 68, 68, 0.6)" },
        }}
      >
        Withdraw
      </Button>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>
          Withdraw listing
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            This will remove <strong>{displayName}</strong> from the review queue.
            Reviewers and admins will be notified. You can re-publish a new version later.
          </DialogContentText>
          <TextField
            label="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Found an issue, will resubmit later"
            size="small"
            fullWidth
            multiline
            minRows={2}
          />
          {error ? (
            <DialogContentText sx={{ mt: 1, color: "#b91c1c", fontSize: 13 }}>
              {error}
            </DialogContentText>
          ) : null}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setOpen(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={() => void handleWithdraw()}
            disabled={busy}
            variant="contained"
            color="error"
          >
            {busy ? "Withdrawing..." : "Withdraw"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
