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
    <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring]">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
      >
        <span>{title || "Raw JSON"}</span>
        <span className="text-[--app-accent]">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded ? (
        <pre className="max-h-80 overflow-auto border-t border-[--app-border] px-3 py-2 text-[10px] leading-relaxed text-[--app-fg]">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
