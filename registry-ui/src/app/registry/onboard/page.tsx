import { redirect } from "next/navigation";
import { Box } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
import { requirePublisherRole } from "@/lib/registryClient";

import { OnboardWizard } from "./wizard/OnboardWizard";

export default async function OnboardPage(props: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  const sp = (await props.searchParams) ?? {};
  const rawMode = typeof sp.mode === "string" ? sp.mode : Array.isArray(sp.mode) ? sp.mode[0] : "";
  const mode: "author" | "curator" = rawMode === "author" ? "author" : "curator";

  const isAuthor = mode === "author";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow={isAuthor ? "Author onboarding" : "Curator onboarding"}
        title={isAuthor ? "Connect your running MCP server" : "Onboard a third-party MCP server"}
        description={
          isAuthor
            ? "Point the registry at your running MCP server. It will introspect the capabilities, generate a security manifest, and publish an author-attested listing."
            : "Vouch for an existing public MCP server. The registry pins its URL, observes its capability surface, and signs a curator-attested listing. The author of the upstream is unaware of and unaffected by the listing."
        }
      />
      <OnboardWizard mode={mode} />
    </Box>
  );
}
