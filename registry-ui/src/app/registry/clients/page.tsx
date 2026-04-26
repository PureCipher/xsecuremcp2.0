import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";
import {
  listRegistryClients,
  type RegistryClientSummary,
} from "@/lib/registryClient";
import { ClientsDirectory } from "./ClientsDirectory";

export default async function ClientsPage() {
  const payload = (await listRegistryClients()) ?? {
    items: [],
    count: 0,
    kinds: [],
  };
  const clients: RegistryClientSummary[] = payload.items ?? [];
  const errorMessage =
    typeof payload.error === "string" && payload.error ? payload.error : null;
  const accessDenied = payload.status === 401 || payload.status === 403;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Clients"
        title="Onboard and bind clients"
        description="Register MCP client identities (agents, services, frameworks) and issue API tokens that flow through every governance plane as the request actor."
      />

      <ClientsDirectory
        clients={clients}
        kinds={payload.kinds ?? []}
        onboardHref="/registry/clients/onboard"
        serversHref="/registry/servers"
        errorMessage={errorMessage}
        accessDenied={accessDenied}
      />
    </Box>
  );
}
