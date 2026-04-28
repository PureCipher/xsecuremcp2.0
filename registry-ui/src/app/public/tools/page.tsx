import Link from "next/link";
import SearchIcon from "@mui/icons-material/Search";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import VerifiedOutlinedIcon from "@mui/icons-material/VerifiedOutlined";
import ChecklistOutlinedIcon from "@mui/icons-material/ChecklistOutlined";
import ArrowOutwardIcon from "@mui/icons-material/ArrowOutward";
import BoltOutlinedIcon from "@mui/icons-material/BoltOutlined";
import { Box, Button, Card, CardContent, Typography } from "@mui/material";

import {
  getRegistryHealth,
  listPublishers,
  listVerifiedTools,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";
import { ToolsCatalog } from "@/app/registry/app/ToolsCatalog";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

export default async function PublicToolsPage(props: {
  searchParams?: Promise<SearchParams>;
}) {
  const sp = (await props.searchParams) ?? {};
  const initialQuery = getStringParam(sp.q);

  const [catalog, publisherDirectory, health] = await Promise.all([
    listVerifiedTools(),
    listPublishers(),
    getRegistryHealth(),
  ]);

  const tools: RegistryToolListing[] = catalog?.tools ?? [];
  const publishers: PublisherSummary[] = publisherDirectory?.publishers ?? [];
  const verifiedCount = health?.verified_tools ?? catalog?.count ?? tools.length;
  const publisherCount = publisherDirectory?.count ?? publishers.length;
  const categoryCount = countCategories(tools);
  const minimumCertification = formatMinimumCertification(health?.minimum_certification);

  return (
    <Box sx={{ display: "grid", gap: 3 }}>
      <Card
        variant="outlined"
        sx={{
          borderRadius: 4,
          borderColor: "var(--app-border)",
          bgcolor: "var(--app-surface)",
          boxShadow: "none",
        }}
      >
        <CardContent
          sx={{
            p: { xs: 3, sm: 4 },
            display: "grid",
            gap: 2.5,
            gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1.3fr) minmax(280px, 340px)" },
            alignItems: "start",
          }}
        >
          <Box sx={{ display: "grid", gap: 2 }}>
            <Box sx={{ display: "grid", gap: 0.75 }}>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Tool directory
              </Typography>
              <Typography
                variant="h3"
                sx={{
                  fontWeight: 850,
                  letterSpacing: "-0.04em",
                  lineHeight: 1.02,
                  color: "var(--app-fg)",
                }}
              >
                {tools.length > 0
                  ? "Browse verified tools without digging through noise."
                  : "The trusted catalog is ready for real tools."}
              </Typography>
              <Typography sx={{ maxWidth: 760, fontSize: 14, lineHeight: 1.75, color: "var(--app-muted)" }}>
                {tools.length > 0
                  ? "Compare listings, filter by category, and open any tool to inspect certification, publisher context, and install instructions."
                  : "This is where verified tools will appear after publishers submit them and reviewers approve them. Until then, you can start from the publisher directory or sign in to publish."}
              </Typography>
            </Box>

            {initialQuery || tools.length === 0 ? (
              <Box
                component="form"
                action="/public/tools"
                method="GET"
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) auto" },
                  gap: 1,
                  alignItems: "center",
                  borderRadius: 3,
                  border: "1px solid var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                  p: 1,
                  maxWidth: 820,
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, px: { xs: 1, sm: 1.5 } }}>
                  <SearchIcon sx={{ fontSize: 20, color: "var(--app-muted)" }} />
                  <Box
                    component="input"
                    type="search"
                    name="q"
                    aria-label="Search tools"
                    defaultValue={initialQuery}
                    placeholder="Search by tool name, capability, or publisher"
                    sx={{
                      flex: 1,
                      minWidth: 0,
                      border: 0,
                      outline: 0,
                      bgcolor: "transparent",
                      fontSize: 15,
                      fontFamily: "inherit",
                      color: "var(--app-fg)",
                      py: 1.15,
                      "&::placeholder": { color: "var(--app-muted)" },
                    }}
                  />
                </Box>

                <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 1 }}>
                  <Button
                    type="submit"
                    variant="contained"
                    sx={{
                      borderRadius: 2.5,
                      px: 2.5,
                      fontWeight: 800,
                      bgcolor: "var(--app-accent)",
                      color: "white",
                      boxShadow: "none",
                      "&:hover": {
                        bgcolor: "var(--app-accent)",
                        filter: "brightness(0.95)",
                        boxShadow: "none",
                      },
                    }}
                  >
                    Search tools
                  </Button>
                  {initialQuery ? (
                    <Link href="/public/tools" style={{ textDecoration: "none" }}>
                      <Button
                        variant="outlined"
                        sx={{
                          width: { xs: "100%", sm: "auto" },
                          borderRadius: 2.5,
                          borderColor: "var(--app-border)",
                          color: "var(--app-fg)",
                        }}
                      >
                        Clear search
                      </Button>
                    </Link>
                  ) : null}
                </Box>
              </Box>
            ) : null}

            {initialQuery ? (
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Showing catalog results for <strong>{initialQuery}</strong>.
              </Typography>
            ) : null}
          </Box>

          <Box sx={{ display: "grid", gap: 1.5 }}>
            <Box
              sx={{
                display: "grid",
                gap: 1.25,
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              }}
            >
              <SnapshotStat label="Verified" value={String(verifiedCount)} />
              <SnapshotStat label="Publishers" value={String(publisherCount)} />
              <SnapshotStat label="Categories" value={String(categoryCount)} />
            </Box>

            <Box
              sx={{
                p: 2,
                borderRadius: 3,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                display: "grid",
                gap: 0.75,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <VerifiedOutlinedIcon sx={{ fontSize: 18, color: "var(--app-accent)" }} />
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                  Trust baseline
                </Typography>
              </Box>
              <Typography sx={{ fontSize: 12, lineHeight: 1.7, color: "var(--app-muted)" }}>
                Minimum review tier: <strong>{minimumCertification}</strong>. Listings surface certification,
                publisher details, and install guidance together.
              </Typography>
            </Box>

            <Box sx={{ display: "grid", gap: 1 }}>
              <Link href="/public/publishers" style={{ textDecoration: "none" }}>
                <Button
                  fullWidth
                  variant="contained"
                  sx={{
                    borderRadius: 2.5,
                    fontWeight: 800,
                    bgcolor: "var(--app-accent)",
                    color: "white",
                    boxShadow: "none",
                    "&:hover": {
                      bgcolor: "var(--app-accent)",
                      filter: "brightness(0.95)",
                      boxShadow: "none",
                    },
                  }}
                >
                  Browse publishers
                </Button>
              </Link>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                <Link href="/public" style={{ textDecoration: "none", flex: 1 }}>
                  <Button
                    fullWidth
                    variant="outlined"
                    sx={{
                      borderRadius: 2.5,
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                      fontWeight: 700,
                    }}
                  >
                    Public home
                  </Button>
                </Link>
                <Link href="/login" style={{ textDecoration: "none", flex: 1 }}>
                  <Button
                    fullWidth
                    variant="outlined"
                    sx={{
                      borderRadius: 2.5,
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                      fontWeight: 700,
                    }}
                  >
                    Sign in
                  </Button>
                </Link>
              </Box>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {tools.length > 0 ? (
        <ToolsCatalog
          key={`public-tools:${initialQuery}`}
          tools={tools}
          basePath="/public/listings"
          publishersHref="/public/publishers"
          publicView
          initialQuery={initialQuery}
          hideSummary
        />
      ) : (
        <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.25fr) minmax(320px, 380px)" } }}>
          <Card
            variant="outlined"
            sx={{
              borderRadius: 4,
              borderColor: "var(--app-border)",
              bgcolor: "var(--app-surface)",
              boxShadow: "none",
            }}
          >
            <CardContent sx={{ p: { xs: 3, sm: 4 }, display: "grid", gap: 2.5 }}>
              <Box sx={{ display: "grid", gap: 0.75 }}>
                <Typography
                  sx={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  Empty for a reason
                </Typography>
                <Typography sx={{ fontSize: 24, fontWeight: 800, color: "var(--app-fg)" }}>
                  No verified tools yet
                </Typography>
                <Typography sx={{ maxWidth: 760, fontSize: 13, lineHeight: 1.75, color: "var(--app-muted)" }}>
                  The catalog stays empty until a publisher submits a real tool and the review flow clears it for public use.
                  That keeps this directory quiet, but trustworthy.
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "grid",
                  gap: 1.25,
                  gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
                }}
              >
                <JourneyStep
                  step="01"
                  title="Publishers submit"
                  body="A tool enters through manifest preflight and publisher metadata."
                />
                <JourneyStep
                  step="02"
                  title="Reviewers approve"
                  body="Registry review decides whether the listing is ready for public trust."
                />
                <JourneyStep
                  step="03"
                  title="Directory updates"
                  body="Approved tools appear here with their trust signals and install recipes."
                />
              </Box>
            </CardContent>
          </Card>

          <Card
            variant="outlined"
            sx={{
              borderRadius: 4,
              borderColor: "var(--app-border)",
              bgcolor: "var(--app-surface)",
              boxShadow: "none",
            }}
          >
            <CardContent sx={{ p: { xs: 3, sm: 3.5 }, display: "grid", gap: 1.5 }}>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Best next step
              </Typography>
              <Typography sx={{ fontSize: 22, fontWeight: 800, color: "var(--app-fg)" }}>
                Start from the publisher side.
              </Typography>
              <Typography sx={{ fontSize: 13, lineHeight: 1.75, color: "var(--app-muted)" }}>
                Browse the publishers already connected to this registry, or sign in if you are preparing the first submission.
              </Typography>

              <Box sx={{ display: "grid", gap: 1 }}>
                <ActionTile
                  href="/public/publishers"
                  icon={<ApartmentOutlinedIcon sx={{ fontSize: 18 }} />}
                  title="Browse publishers"
                  body="See who is already set up to publish into this registry."
                />
                <ActionTile
                  href="/login"
                  icon={<BoltOutlinedIcon sx={{ fontSize: 18 }} />}
                  title="Sign in to publish"
                  body="Move into the console when you are ready to submit a tool."
                />
              </Box>
            </CardContent>
          </Card>

          <Card
            variant="outlined"
            sx={{
              gridColumn: { xl: "1 / -1" },
              borderRadius: 4,
              borderColor: "var(--app-border)",
              bgcolor: "var(--app-surface)",
              boxShadow: "none",
            }}
          >
            <CardContent sx={{ p: { xs: 3, sm: 4 }, display: "grid", gap: 2 }}>
              <Box sx={{ display: "grid", gap: 0.5 }}>
                <Typography
                  sx={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  What every listing shows
                </Typography>
                <Typography sx={{ fontSize: 22, fontWeight: 800, color: "var(--app-fg)" }}>
                  The page stays simple because the checks are always in the same place.
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "grid",
                  gap: 1.5,
                  gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
                }}
              >
                <InspectionCard
                  icon={<VerifiedOutlinedIcon sx={{ fontSize: 18 }} />}
                  title="Certification tier"
                  body="You can tell how much review a tool has received before you open it."
                />
                <InspectionCard
                  icon={<ApartmentOutlinedIcon sx={{ fontSize: 18 }} />}
                  title="Publisher context"
                  body="Every listing links back to the team or person behind the tool."
                />
                <InspectionCard
                  icon={<ChecklistOutlinedIcon sx={{ fontSize: 18 }} />}
                  title="Install guidance"
                  body="The detail page bundles install recipes with the trust signals that matter."
                />
              </Box>
            </CardContent>
          </Card>
        </Box>
      )}
    </Box>
  );
}

