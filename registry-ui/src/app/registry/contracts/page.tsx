import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import { getExchangeLog, listContracts, requireAdminRole } from "@/lib/registryClient";
import { ContractsManager } from "./ContractsManager";

export default async function ContractsPage() {
  const { allowed } = await requireAdminRole();

  if (!allowed) {
    redirect("/registry/app");
  }

  const contractsData = await listContracts();
  const exchangeData = await getExchangeLog();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Inter-Agent Contracts"
        title="Negotiate, sign, and verify digital contracts"
        description="Manage mutual agreements between agents and servers with cryptographic signing, hash-chain integrity verification, and immutable exchange logs."
      />

      <ContractsManager initialContracts={contractsData} initialExchangeLog={exchangeData} />
    </Box>
  );
}
