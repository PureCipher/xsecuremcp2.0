"use client";

import { Tab, Tabs } from "@mui/material";

export function TabBar({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: { key: string; label: string }[];
  activeTab: string;
  onTabChange: (key: string) => void;
}) {
  return (
    <Tabs
      value={activeTab}
      onChange={(_, v: string) => onTabChange(v)}
      variant="scrollable"
      scrollButtons="auto"
      sx={{
        minHeight: 44,
        borderBottom: "1px solid var(--app-border)",
        "& .MuiTabs-indicator": { bgcolor: "var(--app-accent)" },
        "& .MuiTab-root": {
          minHeight: 44,
          textTransform: "none",
          fontSize: 12,
          fontWeight: 700,
          color: "var(--app-muted)",
        },
        "& .MuiTab-root.Mui-selected": { color: "var(--app-fg)" },
      }}
    >
      {tabs.map((tab) => (
        <Tab key={tab.key} value={tab.key} label={tab.label} />
      ))}
    </Tabs>
  );
}
