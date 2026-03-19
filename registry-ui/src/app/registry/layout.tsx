import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getRegistrySession } from "@/lib/registryClient";
import { RegistryShell } from "./RegistryShell";

export default async function RegistryLayout({ children }: { children: ReactNode }) {
  const sessionPayload = await getRegistrySession();
  const hasSession = sessionPayload?.session != null;

  if (!hasSession) {
    redirect("/login");
  }

  const canSubmit: boolean = sessionPayload.session?.can_submit ?? false;
  const canReview: boolean = sessionPayload.session?.can_review ?? false;
  const canAdmin: boolean = sessionPayload.session?.can_admin ?? false;

  return (
    <RegistryShell canSubmit={canSubmit} canReview={canReview} canAdmin={canAdmin}>
      {children}
    </RegistryShell>
  );
}
