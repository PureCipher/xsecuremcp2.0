import { redirect } from "next/navigation";

import { Box, Typography } from "@mui/material";

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
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Inter-Agent Contracts
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Negotiate, sign, and verify digital contracts
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
          Manage mutual agreements between agents and servers with cryptographic signing, hash-chain integrity verification,
          and immutable exchange logs.
        </Typography>
      </Box>

      <ContractsManager initialContracts={contractsData} initialExchangeLog={exchangeData} />
    </Box>
  );
}
