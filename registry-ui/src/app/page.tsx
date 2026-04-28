import { redirect } from "next/navigation";

import { getRegistrySession, getRegistryUserPreferences } from "@/lib/registryClient";
import { resolveRegistryLanding } from "@/lib/registryLanding";

export default async function Home() {
  const sessionPayload = await getRegistrySession();

  if (sessionPayload?.auth_enabled === false) {
    redirect("/registry/app");
  }

  if (sessionPayload?.session != null) {
    const preferencesPayload = await getRegistryUserPreferences();
    redirect(
      resolveRegistryLanding(
        preferencesPayload?.preferences?.workspace?.defaultLandingPage,
        sessionPayload.session.role,
      ),
    );
  }

  redirect("/public");
}
