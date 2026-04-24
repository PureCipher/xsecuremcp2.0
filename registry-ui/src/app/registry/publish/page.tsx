import { redirect } from "next/navigation";

import { getMyListings, requirePublisherRole } from "@/lib/registryClient";
import { PublisherForm } from "./PublisherForm";

export default async function PublishPage(props: { searchParams?: Promise<Record<string, string | string[]>> }) {
  const { allowed } = await requirePublisherRole();

  if (!allowed) {
    redirect("/registry/app");
  }

  const sp = (await props.searchParams) ?? {};
  const from = typeof sp.from === "string" ? sp.from : Array.isArray(sp.from) ? sp.from[0] : "";
  const publishMode =
    typeof sp.publish_mode === "string"
      ? sp.publish_mode
      : Array.isArray(sp.publish_mode)
        ? sp.publish_mode[0]
        : "";
  const serverType =
    typeof sp.server_type === "string"
      ? sp.server_type
      : Array.isArray(sp.server_type)
        ? sp.server_type[0]
        : "";
  const mine = (await getMyListings()) ?? {};
  const tools = Array.isArray(mine.tools) ? mine.tools : [];
  if (!from && tools.length === 0) {
    redirect("/registry/publish/get-started");
  }
  const selected = from ? tools.find((t) => String(t?.listing_id ?? "") === from) : null;

  const initialManifestText = selected?.manifest ? JSON.stringify(selected.manifest, null, 2) : undefined;
  const selectedRuntimeText = selected?.metadata ? JSON.stringify(selected.metadata, null, 2) : undefined;
  const initialRuntimeText = (() => {
    if (selectedRuntimeText) return selectedRuntimeText;
    if (publishMode !== "external") return undefined;
    const st = serverType === "mcp" ? "mcp" : "securemcp";
    return JSON.stringify(
      {
        server_type: st,
        transport: "streamable-http",
        endpoint: "",
      },
      null,
      2,
    );
  })();
  const initialDisplayName = typeof selected?.display_name === "string" ? selected.display_name : undefined;
  const initialCategories = Array.isArray(selected?.categories)
    ? selected.categories.join(",")
    : undefined;

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Publisher console
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">Share your tool</h1>
          <p className="max-w-xl text-[11px] text-[--app-muted]">
            Describe your tool, paste its manifest, and let the registry run SecureMCP guardrails before you
            publish.
          </p>
        </header>
        <PublisherForm
          initialDisplayName={initialDisplayName}
          initialCategories={initialCategories}
          initialManifestText={initialManifestText}
          initialRuntimeText={initialRuntimeText}
        />
    </div>
  );
}
