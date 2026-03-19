"use client";

import dynamic from "next/dynamic";

const CliDeveloperWorkspace = dynamic(
  () => import("./CliDeveloperWorkspace").then((m) => m.CliDeveloperWorkspace),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[480px] items-center justify-center border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring] text-[11px] text-[--app-muted]">
        Loading developer workspace…
      </div>
    ),
  },
);

export function CliPageClient({
  defaultMcpUrl,
  allowedOrigin,
}: {
  defaultMcpUrl: string;
  allowedOrigin: string;
}) {
  return <CliDeveloperWorkspace defaultMcpUrl={defaultMcpUrl} allowedOrigin={allowedOrigin} />;
}