function getStringParam(value: string | string[] | undefined): string {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return String(value[0] ?? "").trim();
  return "";
}

function countCategories(tools: RegistryToolListing[]): number {
  const categories = new Set<string>();
  for (const tool of tools) {
    if (!Array.isArray(tool.categories)) continue;
    for (const category of tool.categories) {
      const trimmed = String(category ?? "").trim();
      if (trimmed) categories.add(trimmed);
    }
  }
  return categories.size;
}

function formatMinimumCertification(level: string | undefined): string {
  if (!level) return "Registry policy";
  return level
    .split(/[_-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function SnapshotStat({ label, value }: { label: string; value: string }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2.5,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 0.35,
      }}
    >
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        {label}
      </Typography>
      <Typography sx={{ fontSize: { xs: 22, sm: 24 }, fontWeight: 800, color: "var(--app-fg)" }}>
        {value}
      </Typography>
    </Box>
  );
}

function JourneyStep({
  step,
  title,
  body,
}: {
  step: string;
  title: string;
  body: string;
}) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 0.75,
      }}
    >
      <Typography
        sx={{
          fontSize: 11,
          fontWeight: 800,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        Step {step}
      </Typography>
      <Typography sx={{ fontSize: 16, fontWeight: 800, color: "var(--app-fg)" }}>
        {title}
      </Typography>
      <Typography sx={{ fontSize: 12.5, lineHeight: 1.7, color: "var(--app-muted)" }}>
        {body}
      </Typography>
    </Box>
  );
}

function ActionTile({
  href,
  icon,
  title,
  body,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Box
        sx={{
          p: 2,
          borderRadius: 3,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
          display: "grid",
          gap: 0.75,
          transition: "border-color 0.15s ease, background-color 0.15s ease",
          "&:hover": {
            borderColor: "var(--app-accent)",
            bgcolor: "var(--app-surface)",
          },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
          <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1, color: "var(--app-accent)" }}>
            {icon}
            <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
              {title}
            </Typography>
          </Box>
          <ArrowOutwardIcon sx={{ fontSize: 16, color: "var(--app-muted)" }} />
        </Box>
        <Typography sx={{ fontSize: 12.5, lineHeight: 1.65, color: "var(--app-muted)" }}>
          {body}
        </Typography>
      </Box>
    </Link>
  );
}

function InspectionCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <Box
      sx={{
        p: 2.5,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 1,
      }}
    >
      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1, color: "var(--app-accent)" }}>
        {icon}
        <Typography sx={{ fontSize: 14, fontWeight: 700, color: "var(--app-fg)" }}>
          {title}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: 12.5, lineHeight: 1.7, color: "var(--app-muted)" }}>
        {body}
      </Typography>
    </Box>
  );
}
