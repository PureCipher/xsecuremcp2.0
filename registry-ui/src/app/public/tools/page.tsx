import Link from "next/link";
import SearchIcon from "@mui/icons-material/Search";
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
        <CardContent sx={{ p: { xs: 3, sm: 4 }, display: "grid", gap: 2 }}>
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
                ? "Browse verified tools"
                : "The trusted catalog is ready for real tools."}
            </Typography>
            <Typography sx={{ fontSize: 14, lineHeight: 1.75, color: "var(--app-muted)" }}>
              {tools.length > 0
                ? `${verifiedCount} verified ${verifiedCount === 1 ? "tool" : "tools"} from ${publisherCount} ${publisherCount === 1 ? "publisher" : "publishers"} across ${categoryCount} ${categoryCount === 1 ? "category" : "categories"}.`
                : "Tools will appear here after publishers submit them and reviewers approve them."}
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
                    "&:hover": { bgcolor: "var(--app-accent)", filter: "brightness(0.95)", boxShadow: "none" },
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
        <Card
          variant="outlined"
          sx={{
            borderRadius: 4,
            borderColor: "var(--app-border)",
            bgcolor: "var(--app-surface)",
            boxShadow: "none",
          }}
        >
          <CardContent sx={{ p: { xs: 3, sm: 4 }, display: "grid", gap: 1.5 }}>
            <Typography sx={{ fontSize: 18, fontWeight: 800, color: "var(--app-fg)" }}>
              No verified tools yet
            </Typography>
            <Typography sx={{ fontSize: 13, lineHeight: 1.75, color: "var(--app-muted)", maxWidth: 640 }}>
              Tools appear here after publishers submit them and reviewers approve them.
              Browse publishers to see who is connected, or sign in to publish.
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 0.5 }}>
              <Link href="/public/publishers" style={{ textDecoration: "none" }}>
                <Button
                  variant="contained"
                  sx={{
                    borderRadius: 2.5,
                    fontWeight: 700,
                    bgcolor: "var(--app-accent)",
                    color: "white",
                    boxShadow: "none",
                    "&:hover": { bgcolor: "var(--app-accent)", filter: "brightness(0.95)", boxShadow: "none" },
                  }}
                >
                  Browse publishers
                </Button>
              </Link>
              <Link href="/login" style={{ textDecoration: "none" }}>
                <Button
                  variant="outlined"
                  sx={{
                    borderRadius: 2.5,
                    fontWeight: 700,
                    borderColor: "var(--app-border)",
                    color: "var(--app-fg)",
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


