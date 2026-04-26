import Link from "next/link";

import { Box, Card, CardContent, Chip, Divider, Typography } from "@mui/material";

import { getRegistryClientGovernance } from "@/lib/registryClient";

const KIND_LABELS: Record<string, string> = {
  agent: "Agent",
  service: "Service",
  framework: "Framework",
  tooling: "Tooling",
  other: "Other",
};

export default async function PublicClientPage(props: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await props.params;
  const decodedId = decodeURIComponent(clientId);
  const governance = await getRegistryClientGovernance(decodedId);

  if (!governance || governance.error || !governance.slug) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
            Client not found
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
            {governance?.error ??
              `No public profile is available for ${decodedId}.`}
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Link
              href="/public/clients"
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--app-muted)",
                textDecoration: "none",
              }}
            >
              ← Back to public client directory
            </Link>
          </Box>
        </CardContent>
      </Card>
    );
  }

  const slug = governance.slug;
  const kind = governance.kind ?? "other";
  const isSuspended = governance.status === "suspended";

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Public client profile
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "text.primary" }}>
          {governance.display_name || slug}
        </Typography>
        <Box sx={{ mt: 1, display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Chip
            size="small"
            label={KIND_LABELS[kind] ?? kind}
            sx={{
              bgcolor: "var(--app-control-active-bg)",
              color: "var(--app-fg)",
              fontWeight: 700,
            }}
          />
          <Chip
            size="small"
            label={isSuspended ? "Suspended" : "Active"}
            color={isSuspended ? "warning" : "success"}
            variant={isSuspended ? "filled" : "outlined"}
          />
        </Box>
      </Box>

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: {
            xs: "1fr",
            md: "minmax(0,1.4fr) minmax(0,1fr)",
          },
        }}
      >
        <Card variant="outlined">
          <CardContent>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              About
            </Typography>
            <Typography
              variant="body2"
              sx={{ mt: 1.5, color: "var(--app-muted)" }}
            >
              {governance.description ||
                "This client hasn't published a description."}
            </Typography>
            {governance.intended_use ? (
              <>
                <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />
                <Typography
                  sx={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  Intended use
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ mt: 1, color: "var(--app-muted)" }}
                >
                  {governance.intended_use}
                </Typography>
              </>
            ) : null}
          </CardContent>
        </Card>

        <Card variant="outlined">
          <CardContent>
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Identifier
            </Typography>
            <Box
              sx={{
                mt: 1.5,
                p: 1.5,
                borderRadius: 1.5,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  color: "var(--app-muted)",
                  fontSize: 10,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                }}
              >
                Slug · actor_id
              </Typography>
              <Typography
                sx={{
                  mt: 0.5,
                  fontFamily: "monospace",
                  color: "var(--app-fg)",
                }}
              >
                {slug}
              </Typography>
            </Box>
            {governance.owner_publisher_id ? (
              <>
                <Divider sx={{ my: 2, borderColor: "var(--app-border)" }} />
                <Typography
                  sx={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  Operated by
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ mt: 1 }}
                >
                  <Link
                    href={`/public/publishers/${encodeURIComponent(
                      governance.owner_publisher_id,
                    )}`}
                    style={{ color: "var(--app-accent)", fontWeight: 600 }}
                  >
                    {governance.owner_publisher_id}
                  </Link>
                </Typography>
              </>
            ) : null}
          </CardContent>
        </Card>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: 1,
              flexWrap: "wrap",
            }}
          >
            <Typography
              sx={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Activity at a glance
            </Typography>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Aggregate counts only — counterparty identifiers are private.
            </Typography>
          </Box>
          <Box
            sx={{
              mt: 2,
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, 1fr)",
                md: "repeat(4, 1fr)",
              },
            }}
          >
            <Tile
              title="Contracts"
              primary={String(governance.contracts?.active_count ?? 0)}
              secondary="active"
            />
            <Tile
              title="Consent"
              primary={String(governance.consent?.outgoing_count ?? 0)}
              secondary={`outgoing · ${governance.consent?.incoming_count ?? 0} incoming`}
            />
            <Tile
              title="Ledger"
              primary={String(governance.ledger?.record_count ?? 0)}
              secondary="records"
            />
            <Tile
              title="Reflexive"
              primary={String(governance.reflexive?.drift_event_count ?? 0)}
              secondary="drift events"
            />
          </Box>
        </CardContent>
      </Card>

      <Box sx={{ pt: 1 }}>
        <Link
          href="/public/clients"
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--app-muted)",
            textDecoration: "none",
          }}
        >
          ← Back to public client directory
        </Link>
      </Box>
    </Box>
  );
}

function Tile({
  title,
  primary,
  secondary,
}: {
  title: string;
  primary: string;
  secondary: string;
}) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 0.5,
      }}
    >
      <Typography
        sx={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--app-muted)",
        }}
      >
        {title}
      </Typography>
      <Typography variant="h6" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
        {primary}
      </Typography>
      <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
        {secondary}
      </Typography>
    </Box>
  );
}
