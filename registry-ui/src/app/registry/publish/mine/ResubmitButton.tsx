"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@mui/material";

export function ResubmitButton({ listingId }: { listingId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleResubmit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/review/${encodeURIComponent(listingId)}/resubmit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "Resubmitted by publisher." }),
        },
      );
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Resubmit failed.");
        return;
      }
      router.refresh();
    } catch {
      setError("Resubmit failed.");
    } finally {
      setBusy(false);
    }
  }, [listingId, router]);

  return (
    <>
      <Button
        size="small"
        variant="contained"
        disabled={busy}
        onClick={() => void handleResubmit()}
        sx={{
          bgcolor: "var(--app-accent)",
          color: "white",
          boxShadow: "none",
          "&:hover": { bgcolor: "var(--app-accent)", filter: "brightness(0.95)", boxShadow: "none" },
        }}
      >
        {busy ? "Resubmitting..." : "Resubmit"}
      </Button>
      {error ? (
        <span style={{ fontSize: 11, color: "#b91c1c" }}>{error}</span>
      ) : null}
    </>
  );
}
