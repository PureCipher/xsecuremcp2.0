import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getRegistrySession } from "@/lib/registryClient";
import { RegistryTopBar } from "./topbar";

export default async function RegistryLayout({ children }: { children: ReactNode }) {
  const sessionPayload = await getRegistrySession();
  const hasSession = sessionPayload?.session != null;

  if (!hasSession) {
    redirect("/login");
  }

  const username: string = sessionPayload.session?.username ?? "account";

  return (
    <div className="min-h-screen bg-emerald-950/95 text-sm text-emerald-50">
      <RegistryTopBar username={username} />
      {children}
    </div>
  );
}

