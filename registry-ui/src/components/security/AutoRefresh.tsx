"use client";

import { useState, useEffect, useCallback } from "react";
import { Box, Button, Checkbox, FormControlLabel, Typography } from "@mui/material";

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
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
      <Button
        type="button"
        onClick={onManualRefresh}
        disabled={isRefreshing}
        size="small"
        variant="outlined"
        sx={{
          borderRadius: 999,
          borderColor: "var(--app-border)",
          color: "var(--app-muted)",
          "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
        }}
      >
        {isRefreshing ? "Refreshing…" : "Refresh"}
      </Button>

      <FormControlLabel
        control={
          <Checkbox
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            size="small"
          />
        }
        label={<Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>Auto-refresh</Typography>}
      />

      {lastRefreshed ? (
        <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
          Last: {lastRefreshed.toLocaleTimeString()}
        </Typography>
      ) : null}
    </Box>
  );
}
