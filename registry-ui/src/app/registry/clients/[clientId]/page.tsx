import Link from "next/link";

import { Box, Card, CardContent, Typography } from "@mui/material";

import {
  getRegistryClient,
  getRegistryClientGovernance,
} from "@/lib/registryClient";
import { ClientDetailView } from "./ClientDetailView";

export default async function ClientDetailPage(props: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await props.params;
  const decodedId = decodeURIComponent(clientId);

  const [detail, governance] = await Promise.all([
    getRegistryClient(decodedId),
    getRegistryClientGovernance(decodedId),
  ]);

  // Detail and governance are independent endpoints — the detail
  // route gates on owner-or-admin, governance returns a sanitized
  // payload for non-managers. If detail can't be loaded at all, we
  // surface a not-found card. If governance fails (404 specifically)
  // we still render the detail view; the panels degrade gracefully.
  if (!detail || detail.status === 404 || (!detail.client && !detail.error)) {
    return <NotFoundCard slug={decodedId} />;
  }

  if (!detail.client) {
    return <ErrorCard slug={decodedId} message={detail.error} />;
  }

  return (
    <ClientDetailView
      client={detail.client}
      tokens={detail.tokens ?? []}
      governance={governance ?? null}
    />
  );
}

function NotFoundCard({ slug }: { slug: string }) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography
          variant="h6"
          sx={{ fontWeight: 700, color: "var(--app-fg)" }}
        >
          Client not found
        </Typography>
        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
          No registered client matches{" "}
          <Box component="span" sx={{ fontFamily: "monospace" }}>
            {slug}
          </Box>
          .
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Link href="/registry/clients"><Box sx={{ display: "inline-flex", fontSize: 11, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" }, }}>
              ← Back to clients
            </Box></Link>
        </Box>
      </CardContent>
    </Card>
  );
}

function ErrorCard({
  slug,
  message,
}: {
  slug: string;
  message?: string;
}) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography
          variant="h6"
          sx={{ fontWeight: 700, color: "var(--app-fg)" }}
        >
          Unable to load client
        </Typography>
        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
          {message ?? `Failed to load registered client ${slug}.`}
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Link href="/registry/clients"><Box sx={{ display: "inline-flex", fontSize: 11, fontWeight: 700, color: "var(--app-muted)", textDecoration: "none", "&:hover": { color: "var(--app-fg)" }, }}>
              ← Back to clients
            </Box></Link>
        </Box>
      </CardContent>
    </Card>
  );
}
