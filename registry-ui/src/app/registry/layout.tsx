import type { ReactNode } from "react";
import { getMyListings, getRegistrySession, sessionMayUsePublishConsole } from "@/lib/registryClient";
import { registryPersonaFromSession } from "@/lib/registryPersona";
import { RegistryShell } from "./RegistryShell";

export default async function RegistryLayout({ children }: { children: ReactNode }) {
  const sessionPayload = await getRegistrySession();
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  const hasSession = !authEnabled || session != null;

  // When registry JWT auth is off, the backend exposes APIs without a session cookie.
  // Treat that as a full local-dev surface so the Next console stays usable.
  const canSubmit = authEnabled ? (session?.can_submit ?? false) : true;
  const canReview = authEnabled ? (session?.can_review ?? false) : true;
  const canAdmin = authEnabled ? (session?.can_admin ?? false) : true;
  const canPublishConsole = sessionMayUsePublishConsole(authEnabled, session?.role);
  const publisherHasListings = await (async () => {
    if (!canPublishConsole) return false;
    const mine = (await getMyListings()) ?? {};
    const count =
      typeof mine.count === "number"
        ? mine.count
        : Array.isArray(mine.tools)
          ? mine.tools.length
          : 0;
    return count > 0;
  })();
  const persona = registryPersonaFromSession(authEnabled, session?.role);

  return (
    <RegistryShell
      authEnabled={authEnabled}
      hasSession={hasSession}
      persona={persona}
      canSubmit={canSubmit}
      canReview={canReview}
      canAdmin={canAdmin}
      canPublishConsole={canPublishConsole}
      publisherHasListings={publisherHasListings}
    >
      {children}
    </RegistryShell>
  );
}
