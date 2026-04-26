"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, Box, Button, Card, CardContent, Collapse, TextField } from "@mui/material";

type Props = {
  listingId: string;
  availableActions: string[];
};

export function ReviewActions({ listingId, availableActions }: Props) {
  const router = useRouter();
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [reasonText, setReasonText] = useState("");

  async function runAction(action: string, reasonOverride?: string) {
    setBusyAction(action);
    setError(null);
    try {
      // moderator_id is intentionally NOT sent from the client. The
      // registry derives it from the authenticated session so the audit
      // trail can't be spoofed. Pre-fix this hard-coded the literal
      // "registry-ui" string for every action, breaking attribution.
      const response = await fetch(`/api/review/${encodeURIComponent(listingId)}/${encodeURIComponent(action)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason:
            reasonOverride ??
            (action === "approve" ? "Approved from registry UI." : "Updated from registry review queue."),
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.error) {
        setError(payload?.error ?? "Moderation failed.");
      } else {
        router.refresh();
      }
    } catch (err) {
      console.error("Moderation error", err);
      setError("Unable to reach the registry.");
    } finally {
      setBusyAction(null);
    }
  }

  if (!availableActions || availableActions.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mt: 1.5, display: "grid", gap: 1 }}>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
        {availableActions.map((action) => (
          <Button
            key={action}
            type="button"
            size="small"
            variant="outlined"
            disabled={busyAction === action}
            onClick={() => {
              const needsReason = ["reject", "request-changes", "suspend"].includes(action);
              if (needsReason) {
                setExpandedAction((current) => (current === action ? null : action));
                setReasonText("");
              } else {
                void runAction(action);
              }
            }}
            sx={{
              borderColor: "var(--app-accent)",
              color: "var(--app-muted)",
              "&:hover": { bgcolor: "var(--app-control-active-bg)", borderColor: "var(--app-accent)" },
              textTransform: "none",
              letterSpacing: "0.01em",
              fontWeight: 700,
              fontSize: 12,
            }}
          >
            {busyAction === action ? "Working…" : action.replace("-", " ")}
          </Button>
        ))}
      </Box>

      <Collapse in={!!expandedAction} unmountOnExit>
        <Card variant="outlined" sx={{ mt: 1, bgcolor: "var(--app-control-bg)" }}>
          <CardContent sx={{ p: 1.5, display: "grid", gap: 1 }}>
            <TextField
              value={reasonText}
              onChange={(e) => setReasonText(e.target.value)}
              placeholder="Add a short reason for this decision."
              multiline
              minRows={3}
              size="small"
              fullWidth
            />
            <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
              <Button
                type="button"
                size="small"
                variant="text"
                onClick={() => {
                  setExpandedAction(null);
                  setReasonText("");
                }}
                sx={{ color: "var(--app-muted)" }}
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="small"
                variant="contained"
                disabled={!expandedAction || busyAction === expandedAction || !reasonText.trim()}
                onClick={() => {
                  if (!expandedAction) return;
                  void runAction(expandedAction, reasonText.trim());
                  setExpandedAction(null);
                  setReasonText("");
                }}
                sx={{
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  "&:hover": { bgcolor: "var(--app-accent)" },
                }}
              >
                Confirm
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Collapse>

      {error ? <Alert severity="error">{error}</Alert> : null}
    </Box>
  );
}
