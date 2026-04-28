import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";
import {
  getClientsActivitySummary,
  listRegistryClients,
  type RegistryClientSummary,
} from "@/lib/registryClient";
import { ClientsDirectory } from "./ClientsDirectory";
import { ClientsActivityDashboard } from "./ClientsActivityDashboard";

export default async function ClientsPage() {
  // Iter 14.24 — fetch the directory + activity summary in parallel
  // so first paint includes both. The summary refreshes itself
  // every 30s on the client side.
  const [payload, summary] = await Promise.all([
    listRegistryClients(),
    getClientsActivitySummary(),
  ]);
  const directoryPayload = payload ?? { items: [], count: 0, kinds: [] };
  const clients: RegistryClientSummary[] = directoryPayload.items ?? [];
  const errorMessage =
    typeof directoryPayload.error === "string" && directoryPayload.error
      ? directoryPayload.error
      : null;
  const accessDenied =
    directoryPayload.status === 401 || directoryPayload.status === 403;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Clients"
        title="Onboard and bind clients"
        description="Register MCP client identities (agents, services, frameworks) and issue API tokens that flow through every governance plane as the request actor."
      />

      <ClientsActivityDashboard initialSummary={summary} />

      <ClientsDirectory
        clients={clients}
        kinds={directoryPayload.kinds ?? []}
        onboardHref="/registry/clients/onboard"
        serversHref="/registry/servers"
        errorMessage={errorMessage}
        accessDenied={accessDenied}
      />
    </Box>
  );
}
