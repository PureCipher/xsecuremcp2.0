"use client";

import { useState, type ReactNode } from "react";
import { Box, Tab, Tabs } from "@mui/material";

/**
 * Iter 14.17 — Generic sub-tab container.
 *
 * Used by the consolidated "Now Live" and "Lifecycle" top-level
 * tabs so each top-level group can host its own sub-tabs without
 * the parent ``PolicyManager`` learning a second routing scheme.
 *
 * Each entry's ``content`` is rendered eagerly on demand (no lazy
 * import — content is already on the page when the user clicks the
 * top-level tab). Sub-tab state is local to the component so
 * navigating between top-level tabs doesn't reset sub-tab choice
 * across remounts; if a curator wants the sub-tab to persist across
 * a page reload, that's a future iteration (URL hash plumbing).
 */
export type TabGroupEntry = {
  /** Stable identifier for the sub-tab. */
  key: string;
  /** Human-readable label rendered on the sub-tab. */
  label: string;
  /** Content rendered when this sub-tab is active. */
  content: ReactNode;
  /** Optional badge count (e.g., pending items in this section). */
  badge?: number;
};

export function TabGroup({
  tabs,
  defaultKey,
}: {
  tabs: TabGroupEntry[];
  /** Sub-tab to show on first render. Defaults to the first entry. */
  defaultKey?: string;
}) {
  const initial = defaultKey ?? tabs[0]?.key ?? "";
  const [active, setActive] = useState<string>(initial);
  const activeEntry = tabs.find((t) => t.key === active) ?? tabs[0];

  if (!activeEntry) return null;

  return (
    <Box>
      <Box
        sx={{
          mb: 2,
          // Tighter sub-tab styling so the second-level navigation
          // reads as a sub-tier, not a duplicate of the top-level
          // tab bar.
          borderBottom: "1px solid var(--app-border)",
        }}
      >
        <Tabs
          value={active}
          onChange={(_, v: string) => setActive(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 36,
            "& .MuiTab-root": {
              minHeight: 36,
              fontSize: 12.5,
              textTransform: "none",
              color: "var(--app-muted)",
              fontWeight: 600,
              "&.Mui-selected": { color: "var(--app-fg)" },
            },
            "& .MuiTabs-indicator": { bgcolor: "var(--app-accent)" },
          }}
        >
          {tabs.map((tab) => (
            <Tab
              key={tab.key}
              value={tab.key}
              label={
                tab.badge ? (
                  <Box
                    component="span"
                    sx={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 0.75,
                    }}
                  >
                    <Box component="span">{tab.label}</Box>
                    <Box
                      component="span"
                      sx={{
                        minWidth: 18,
                        height: 18,
                        px: 0.6,
                        borderRadius: 999,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: "var(--app-accent)",
                        color: "var(--app-accent-contrast)",
                        fontSize: 10,
                        lineHeight: 1,
                        fontWeight: 700,
                      }}
                    >
                      {tab.badge}
                    </Box>
                  </Box>
                ) : (
                  tab.label
                )
              }
            />
          ))}
        </Tabs>
      </Box>
      <Box>{activeEntry.content}</Box>
    </Box>
  );
}
