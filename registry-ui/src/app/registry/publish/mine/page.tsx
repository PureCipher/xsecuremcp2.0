import { redirect } from "next/navigation";
import Link from "next/link";

import { Box, Button, Card, CardActions, CardContent, Chip, Typography } from "@mui/material";

import { RegistryPageHeader } from "@/components/security";
import { getMyListings, getRegistrySession, requirePublisherRole } from "@/lib/registryClient";

type Listing = {
  listing_id?: string;
  tool_name?: string;
  display_name?: string;
  version?: string;
  status?: string;
  certification_level?: string;
  description?: string;
  manifest?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  moderation_log?: { action?: string; moderator_id?: string; reason?: string }[];
};

export default async function MyListingsPage() {
  const sessionPayload = await getRegistrySession();
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  if (authEnabled && session == null) {
    redirect("/login");
  }

  const { allowed } = await requirePublisherRole();
  if (!allowed) {
    redirect("/registry/app");
  }

  const payload = (await getMyListings()) ?? {};
  const tools = (payload.tools ?? []) as Listing[];

  const sorted = [...tools].sort((a, b) => {
    const rank = (s?: string) => {
      if (s === "pending_review") return 0;
      if (s === "draft") return 1;
      if (s === "rejected") return 2;
      if (s === "suspended") return 3;
      if (s === "published") return 4;
      return 9;
    };
    return rank(a.status) - rank(b.status);
  });

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Publisher console"
        title="My listings"
        description="Track your submissions across draft, pending review, and published states."
        actions={
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <Link href="/registry/publish" legacyBehavior passHref>
            <Button
              component="a"
              variant="contained"
              sx={{
                bgcolor: "var(--app-accent)",
                color: "var(--app-accent-contrast)",
                "&:hover": { bgcolor: "var(--app-accent)" },
              }}
            >
              Publish a tool
            </Button>
          </Link>
          <Link href="/registry/publish/get-started" legacyBehavior passHref>
            <Button
              component="a"
              variant="outlined"
              sx={{
                borderColor: "var(--app-control-border)",
                color: "var(--app-muted)",
                bgcolor: "var(--app-control-bg)",
                "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
              }}
            >
              Get started
            </Button>
          </Link>
          </Box>
        }
      />

      <Card variant="outlined">
        <CardContent sx={{ p: 2.5 }}>
          {sorted.length === 0 ? (
            <Box sx={{ display: "grid", gap: 1 }}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>No listings yet.</Typography>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Start by running preflight and publishing your first listing.
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 1.5 }}>
              {sorted.map((item) => (
                <Card key={item.listing_id ?? `${item.tool_name}-${item.version}`} variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                  <CardContent sx={{ pb: 1.5 }}>
                    <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1.5 }}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography noWrap sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                          {item.display_name ?? item.tool_name ?? "Untitled tool"}
                        </Typography>
                        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                          {item.tool_name ?? "unknown"} · v{item.version ?? "?"}
                        </Typography>
                      </Box>
                      <StatusChip status={item.status} />
                    </Box>

                    {item.description ? (
                      <Typography sx={{ mt: 1.5, fontSize: 12, color: "var(--app-muted)" }}>
                        {item.description}
                      </Typography>
                    ) : null}

                    {lastModerationReason(item) ? (
                      <Typography sx={{ mt: 1.5, fontSize: 11, color: "var(--app-muted)" }}>
                        Latest reviewer note:{" "}
                        <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                          {lastModerationReason(item)}
                        </Box>
                      </Typography>
                    ) : null}
                  </CardContent>

                  {item.tool_name ? (
                    <CardActions sx={{ px: 2, pb: 2, pt: 0, display: "flex", gap: 1, flexWrap: "wrap" }}>
                      <Link
                        href={`/registry/listings/${encodeURIComponent(item.tool_name)}`}
                        legacyBehavior
                        passHref
                      >
                        <Button
                          component="a"
                          size="small"
                          variant="outlined"
                          sx={{
                            borderColor: "var(--app-control-border)",
                            color: "var(--app-muted)",
                            bgcolor: "var(--app-control-bg)",
                            "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
                          }}
                        >
                          View listing
                        </Button>
                      </Link>
                      <Link
                        href={`/registry/publish?from=${encodeURIComponent(item.listing_id ?? "")}`}
                        legacyBehavior
                        passHref
                      >
                        <Button
                          component="a"
                          size="small"
                          variant="outlined"
                          sx={{
                            borderColor: "var(--app-accent)",
                            color: "var(--app-muted)",
                            "&:hover": { bgcolor: "var(--app-control-active-bg)", borderColor: "var(--app-accent)" },
                          }}
                        >
                          Publish new version
                        </Button>
                      </Link>
                    </CardActions>
                  ) : null}
                </Card>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

function lastModerationReason(item: Listing): string {
  const log = Array.isArray(item.moderation_log) ? item.moderation_log : [];
  const last = log.length ? log[log.length - 1] : null;
  return (last?.reason ?? "").trim();
}

function StatusChip({ status }: { status?: string }) {
  const s = (status ?? "unknown").toLowerCase();
  const label = s.replace(/_/g, " ");

  const sx =
    s === "pending_review"
      ? { bgcolor: "rgba(245, 158, 11, 0.12)", color: "#92400e" }
      : s === "published"
        ? { bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)" }
        : s === "rejected"
          ? { bgcolor: "rgba(239, 68, 68, 0.12)", color: "#b91c1c" }
          : s === "suspended"
            ? { bgcolor: "rgba(249, 115, 22, 0.12)", color: "#c2410c" }
            : { bgcolor: "var(--app-active-bg)", color: "var(--app-muted)" };

  return (
    <Chip
      label={label}
      size="small"
      sx={{
        ...sx,
        height: 24,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: "0.01em",
      }}
    />
  );
}

