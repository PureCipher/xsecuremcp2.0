import Link from "next/link";
import { redirect } from "next/navigation";
import {
  getRegistrySession,
  listVerifiedTools,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { ToolsCatalog } from "./ToolsCatalog";

export default async function RegistryAppPage() {
  const sessionPayload = await getRegistrySession();
  const hasSession = sessionPayload?.session != null;

  if (!hasSession) {
    redirect("/login");
  }

  const catalog = (await listVerifiedTools()) ?? { tools: [], count: 0 };
  const tools: RegistryToolListing[] = catalog.tools ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            PureCipher Secured MCP Registry
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-[--app-fg]">Trusted tool directory</h1>
          <p className="mt-1 max-w-xl text-xs text-[--app-muted]">
            Search trusted MCP tools, review certification levels, and open listings for install recipes.
          </p>
        </div>
        <div className="mt-1 flex flex-col items-start gap-1 text-xs text-[--app-muted] sm:items-end">
          <Link
            href="/registry/publishers"
            className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
          >
            Browse publishers →
          </Link>
        </div>
      </header>

      <section className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
        {tools.length === 0 ? (
          <p className="text-[--app-muted]">
            No verified tools are published yet. Once tools are in the registry they&apos;ll appear here.
          </p>
        ) : (
          <ToolsCatalog tools={tools} />
        )}
      </section>
    </div>
  );
}
