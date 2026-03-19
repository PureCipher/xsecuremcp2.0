"use client";

import { useState, useEffect, useCallback } from "react";

export function useAutoRefresh(
  callback: () => Promise<void>,
  intervalMs: number = 30000,
  enabled: boolean = false,
) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await callback();
      setLastRefreshed(new Date());
    } finally {
      setIsRefreshing(false);
    }
  }, [callback]);

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs, refresh]);

  return { isRefreshing, lastRefreshed, refresh };
}

export function AutoRefreshToggle({
  enabled,
  onToggle,
  isRefreshing,
  lastRefreshed,
  onManualRefresh,
}: {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  isRefreshing: boolean;
  lastRefreshed: Date | null;
  onManualRefresh: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onManualRefresh}
        disabled={isRefreshing}
        className="rounded-full border border-[--app-border] px-3 py-1 text-[10px] font-medium text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-40"
      >
        {isRefreshing ? "Refreshing…" : "Refresh"}
      </button>
      <label className="flex cursor-pointer items-center gap-1.5">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="h-3 w-3 rounded border-[--app-border] bg-[--app-chrome-bg] text-[--app-accent] focus:ring-[--app-accent]"
        />
        <span className="text-[10px] text-[--app-muted]">Auto-refresh</span>
      </label>
      {lastRefreshed ? (
        <span className="text-[10px] text-[--app-muted]">
          Last: {lastRefreshed.toLocaleTimeString()}
        </span>
      ) : null}
    </div>
  );
}
