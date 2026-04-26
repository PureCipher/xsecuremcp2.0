import Link from "next/link";
import { Box, Button, Card, CardContent, Container, Typography } from "@mui/material";

import { listPublishers, listVerifiedTools } from "@/lib/registryClient";

export const dynamic = "force-dynamic";

interface CatalogStats {
  toolCount: number;
  publisherCount: number;
  certifiedCount: number;
}

async function fetchCatalogStats(): Promise<CatalogStats> {
  // Best-effort. If the backend is unreachable we fall back to zeros
  // and the hero still renders — better than blocking the entire page.
  const [toolsResponse, publishersResponse] = await Promise.all([
    listVerifiedTools(),
    listPublishers(),
  ]);
  const tools = toolsResponse?.tools ?? [];
  const publishers = publishersResponse?.publishers ?? [];
  const certified = tools.filter((tool) => {
    const level = (tool.certification_level ?? "").toLowerCase();
    return (
      level.includes("certified") ||
      level.includes("verified") ||
      level.includes("trusted") ||
      level.includes("attested") ||
      level.includes("signed")
    );
  }).length;
  return {
    toolCount: tools.length,
    publisherCount: publishers.length,
    certifiedCount: certified,
  };
}

export default async function PublicLandingPage() {
  const stats = await fetchCatalogStats();

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 6, sm: 10 } }}>
      <Box sx={{ display: "grid", gap: 8 }}>
        <Box component="header" sx={{ display: "grid", gap: 3, maxWidth: 880 }}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            PureCipher · Trusted MCP Registry
          </Typography>
          <Typography
            variant="h2"
            sx={{
              fontWeight: 850,
              letterSpacing: "-0.04em",
              lineHeight: 1.05,
              color: "var(--app-fg)",
              fontSize: { xs: 40, sm: 52, md: 60 },
            }}
          >
            Install MCP tools you can actually trust.
          </Typography>
          <Typography
            sx={{
              fontSize: 17,
              lineHeight: 1.7,
              color: "var(--app-muted)",
              maxWidth: 720,
            }}
          >
            Every tool in the catalog ships with a signed security manifest,
            an attested certification level, and a copy-paste install recipe
            for your client. Browse the catalog, vet the publisher, and pull
            in tools without guessing what they do.
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, mt: 1 }}>
            <Link href="/public/tools" style={{ textDecoration: "none" }}>
              <Button
                size="large"
                variant="contained"
                sx={{
                  borderRadius: 2.5,
                  px: 3,
                  py: 1.25,
                  fontWeight: 700,
                  bgcolor: "var(--app-accent)",
                  color: "white",
                  "&:hover": { bgcolor: "var(--app-accent)", filter: "brightness(0.95)" },
                }}
              >
                Browse the catalog
              </Button>
            </Link>
            <Link href="/public/publishers" style={{ textDecoration: "none" }}>
              <Button
                size="large"
                variant="outlined"
                sx={{
                  borderRadius: 2.5,
                  px: 3,
                  py: 1.25,
                  fontWeight: 700,
                  borderColor: "var(--app-border)",
                  color: "var(--app-fg)",
                  "&:hover": {
                    borderColor: "var(--app-accent)",
                    bgcolor: "var(--app-hover-bg)",
                  },
                }}
              >
                See publishers
              </Button>
            </Link>
          </Box>
        </Box>

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", sm: "repeat(3, minmax(0, 1fr))" },
          }}
        >
          <StatCard label="Verified tools" value={stats.toolCount} />
          <StatCard label="Certified" value={stats.certifiedCount} />
          <StatCard label="Publishers" value={stats.publisherCount} />
        </Box>

        <Box sx={{ display: "grid", gap: 3 }}>
          <Box sx={{ display: "grid", gap: 1 }}>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              How it works
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
              Three signals, one decision.
            </Typography>
          </Box>

          <Box
            sx={{
              display: "grid",
              gap: 2,
              gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
            }}
          >
            <FeatureCard
              eyebrow="01 · Manifest"
              title="Know what it can do"
              body="Every listing declares its permissions, data flows, and resource access. No hidden network calls, no surprise file writes — what you see in the manifest is what the tool is allowed to do."
            />
            <FeatureCard
              eyebrow="02 · Certification"
              title="Vetted before publish"
              body="Tools pass through a certification pipeline that scores their manifest against a set of safety rules. Each listing carries a tier — Self-attested, Basic, Standard, or Strict — that's visible at a glance."
            />
            <FeatureCard
              eyebrow="03 · Signature"
              title="Tamper-evident"
              body="Attestations are cryptographically signed. The detail page verifies the signature on every visit and shows manifest hash matches, so a swapped binary is detectable from outside the publisher's organization."
            />
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
              p: { xs: 4, sm: 6 },
              display: "grid",
              gap: 3,
              alignItems: "center",
              gridTemplateColumns: { xs: "1fr", md: "1.2fr 1fr" },
            }}
          >
            <Box>
              <Typography
                sx={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Publishers
              </Typography>
              <Typography
                variant="h4"
                sx={{ fontWeight: 800, mt: 1, color: "var(--app-fg)" }}
              >
                Ship a tool that earns trust on day one.
              </Typography>
              <Typography
                sx={{ mt: 1.5, fontSize: 14, lineHeight: 1.65, color: "var(--app-muted)" }}
              >
                Sign in to the registry console, declare your manifest, and
                submit for review. Approved listings appear here with a
                cryptographic attestation, version history, and install
                recipes generated from your runtime metadata.
              </Typography>
              <Box sx={{ display: "flex", gap: 1.5, mt: 2.5, flexWrap: "wrap" }}>
                <Link href="/login" style={{ textDecoration: "none" }}>
                  <Button
                    variant="contained"
                    sx={{
                      borderRadius: 2.5,
                      px: 2.5,
                      py: 1,
                      fontWeight: 700,
                      bgcolor: "var(--app-accent)",
                      color: "white",
                      "&:hover": {
                        bgcolor: "var(--app-accent)",
                        filter: "brightness(0.95)",
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
                      py: 1,
                      fontWeight: 700,
                      borderColor: "var(--app-border)",
                      color: "var(--app-fg)",
                    }}
                  >
                    Read the publisher guide
                  </Button>
                </Link>
              </Box>
            </Box>
            <Box
              sx={{
                p: 3,
                borderRadius: 3,
                bgcolor: "var(--app-control-bg)",
                border: "1px solid var(--app-border)",
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: 12,
                color: "var(--app-fg)",
                whiteSpace: "pre",
                overflow: "auto",
              }}
            >
              {`# Get started in three commands
$ pip install purecipher-publisher
$ purecipher init my-tool --template http
$ purecipher publish`}
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
      }}
    >
      <CardContent sx={{ p: 3 }}>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          {label}
        </Typography>
        <Typography
          sx={{
            fontSize: 36,
            fontWeight: 850,
            color: "var(--app-fg)",
            lineHeight: 1.1,
            mt: 0.5,
          }}
        >
          {value.toLocaleString()}
        </Typography>
      </CardContent>
    </Card>
  );
}

function FeatureCard({
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
        borderRadius: 3,
        borderColor: "var(--app-border)",
        bgcolor: "var(--app-surface)",
        boxShadow: "none",
        height: "100%",
      }}
    >
      <CardContent sx={{ p: 3, display: "grid", gap: 1.5 }}>
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
        <Typography
          sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}
        >
          {title}
        </Typography>
        <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: "var(--app-muted)" }}>
          {body}
        </Typography>
      </CardContent>
    </Card>
  );
}
