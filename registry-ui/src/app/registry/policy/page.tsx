import Link from "next/link";
import { getPolicyManagement, requirePolicyRole } from "@/lib/registryClient";
import { PolicyManager } from "./PolicyManager";

export default async function PolicyPage() {
  const { allowed } = await requirePolicyRole();

  if (!allowed) {
    return (
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">Policy management</h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Reviewer or admin role required to manage live SecureMCP policies.
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

  const policyData = await getPolicyManagement();

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Policy management
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">
            Manage SecureMCP access rules
          </h1>
          <p className="max-w-2xl text-[11px] text-emerald-100/80">
            Update the live policy chain, keep a clean version history, and roll back quickly
            when a rule change needs to be reverted.
          </p>
        </header>

        <PolicyManager initialData={policyData ?? {}} />
      </div>
    </main>
  );
}
