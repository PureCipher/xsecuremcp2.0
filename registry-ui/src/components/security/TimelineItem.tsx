"use client";

import { StatusBadge } from "./StatusBadge";

export function TimelineItem({
  timestamp,
  title,
  detail,
  status,
}: {
  timestamp: string;
  title: string;
  detail?: string;
  status?: string;
}) {
  const timeStr = (() => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  })();

  return (
    <div className="relative border-l-2 border-[--app-border] py-2 pl-4">
      <div className="absolute -left-[5px] top-3 h-2 w-2 rounded-full bg-[--app-accent]" />
      <div className="flex items-center gap-2">
        <p className="text-[12px] font-medium text-[--app-fg]">{title}</p>
        {status ? <StatusBadge status={status} /> : null}
      </div>
      {detail ? (
        <p className="mt-0.5 text-[11px] text-[--app-muted]">{detail}</p>
      ) : null}
      <p className="mt-0.5 text-[10px] text-[--app-muted]">{timeStr}</p>
    </div>
  );
}
