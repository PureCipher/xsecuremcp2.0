import Link from "next/link";
import SearchIcon from "@mui/icons-material/Search";
import VerifiedOutlinedIcon from "@mui/icons-material/VerifiedOutlined";
import { Box, Button, Card, CardContent, Typography } from "@mui/material";

import {
  getRegistryHealth,
  listPublishers,
  listVerifiedTools,
  type PublisherSummary,
  type RegistryToolListing,
} from "@/lib/registryClient";

export const dynamic = "force-dynamic";

const HERO_CATEGORIES: ReadonlyArray<{ label: string; q: string }> = [
  { label: "File system", q: "filesystem" },
  { label: "Database", q: "database" },
  { label: "Network", q: "network" },
  { label: "Auth", q: "auth" },
  { label: "AI", q: "ai" },
  { label: "DevOps", q: "devops" },
  { label: "Documents", q: "document" },
];

export default async function PublicLandingPage() {
  const [catalog, publisherDirectory, health] = await Promise.all([
    listVerifiedTools(),
    listPublishers(),
    getRegistryHealth(),
  ]);

  const tools: RegistryToolListing[] = catalog?.tools ?? [];
  const publishers: PublisherSummary[] = publisherDirectory?.publishers ?? [];
  const featuredTools = tools.slice(0, 3);
  const verifiedCount = health?.verified_tools ?? catalog?.count ?? tools.length;
  const publisherCount = publisherDirectory?.count ?? publishers.length;
  return (
    <Box sx={{ py: { xs: 2, sm: 2.5, md: 3 } }}>
      <Box sx={{ display: "grid", gap: { xs: 3, md: 4 } }}>
        <Card
          variant="outlined"
          sx={{
            borderRadius: 4,
            borderColor: "var(--app-border)",
            bgcolor: "var(--app-surface)",
            boxShadow: "none",
            overflow: "hidden",
          }}
        >
          <CardContent sx={{ p: { xs: 3, sm: 4 }, display: "grid", gap: { xs: 3, md: 3.5 } }}>
            <Box sx={{ display: "grid", gap: 1.5, maxWidth: 840 }}>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.2em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                PureCipher trusted registry
              </Typography>
              <Typography
                variant="h2"
                sx={{
                  fontWeight: 850,
                  letterSpacing: "-0.05em",
                  lineHeight: 1,
                  color: "var(--app-fg)",
                  fontSize: { xs: 38, sm: 48, md: 56, xl: 60 },
                  maxWidth: 760,
                }}
              >
                Find a tool fast. Verify it once. Install with confidence.
              </Typography>
              <Typography
                sx={{
                  fontSize: { xs: 15, sm: 16 },
                  lineHeight: 1.7,
                  color: "var(--app-muted)",
                  maxWidth: 720,
                }}
              >
                {verifiedCount} verified {verifiedCount === 1 ? "tool" : "tools"} from {publisherCount} {publisherCount === 1 ? "publisher" : "publishers"}.
              </Typography>
            </Box>

            <Box
              component="form"
              action="/public/tools"
              method="GET"
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) auto" },
                gap: 1.25,
                alignItems: "center",
                borderRadius: 3,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                p: 1,
                maxWidth: 840,
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  minWidth: 0,
                  px: { xs: 1, sm: 1.5 },
                }}
              >
                <SearchIcon sx={{ fontSize: 20, color: "var(--app-muted)" }} />
                <Box
                  component="input"
                  type="search"
                  name="q"
                  aria-label="Search tools"
                  autoComplete="off"
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
                    py: 1.2,
                    "&::placeholder": { color: "var(--app-muted)" },
                  }}
                />
              </Box>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: { xs: "column", sm: "row" },
                  gap: 1,
                }}
              >
                <Button
                  type="submit"
                  variant="contained"
                  sx={{
                    minWidth: { sm: 130 },
                    borderRadius: 2.5,
                    px: 2.5,
                    py: 1,
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
                  Search catalog
                </Button>
                <Link href="/public/tools" style={{ textDecoration: "none" }}>
                  <Button
                    variant="outlined"
                    sx={{
                      width: { xs: "100%", sm: "auto" },
                      borderRadius: 2.5,
                      px: 2.5,
                      py: 1,
                      fontWeight: 700,
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                      bgcolor: "var(--app-surface)",
                    }}
                  >
                    Browse all tools
                  </Button>
                </Link>
              </Box>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
              {HERO_CATEGORIES.map((category) => (
                <CategoryChip key={category.q} label={category.label} q={category.q} />
              ))}
            </Box>
          </CardContent>
        </Card>

        <Box sx={{ display: "grid", gap: 2 }}>
          <Box
            sx={{
              display: "flex",
              flexDirection: { xs: "column", sm: "row" },
              alignItems: { sm: "flex-end" },
              justifyContent: "space-between",
              gap: 1.5,
            }}
          >
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
                Featured tools
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
                Start with the catalog, not guesswork.
              </Typography>
              <Typography sx={{ fontSize: 13, color: "var(--app-muted)", maxWidth: 780 }}>
                Open a listing to see its description, trust signals, and install recipe in one place.
              </Typography>
            </Box>
            <Link href="/public/tools" style={{ textDecoration: "none" }}>
              <Button variant="text" sx={{ color: "var(--app-accent)", fontWeight: 700, px: 0 }}>
                See every tool
              </Button>
            </Link>
          </Box>

          {featuredTools.length > 0 ? (
            <Box
              sx={{
                display: "grid",
                gap: 2,
                gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
              }}
            >
              {featuredTools.map((tool) => (
                <FeaturedToolCard key={tool.listing_id ?? tool.tool_name} tool={tool} />
              ))}
            </Box>
          ) : (
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
                  gap: 2,
                  gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) auto" },
                  alignItems: "center",
                }}
              >
                <Box sx={{ display: "grid", gap: 0.75 }}>
                  <Typography sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}>
                    The catalog is ready for the first verified listings.
                  </Typography>
                  <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: "var(--app-muted)" }}>
                    This registry is up, but there are no public tools to browse yet. You can still
                    inspect publishers, or sign in if you are preparing to publish.
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                  <Link href="/public/publishers" style={{ textDecoration: "none" }}>
                    <Button
                      variant="outlined"
                      sx={{
                        borderRadius: 2.5,
                        borderColor: "var(--app-border)",
                        color: "var(--app-fg)",
                        fontWeight: 700,
                      }}
                    >
                      Browse publishers
                    </Button>
                  </Link>
                  <Link href="/login" style={{ textDecoration: "none" }}>
                    <Button
                      variant="contained"
                      sx={{
                        borderRadius: 2.5,
                        fontWeight: 700,
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
                      Sign in to publish
                    </Button>
                  </Link>
                </Box>
              </CardContent>
            </Card>
          )}
        </Box>

      </Box>
    </Box>
  );
}

