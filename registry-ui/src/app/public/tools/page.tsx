import Link from "next/link";

import { Box, Button, Card, CardContent, Typography } from "@mui/material";

import { listVerifiedTools, type RegistryToolListing } from "@/lib/registryClient";
import { ToolsCatalog } from "@/app/registry/app/ToolsCatalog";

export default async function PublicToolsPage() {
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
            Browse published tools, review certification levels, and open listings for install recipes.
          </Typography>
        </Box>

        <Link href="/public/publishers" legacyBehavior passHref>
          <Button component="a" variant="text" sx={{ color: "var(--app-muted)" }}>
            Browse publishers →
          </Button>
        </Link>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          {tools.length === 0 ? (
            <Typography sx={{ color: "var(--app-muted)" }}>
              No verified tools are published yet. Once tools are in the registry they&apos;ll appear here.
            </Typography>
          ) : (
            <ToolsCatalog tools={tools} basePath="/public/listings" />
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

