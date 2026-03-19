import Link from "next/link";
import { requirePublisherRole } from "@/lib/registryClient";
import { PublisherForm } from "./PublisherForm";

export default async function PublishPage() {
  const { allowed } = await requirePublisherRole();

  if (!allowed) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-xl font-semibold text-[--app-fg]">Share a tool</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            Publisher, reviewer, or admin role required to publish listings into the registry.
          </p>
          <p className="mt-4">
            <Link
              href="/registry/app"
              className="text-[11px] font-medium text-[--app-muted] hover:text-[--app-fg]"
            >
              ← Back to tools
            </Link>
          </p>
      </div>
    );
  }

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
        <PublisherForm />
    </div>
  );
}