function CategoryChip({ label, q }: { label: string; q: string }) {
  return (
    <Link href={`/public/tools?q=${encodeURIComponent(q)}`} style={{ textDecoration: "none" }}>
      <Box
        sx={{
          display: "inline-flex",
          alignItems: "center",
          px: 1.5,
          py: 0.65,
          borderRadius: 999,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
          fontSize: 12,
          fontWeight: 600,
          color: "var(--app-fg)",
          cursor: "pointer",
          transition: "border-color 0.15s ease, background-color 0.15s ease",
          "&:hover": {
            borderColor: "var(--app-accent)",
            bgcolor: "var(--app-active-bg)",
          },
        }}
      >
        {label}
      </Box>
    </Link>
  );
}

function FeaturedToolCard({ tool }: { tool: RegistryToolListing }) {
  const title = tool.display_name?.trim() || tool.tool_name;
  const description =
    tool.description?.trim() ||
    "Open the listing to inspect trust signals, publisher details, and install instructions.";
  const publisher = tool.publisher_id || tool.author || "Publisher not listed";
  const categories = tool.categories?.slice(0, 2) ?? [];

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3.5,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
        height: "100%",
      }}
    >
      <CardContent sx={{ p: 3, display: "grid", gap: 2, height: "100%" }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1.5 }}>
          <Box sx={{ display: "grid", gap: 0.75 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}>
              {title}
            </Typography>
            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
              {tool.tool_name}
            </Typography>
          </Box>
          <CertificationPill level={tool.certification_level} />
        </Box>

        <Typography
          sx={{
            fontSize: 13,
            lineHeight: 1.7,
            color: "var(--app-muted)",
            display: "-webkit-box",
            overflow: "hidden",
            WebkitBoxOrient: "vertical",
            WebkitLineClamp: 4,
          }}
        >
          {description}
        </Typography>

        <Box sx={{ display: "grid", gap: 1, mt: "auto" }}>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {categories.length > 0 ? (
              categories.map((category) => (
                <Box
                  key={category}
                  sx={{
                    px: 1,
                    py: 0.35,
                    borderRadius: 999,
                    bgcolor: "var(--app-control-bg)",
                    border: "1px solid var(--app-border)",
                    fontSize: 11,
                    color: "var(--app-muted)",
                  }}
                >
                  {category}
                </Box>
              ))
            ) : (
              <Box
                sx={{
                  px: 1,
                  py: 0.35,
                  borderRadius: 999,
                  bgcolor: "var(--app-control-bg)",
                  border: "1px solid var(--app-border)",
                  fontSize: 11,
                  color: "var(--app-muted)",
                }}
              >
                Verified listing
              </Box>
            )}
          </Box>

          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
            Publisher: {publisher}
          </Typography>
          <Link
            href={`/public/listings/${encodeURIComponent(tool.tool_name)}`}
            style={{ textDecoration: "none" }}
          >
            <Button
              variant="text"
              sx={{
                mt: 0.5,
                px: 0,
                justifyContent: "flex-start",
                color: "var(--app-accent)",
                fontWeight: 700,
              }}
            >
              Open listing
            </Button>
          </Link>
        </Box>
      </CardContent>
    </Card>
  );
}

function CertificationPill({ level }: { level: string | undefined }) {
  const label = formatCertificationLabel(level);

  return (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.5,
        px: 1,
        py: 0.45,
        borderRadius: 999,
        bgcolor: "var(--app-control-bg)",
        border: "1px solid var(--app-border)",
        fontSize: 11,
        fontWeight: 700,
        color: "var(--app-fg)",
        whiteSpace: "nowrap",
      }}
    >
      <VerifiedOutlinedIcon sx={{ fontSize: 14, color: "var(--app-accent)" }} />
      {label}
    </Box>
  );
}

function formatCertificationLabel(level: string | undefined): string {
  if (!level) return "Verified";
  return level
    .split(/[_-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

