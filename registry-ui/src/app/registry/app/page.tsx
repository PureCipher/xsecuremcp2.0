import Link from "next/link";
import { redirect } from "next/navigation";
import { Box, Button } from "@mui/material";
import {
  getReviewQueue,
  getRegistrySession,
  listVerifiedTools,
  sessionMayUsePublishConsole,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { RegistryPageHeader } from "@/components/security";
import { ToolsCatalog } from "./ToolsCatalog";

export default async function RegistryAppPage() {
  const sessionPayload = await getRegistrySession();
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const role = sessionPayload?.session?.role ?? null;
  const canReview = authEnabled ? (sessionPayload?.session?.can_review ?? false) : true;
  const canPublishConsole = sessionMayUsePublishConsole(authEnabled, role);
  const canAdmin = authEnabled ? (sessionPayload?.session?.can_admin ?? false) : true;

  if (canPublishConsole && !canReview && !canAdmin) {
    redirect("/registry/publish/mine");
  }
  if (canReview && !canPublishConsole && !canAdmin) {
    redirect("/registry/review");
  }

  const queue = canReview ? (await getReviewQueue()) ?? {} : {};
  const pendingCount = queue.counts?.pending_review ?? 0;

  const catalog = (await listVerifiedTools()) ?? { tools: [], count: 0 };
  const tools: RegistryToolListing[] = catalog.tools ?? [];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="PureCipher Secured MCP Registry"
        title="Trusted tool directory"
        description="Search trusted MCP tools, review certification levels, and open listings for install recipes."
        actions={
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          {canPublishConsole || (!canReview && !authEnabled) ? (
            <Link href="/registry/publish/get-started"><Button variant="outlined" sx={{ borderColor: "var(--app-control-border)", color: "var(--app-muted)" }}>
                Publisher onboarding
              </Button></Link>
          ) : null}
          <Link href="/registry/publishers"><Button variant="contained">
              Browse publishers
            </Button></Link>
          </Box>
        }
      />

      <ToolsCatalog
        tools={tools}
        publishHref={canPublishConsole ? "/registry/publish" : undefined}
        reviewHref={canReview ? "/registry/review" : undefined}
        publishersHref="/registry/publishers"
        pendingCount={pendingCount}
      />
    </Box>
  );
}
