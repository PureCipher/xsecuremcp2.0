"use client";

import { useState } from "react";

type Props = {
  listingId: string;
  availableActions: string[];
};

export function ReviewActions({ listingId, availableActions }: Props) {
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [reasonText, setReasonText] = useState("");

  async function runAction(action: string, reasonOverride?: string) {
    setBusyAction(action);
    setError(null);
    try {
      const response = await fetch(`/api/review/${encodeURIComponent(listingId)}/${encodeURIComponent(action)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          moderator_id: "registry-ui",
          reason:
            reasonOverride ??
            (action === "approve" ? "Approved from registry UI." : "Updated from registry review queue."),
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.error) {
        setError(payload?.error ?? "Moderation failed.");
      } else {
        if (typeof window !== "undefined") {
          window.location.reload();
        }
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
    <div className="mt-2 space-y-1 text-[10px]">
      <div className="flex flex-wrap gap-2">
        {availableActions.map((action) => (
          <button
            key={action}
            type="button"
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
            className="rounded-full border border-[--app-accent] px-2.5 py-1 text-[10px] font-semibold text-[--app-muted] transition hover:bg-[--app-control-active-bg] disabled:opacity-60"
          >
            {busyAction === action ? "Working…" : action.replace("-", " ").toUpperCase()}
          </button>
        ))}
      </div>
      {expandedAction ? (
        <div className="space-y-1 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-2 ring-1 ring-[--app-surface-ring]">
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            placeholder="Add a short reason for this decision."
            className="h-16 w-full rounded-md border border-[--app-border] bg-transparent px-2 py-1 text-[10px] text-[--app-fg] outline-none ring-0 transition focus:border-[--app-accent] focus:ring-1 focus:ring-[--app-accent]"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-full px-2 py-1 text-[10px] text-[--app-muted] hover:text-[--app-fg]"
              onClick={() => {
                setExpandedAction(null);
                setReasonText("");
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={busyAction === expandedAction || !reasonText.trim()}
              onClick={() => {
                void runAction(expandedAction, reasonText.trim());
                setExpandedAction(null);
                setReasonText("");
              }}
              className="rounded-full bg-[--app-accent] px-3 py-1 text-[10px] font-semibold text-[--app-accent-contrast] shadow-sm transition hover:opacity-90 disabled:opacity-60"
            >
              Confirm
            </button>
          </div>
        </div>
      ) : null}
      {error ? <p className="text-[10px] text-rose-300">{error}</p> : null}
    </div>
  );
}
