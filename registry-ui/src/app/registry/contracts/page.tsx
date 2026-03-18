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
      <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
        <div className="mx-auto max-w-3xl rounded-3xl bg-emerald-900/40 p-6 ring-1 ring-emerald-700/60">
          <h1 className="text-xl font-semibold text-emerald-50">
            Inter-Agent Digital Contracts
          </h1>
          <p className="mt-2 text-[12px] text-emerald-100/90">
            Admin role required to manage contracts.
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

  const contractsData = await listContracts();
  const exchangeData = await getExchangeLog();

  return (
    <main className="min-h-screen bg-emerald-950/95 px-4 py-10 text-sm text-emerald-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
            Inter-Agent Contracts
          </p>
          <h1 className="text-2xl font-semibold text-emerald-50">
            Negotiate, sign, and verify digital contracts
          </h1>
          <p className="max-w-2xl text-[11px] text-emerald-100/80">
            Manage mutual agreements between agents and servers with cryptographic signing,
            hash-chain integrity verification, and immutable exchange logs.
          </p>
        </header>
        <ContractsManager
          initialContracts={contractsData}
          initialExchangeLog={exchangeData}
        />
      </div>
    </main>
  );
}
