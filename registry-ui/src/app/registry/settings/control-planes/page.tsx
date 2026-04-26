import { redirect } from "next/navigation";

import { Box } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import {
  getControlPlaneStatus,
  getRegistrySession,
} from "@/lib/registryClient";
import { ControlPlanesPanel } from "./ControlPlanesPanel";

export const dynamic = "force-dynamic";

export default async function ControlPlanesSettingsPage() {
  const [statusPayload, sessionPayload] = await Promise.all([
    getControlPlaneStatus(),
    getRegistrySession(),
  ]);

  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  const isAdmin = authEnabled ? (session?.can_admin ?? false) : true;

  // Admin-only. Send non-admins back to the main settings page so
  // they get a clean redirect rather than a confusing empty card.
  if (!isAdmin) {
    redirect("/registry/settings");
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Admin · Control planes"
        title="Runtime SecureMCP control-plane toggles"
        description="Enable or disable each opt-in plane on this registry. Toggles take effect immediately, persist across restart, and are recorded in the admin audit log."
      />

      <ControlPlanesPanel initialStatus={statusPayload ?? null} />
    </Box>
  );
}
