import Link from "next/link";
import {
  getRegistrySession,
  listContracts,
  getExchangeLog,
} from "@/lib/registryClient";
import { ContractsManager } from "./ContractsManager";

export default async function ContractsPage() {
  const sessionPayload = await getRegistrySession();
  const role = sessionPayload?.session?.role ?? null;
  const canAdmin = role === "admin";

  if (!canAdmin) {
    return (
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-6 ring-1 ring-[--app-surface-ring]">
          <h1 className="text-xl font-semibold text-[--app-fg]">
            Inter-Agent Digital Contracts
          </h1>
          <p className="mt-2 text-[12px] text-[--app-muted]">
            Admin role required to manage contracts.
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

  const contractsData = await listContracts();
  const exchangeData = await getExchangeLog();

  return (
    <div className="flex flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Inter-Agent Contracts
          </p>
          <h1 className="text-2xl font-semibold text-[--app-fg]">
            Negotiate, sign, and verify digital contracts
          </h1>
          <p className="max-w-2xl text-[11px] text-[--app-muted]">
            Manage mutual agreements between agents and servers with cryptographic signing,
            hash-chain integrity verification, and immutable exchange logs.
          </p>
        </header>
        <ContractsManager
          initialContracts={contractsData}
          initialExchangeLog={exchangeData}
        />
    </div>
  );
}
