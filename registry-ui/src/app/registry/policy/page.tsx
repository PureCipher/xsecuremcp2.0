import Link from "next/link";
import {
  getPolicyManagement,
  getRegistrySession,
  requirePolicyRole,
} from "@/lib/registryClient";
import { PolicyManager } from "./PolicyManager";

export default async function PolicyPage() {
  const { allowed } = await requirePolicyRole();
  const sessionPayload = await getRegistrySession();
  const username = sessionPayload?.session?.username ?? null;

  if (!allowed) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-xl font-semibold text-[--app-fg]">Policy management</h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            Reviewer or admin role required to manage live SecureMCP policies.
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

  const policyData = await getPolicyManagement();

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Policy management
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">
            Propose, review, and apply SecureMCP rules
          </h1>
          <p className="max-w-2xl text-[11px] text-[--app-muted]">
            Draft changes first, run a quick simulation, approve them before they go live,
            and keep every draft tied to the live policy version it came from.
          </p>
        </header>

        <PolicyManager
          initialData={policyData ?? {}}
          currentUsername={username}
        />
    </div>
  );
}
