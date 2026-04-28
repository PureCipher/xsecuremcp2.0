"use client";

import type { PolicyTabKey } from "../hooks/useTabNavigation";
import { Box, Tab, Tabs } from "@mui/material";

type PolicyTabsProps = {
  activeTab: PolicyTabKey;
  onTabChange: (tab: PolicyTabKey) => void;
  pendingCount?: number;
  versionCount?: number;
};

// Iter 14.17 — top-level navigation reflects user workflow rather
// than backend taxonomy:
//
//   Catalog       → install bundles
//   Now Live      → see what's running (live chain + tools)
//   Proposals     → review staged changes
//   Lifecycle     → versions + migrations
//   Metrics       → monitor health
//
// The two merged groups (Now Live, Lifecycle) host their original
// content as sub-tabs via :file:`TabGroup.tsx`. Five top-level
// tabs total (down from seven post-14.16) — and crucially, the
// labels read as activities, not as backend planes.
const TAB_ITEMS: Array<{ key: PolicyTabKey; label: string }> = [
  { key: "catalog", label: "Catalog" },
  { key: "now-live", label: "Now Live" },
  { key: "proposals", label: "Proposals" },
  { key: "lifecycle", label: "Lifecycle" },
  { key: "metrics", label: "Metrics" },
];

export function PolicyTabs({
  activeTab,
  onTabChange,
  pendingCount,
  versionCount,
}: PolicyTabsProps) {
  return (
    <Box aria-label="Policy management tabs">
      <Tabs
        value={activeTab}
        onChange={(_, v) => onTabChange(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{
          minHeight: 40,
          "& .MuiTab-root": { minHeight: 40 },
          "& .MuiTabs-indicator": { bgcolor: "var(--app-accent)" },
        }}
      >
        {TAB_ITEMS.map((item) => {
          // Iter 14.17 — the version count badge moved to the
          // Lifecycle tab (which now hosts Versions as a sub-tab),
          // so the badge surfaces at the top level rather than
          // hiding inside the inner sub-tab.
          const badge =
            item.key === "proposals" && pendingCount
              ? pendingCount
              : item.key === "lifecycle" && versionCount
                ? versionCount
                : null;

          return (
            <Tab
              key={item.key}
              value={item.key}
              label={
                badge ? (
                  <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
                    <Box component="span">{item.label}</Box>
                    <Box
                      component="span"
                      sx={{
                        minWidth: 20,
                        height: 20,
                        px: 0.75,
                        borderRadius: 999,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: "var(--app-accent)",
                        color: "var(--app-accent-contrast)",
                        fontSize: 11,
                        lineHeight: 1,
                        fontWeight: 700,
                      }}
                    >
                      {badge}
                    </Box>
                  </Box>
                ) : (
                  item.label
                )
              }
            />
          );
        })}
      </Tabs>
    </Box>
  );
}
