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
    <div className="flex gap-1 border-b border-emerald-700/50 pb-px">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onTabChange(tab.key)}
          className={`rounded-t-lg px-3 py-2 text-[11px] font-medium transition ${
            activeTab === tab.key
              ? "border-b-2 border-emerald-400 text-emerald-50"
              : "text-emerald-300/70 hover:text-emerald-200"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
