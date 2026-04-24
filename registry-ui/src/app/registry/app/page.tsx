import Link from "next/link";
import { redirect } from "next/navigation";
import { Box, Button, Card, CardContent, Typography } from "@mui/material";
import {
  getReviewQueue,
  getRegistrySession,
  listVerifiedTools,
  sessionMayUsePublishConsole,
  type RegistryToolListing,
} from "@/lib/registryClient";
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
      <Box
        component="header"
        sx={{
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          gap: 2,
          alignItems: { sm: "flex-end" },
          justifyContent: "space-between",
        }}
      >
        <Box>
          <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            PureCipher Secured MCP Registry
          </Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 700, color: "var(--app-fg)" }}>
            Trusted tool directory
          </Typography>
          <Typography sx={{ mt: 1, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
            Search trusted MCP tools, review certification levels, and open listings for install recipes.
          </Typography>
        </Box>

        <Box sx={{ display: "grid", gap: 0.5, alignItems: "end", justifyItems: { xs: "start", sm: "end" } }}>
          {canPublishConsole || (!canReview && !authEnabled) ? (
            <Link href="/registry/publish/get-started" legacyBehavior passHref>
              <Button
                component="a"
                variant="text"
                sx={{ color: "var(--app-muted)", justifySelf: { xs: "start", sm: "end" } }}
              >
                Publisher onboarding →
              </Button>
            </Link>
          ) : null}
          <Link href="/registry/publishers" legacyBehavior passHref>
            <Button
              component="a"
              variant="text"
              sx={{ color: "var(--app-muted)", justifySelf: { xs: "start", sm: "end" } }}
            >
              Browse publishers →
            </Button>
          </Link>
        </Box>
      </Box>

      {canPublishConsole || canReview ? (
        <Card
          variant="outlined"
          sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}
        >
          <CardContent
            sx={{
              p: 2.5,
              display: "flex",
              flexDirection: { xs: "column", sm: "row" },
              gap: 2,
              alignItems: { sm: "center" },
              justifyContent: "space-between",
            }}
          >
            <Box>
              <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Quick actions
              </Typography>
              <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
                Shortcuts based on your role: publish submissions or moderate the queue.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              {canPublishConsole ? (
                <Link href="/registry/publish/mine" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="outlined"
                    sx={{
                      borderRadius: 999,
                      borderColor: "var(--app-control-border)",
                      color: "var(--app-muted)",
                      bgcolor: "var(--app-control-bg)",
                      "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
                    }}
                  >
                    My listings
                  </Button>
                </Link>
              ) : null}
              {canPublishConsole ? (
                <Link href="/registry/publish" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="contained"
                    sx={{
                      borderRadius: 999,
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      "&:hover": { bgcolor: "var(--app-accent)" },
                    }}
                  >
                    Publish a tool
                  </Button>
                </Link>
              ) : null}
              {canPublishConsole ? (
                <Link href="/registry/publish/get-started" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="outlined"
                    sx={{
                      borderRadius: 999,
                      borderColor: "var(--app-accent)",
                      color: "var(--app-muted)",
                      "&:hover": { bgcolor: "var(--app-control-active-bg)", borderColor: "var(--app-accent)" },
                    }}
                  >
                    Get started
                  </Button>
                </Link>
              ) : null}
              {canReview ? (
                <Link href="/registry/review" legacyBehavior passHref>
                  <Button
                    component="a"
                    variant="outlined"
                    sx={{
                      borderRadius: 999,
                      borderColor: "var(--app-accent)",
                      color: "var(--app-muted)",
                      "&:hover": { bgcolor: "var(--app-control-active-bg)", borderColor: "var(--app-accent)" },
                    }}
                  >
                    Review queue{pendingCount ? ` (${pendingCount} pending)` : ""}
                  </Button>
                </Link>
              ) : null}
            </Box>
          </CardContent>
        </Card>
      ) : null}

      <Card
        variant="outlined"
        sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}
      >
        <CardContent sx={{ p: 2.5 }}>
          {tools.length === 0 ? (
            <Typography sx={{ color: "var(--app-muted)" }}>
              No verified tools are published yet. Once tools are in the registry they&apos;ll appear here.
            </Typography>
          ) : (
            <ToolsCatalog tools={tools} />
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
