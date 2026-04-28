import Link from "next/link";
import SearchIcon from "@mui/icons-material/Search";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import TravelExploreOutlinedIcon from "@mui/icons-material/TravelExploreOutlined";
import VerifiedOutlinedIcon from "@mui/icons-material/VerifiedOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
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

const TRUST_SIGNALS: ReadonlyArray<{
  eyebrow: string;
  title: string;
  body: string;
}> = [
  {
    eyebrow: "Manifest",
    title: "See access before install",
    body: "Every listing makes its permissions, data flows, and resource access visible before you adopt it.",
  },
  {
    eyebrow: "Certification",
    title: "Review level at a glance",
    body: "Listings surface their review tier clearly, so you do not have to infer how much scrutiny a tool received.",
  },
  {
    eyebrow: "Signature",
    title: "Verify what was published",
    body: "Attestations are signed and checked on the detail page so tampering is visible from outside the publisher.",
  },
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
  const certifiedCount = tools.filter((tool) => isCertified(tool.certification_level)).length;
  const minimumCertification = formatMinimumCertification(health?.minimum_certification);

  return (
    <Box sx={{ py: { xs: 2, sm: 2.5, md: 3 } }}>
      <Box sx={{ display: "grid", gap: { xs: 3, md: 4 } }}>
        <Box
          sx={{
            display: "grid",
            gap: { xs: 2, md: 3 },
            gridTemplateColumns: {
              xs: "1fr",
              lg: "minmax(0, 1.35fr) minmax(320px, 380px)",
            },
            alignItems: "stretch",
          }}
        >
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
                  Search verified MCP tools, inspect the publisher behind them, and
                  open a listing that shows the trust signals you need before adopting it.
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

              <Box sx={{ display: "grid", gap: 1.5 }}>
                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                  <Typography
                    sx={{
                      fontSize: 11,
                      fontWeight: 800,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "var(--app-muted)",
                      mr: 0.5,
                    }}
                  >
                    Popular filters
                  </Typography>
                  {HERO_CATEGORIES.map((category) => (
                    <CategoryChip key={category.q} label={category.label} q={category.q} />
                  ))}
                </Box>

                <Box
                  sx={{
                    display: "grid",
                    gap: 1.5,
                    gridTemplateColumns: {
                      xs: "1fr",
                      sm: "repeat(2, minmax(0, 1fr))",
                      md: "repeat(3, minmax(0, 1fr))",
                    },
                  }}
                >
                  <LandingShortcut
                    href="/public/tools"
                    icon={<Inventory2OutlinedIcon sx={{ fontSize: 18 }} />}
                    title="Browse verified tools"
                    body="Jump straight into the catalog and compare published listings."
                  />
                  <LandingShortcut
                    href="/public/publishers"
                    icon={<ApartmentOutlinedIcon sx={{ fontSize: 18 }} />}
                    title="See who publishes them"
                    body="Open publisher profiles to see the teams behind the tools."
                  />
                  <LandingShortcut
                    href="/login"
                    icon={<BoltOutlinedIcon sx={{ fontSize: 18 }} />}
                    title="Sign in to publish"
                    body="Move into the console when you want to submit or manage tools."
                  />
                </Box>
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
            <CardContent sx={{ p: { xs: 3, sm: 3.5 }, display: "grid", gap: 2.5, height: "100%" }}>
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
                  Registry snapshot
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
                  Search, verify, install.
                </Typography>
                <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: "var(--app-muted)" }}>
                  The public registry is built to answer three questions quickly:
                  what a tool does, who stands behind it, and how much review it has received.
                </Typography>
              </Box>

              <Box
                sx={{
                  display: "grid",
                  gap: 1.25,
                  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                }}
              >
                <SnapshotStat label="Verified" value={String(verifiedCount)} />
                <SnapshotStat label="Publishers" value={String(publisherCount)} />
                <SnapshotStat label="Certified" value={String(certifiedCount)} />
              </Box>

              <Box
                sx={{
                  display: "grid",
                  gap: 1.25,
                  p: 2,
                  borderRadius: 3,
                  border: "1px solid var(--app-border)",
                  bgcolor: "var(--app-control-bg)",
                }}
              >
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <ShieldOutlinedIcon sx={{ fontSize: 18, color: "var(--app-accent)" }} />
                  <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                    Trust baseline
                  </Typography>
                </Box>
                <Typography sx={{ fontSize: 12, lineHeight: 1.7, color: "var(--app-muted)" }}>
                  Minimum review tier: <strong>{minimumCertification}</strong>. Listing pages
                  surface certification, signature checks, and publisher context together.
                </Typography>
              </Box>

              <Box sx={{ display: "grid", gap: 1 }}>
                <Link href="/public/tools" style={{ textDecoration: "none" }}>
                  <Button
                    fullWidth
                    variant="contained"
                    sx={{
                      borderRadius: 2.5,
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
                    Open tool catalog
                  </Button>
                </Link>
                <Link href="/public/publishers" style={{ textDecoration: "none" }}>
                  <Button
                    fullWidth
                    variant="outlined"
                    sx={{
                      borderRadius: 2.5,
                      py: 1,
                      fontWeight: 700,
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                    }}
                  >
                    Browse publishers
                  </Button>
                </Link>
              </Box>
            </CardContent>
          </Card>
        </Box>

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

        <Box id="trust-signals" sx={{ display: "grid", gap: 2 }}>
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
              Trust signals
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
              The essentials are always visible.
            </Typography>
          </Box>

          <Box
            sx={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
            }}
          >
            {TRUST_SIGNALS.map((signal) => (
              <TrustSignalCard
                key={signal.eyebrow}
                eyebrow={signal.eyebrow}
                title={signal.title}
                body={signal.body}
              />
            ))}
          </Box>
        </Box>

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
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                For publishers
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
                Ready to publish a tool?
              </Typography>
              <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: "var(--app-muted)", maxWidth: 720 }}>
                Sign in to the registry console to declare your manifest, submit your tool for review,
                and generate install recipes from runtime metadata.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Link href="/login" style={{ textDecoration: "none" }}>
                <Button
                  variant="contained"
                  sx={{
                    borderRadius: 2.5,
                    px: 2.5,
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
              <Link href="/registry/publish/get-started" style={{ textDecoration: "none" }}>
                <Button
                  variant="outlined"
                  sx={{
                    borderRadius: 2.5,
                    px: 2.5,
                    fontWeight: 700,
                    borderColor: "var(--app-border)",
                    color: "var(--app-fg)",
                  }}
                >
                  Read the publisher guide
                </Button>
              </Link>
            </Box>
          </CardContent>
        </Card>
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

function LandingShortcut({
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
          height: "100%",
          p: 2,
          borderRadius: 3,
          border: "1px solid var(--app-border)",
          bgcolor: "var(--app-control-bg)",
          display: "grid",
          gap: 1,
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

function TrustSignalCard({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
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
      <CardContent sx={{ p: 3, display: "grid", gap: 1.25 }}>
        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1, color: "var(--app-accent)" }}>
          <TravelExploreOutlinedIcon sx={{ fontSize: 18 }} />
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            {eyebrow}
          </Typography>
        </Box>
        <Typography sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}>
          {title}
        </Typography>
        <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: "var(--app-muted)" }}>
          {body}
        </Typography>
      </CardContent>
    </Card>
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

function formatMinimumCertification(level: string | undefined): string {
  if (!level) return "Registry policy";
  return formatCertificationLabel(level);
}

function isCertified(level: string | undefined): boolean {
  if (!level) return false;
  return ["basic", "standard", "strict", "advanced"].includes(level.toLowerCase());
}
