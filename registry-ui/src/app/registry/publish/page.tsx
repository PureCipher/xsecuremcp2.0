import Link from "next/link";
import { requirePublisherRole } from "@/lib/registryClient";
import { PublisherForm } from "./PublisherForm";

export default async function PublishPage() {
  const { allowed } = await requirePublisherRole();

  if (!allowed) {
    return (
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">Share a tool</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Publisher, reviewer, or admin role required to publish listings into the registry.
          </p>
          <p className="mt-4">
            <Link
              href="/registry/app"
              className="text-[11px] font-medium text-emerald-200 hover:text-emerald-100"
            >
              ← Back to tools
            </Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Publisher console
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">Share your tool</h1>
          <p className="max-w-xl text-[11px] text-emerald-100/80">
            Describe your tool, paste its manifest, and let the registry run SecureMCP guardrails before you
            publish.
          </p>
        </header>
        <PublisherForm />
      </div>
    </main>
  );
}
