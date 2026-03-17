"use client";

import type { PolicyTabKey } from "../hooks/useTabNavigation";

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
    <nav className="flex flex-wrap gap-2" aria-label="Policy management tabs">
      {TAB_ITEMS.map((item) => {
        const isActive = activeTab === item.key;
        const badge =
          item.key === "proposals" && pendingCount
            ? pendingCount
            : item.key === "versions" && versionCount
              ? versionCount
              : null;

        return (
          <button
            key={item.key}
            type="button"
            onClick={() => onTabChange(item.key)}
            className={`rounded-full px-4 py-2 text-xs font-semibold transition ${
              isActive
                ? "bg-emerald-500 text-emerald-950"
                : "border border-emerald-700/70 text-emerald-100 hover:bg-emerald-700/20"
            }`}
            aria-selected={isActive}
            role="tab"
          >
            {item.label}
            {badge ? (
              <span
                className={`ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-bold ${
                  isActive
                    ? "bg-emerald-950/30 text-emerald-50"
                    : "bg-emerald-700/40 text-emerald-200"
                }`}
              >
                {badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
