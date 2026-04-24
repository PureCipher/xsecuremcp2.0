"use client";

import dynamic from "next/dynamic";
import { Typography } from "@mui/material";

const CliDeveloperWorkspace = dynamic(
  () => import("./CliDeveloperWorkspace").then((m) => m.CliDeveloperWorkspace),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[480px] items-center justify-center border border-[--app-border] bg-[--app-control-bg] ring-1 ring-[--app-surface-ring]">
        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
          Loading developer workspace…
        </Typography>
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
