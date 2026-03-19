"use client";

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
    <div className="flex gap-1 border-b border-[--app-border] pb-px">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onTabChange(tab.key)}
          className={`rounded-t-lg px-3 py-2 text-[11px] font-medium transition ${
            activeTab === tab.key
              ? "border-b-2 border-[--app-accent] text-[--app-fg]"
              : "text-[--app-muted] hover:text-[--app-fg]"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
