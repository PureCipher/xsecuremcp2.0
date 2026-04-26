"use client";

import type { PolicyTabKey } from "../hooks/useTabNavigation";
import { Box, Tab, Tabs } from "@mui/material";

type PolicyTabsProps = {
  activeTab: PolicyTabKey;
  onTabChange: (tab: PolicyTabKey) => void;
  pendingCount?: number;
  versionCount?: number;
};

const TAB_ITEMS: Array<{ key: PolicyTabKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "live", label: "Live Chain" },
  { key: "proposals", label: "Proposals" },
  { key: "versions", label: "Versions" },
  { key: "tools", label: "Tools" },
  { key: "migration", label: "Migration" },
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
          const badge =
            item.key === "proposals" && pendingCount
              ? pendingCount
              : item.key === "versions" && versionCount
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
