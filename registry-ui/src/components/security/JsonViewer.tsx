"use client";

import { useState } from "react";

export function JsonViewer({
  data,
  title,
  defaultExpanded = false,
}: {
  data: unknown;
  title?: string;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-2xl bg-emerald-950/80 ring-1 ring-emerald-700/40">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-[11px] font-medium text-emerald-300 hover:text-emerald-200"
      >
        <span>{title || "Raw JSON"}</span>
        <span className="text-emerald-500">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded ? (
        <pre className="max-h-80 overflow-auto border-t border-emerald-800/50 px-3 py-2 text-[10px] leading-relaxed text-emerald-100/90">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
