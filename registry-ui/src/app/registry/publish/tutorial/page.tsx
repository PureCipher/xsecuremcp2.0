import { redirect } from "next/navigation";

import { getRegistrySession } from "@/lib/registryClient";

export default async function PublisherTutorialPage() {
  // Legacy route: keep for backward compatibility but route users to onboarding.
  const sessionPayload = await getRegistrySession();
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  if (authEnabled && session == null) {
    redirect("/login");
  }
  redirect("/registry/publish/get-started");
}
