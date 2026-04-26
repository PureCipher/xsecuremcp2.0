"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";

import type { RegistryClientSummary } from "@/lib/registryClient";

type Props = {
  clients?: RegistryClientSummary[];
  kinds?: string[];
  onboardHref?: string;
  serversHref?: string;
  publicView?: boolean;
  errorMessage?: string | null;
  accessDenied?: boolean;
};

const KIND_LABELS: Record<string, string> = {
  agent: "Agent",
  service: "Service",
  framework: "Framework",
  tooling: "Tooling",
  other: "Other",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFKD")
    .replaceAll(/\p{Diacritic}+/gu, "")
    .trim();
}

function clientHaystack(c: RegistryClientSummary): string {
  return normalizeText(
    [
      c.slug,
      c.display_name,
      c.description,
      c.intended_use,
      c.owner_publisher_id,
      c.kind,
    ]
      .filter(Boolean)
      .join(" "),
  );
}

export function ClientsDirectory({
  clients = [],
  kinds = [],
  onboardHref,
  serversHref,
  publicView = false,
  errorMessage = null,
  accessDenied = false,
}: Props) {
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<string>("__all__");
  const normalizedQuery = useMemo(() => normalizeText(query), [query]);

  const filtered = useMemo(() => {
    const matchesKind = (c: RegistryClientSummary) =>
      kindFilter === "__all__" ? true : c.kind === kindFilter;
    const matchesText = (c: RegistryClientSummary) =>
      normalizedQuery ? clientHaystack(c).includes(normalizedQuery) : true;
    return [...clients]
      .filter((c) => matchesKind(c) && matchesText(c))
      .sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0));
  }, [clients, kindFilter, normalizedQuery]);

  const hasFilters = normalizedQuery.length > 0 || kindFilter !== "__all__";
  const showEmptyState = clients.length === 0 && !accessDenied;

  return (
    <Card variant="outlined" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        <Box
          sx={{
            p: { xs: 2.5, md: 3 },
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            alignItems: { xs: "flex-start", md: "center" },
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          <Box sx={{ display: "grid", gap: 0.75, maxWidth: 720 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Client registry
            </Typography>
            <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
              {clients.length === 0
                ? publicView
                  ? "No public clients yet"
                  : "No clients onboarded yet"
                : `${clients.length} ${clients.length === 1 ? "client" : "clients"} registered`}
            </Typography>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              {publicView
                ? "Public client profiles will appear here once client metadata is published."
                : "Each client gets a stable slug that flows through every governance plane as the request actor — same identity in policy, contracts, consent, and provenance."}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {onboardHref && !publicView ? (
              <Link href={onboardHref} legacyBehavior passHref>
                <Button component="a" variant="contained">
                  Onboard client
                </Button>
              </Link>
            ) : null}
            {serversHref ? (
              <Link href={serversHref} legacyBehavior passHref>
                <Button
                  component="a"
                  variant={onboardHref && !publicView ? "outlined" : "contained"}
                >
                  MCP servers
                </Button>
              </Link>
            ) : null}
          </Box>
        </Box>

        {errorMessage ? (
          <Box
            sx={{
              mx: { xs: 2.5, md: 3 },
              mb: 2,
              p: 2,
              borderRadius: 2,
              border: "1px solid rgb(239, 68, 68)",
              bgcolor: "rgba(239, 68, 68, 0.08)",
            }}
          >
            <Typography
              variant="caption"
              sx={{ color: "rgb(254, 202, 202)", fontWeight: 600 }}
            >
              {errorMessage}
            </Typography>
          </Box>
        ) : null}

        {accessDenied ? (
          <Box sx={{ px: { xs: 2.5, md: 3 }, pb: { xs: 2.5, md: 3 } }}>
            <Box
              sx={{
                p: 3,
                borderRadius: 2,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
              }}
            >
              <Typography
                variant="body2"
                sx={{ color: "var(--app-muted)", fontWeight: 600 }}
              >
                Sign in as a publisher or admin to manage MCP clients.
              </Typography>
            </Box>
          </Box>
        ) : null}

        {!accessDenied && clients.length > 0 ? (
          <>
            <Divider sx={{ borderColor: "var(--app-border)" }} />

            <Box
              sx={{
                p: { xs: 2.5, md: 3 },
                display: "flex",
                flexDirection: { xs: "column", sm: "row" },
                gap: 2,
                alignItems: { xs: "stretch", sm: "center" },
              }}
            >
              <TextField
                size="small"
                placeholder="Search clients by slug, name, or owner"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                sx={{ flex: 1 }}
              />
              <Select
                size="small"
                value={kindFilter}
                onChange={(e) => setKindFilter(String(e.target.value))}
                sx={{ minWidth: 180 }}
              >
                <MenuItem value="__all__">All kinds</MenuItem>
                {(kinds.length > 0
                  ? kinds
                  : ["agent", "service", "framework", "tooling", "other"]
                ).map((k) => (
                  <MenuItem key={k} value={k}>
                    {kindLabel(k)}
                  </MenuItem>
                ))}
              </Select>
            </Box>

            <Divider sx={{ borderColor: "var(--app-border)" }} />

            <Box sx={{ p: { xs: 1.5, md: 2 } }}>
              {filtered.length === 0 ? (
                <Box sx={{ p: 3 }}>
                  <Typography
                    variant="body2"
                    sx={{ color: "var(--app-muted)" }}
                  >
                    {hasFilters
                      ? "No clients match the current filters."
                      : "No clients to display."}
                  </Typography>
                </Box>
              ) : (
                <Box
                  sx={{
                    display: "grid",
                    gap: 1.5,
                    gridTemplateColumns: {
                      xs: "1fr",
                      md: "repeat(2, 1fr)",
                      lg: "repeat(3, 1fr)",
                    },
                  }}
                >
                  {filtered.map((c) => (
                    <ClientCard key={c.client_id} client={c} />
                  ))}
                </Box>
              )}
            </Box>
          </>
        ) : null}

        {showEmptyState ? (
          <Box sx={{ px: { xs: 2.5, md: 3 }, pb: { xs: 2.5, md: 3 } }}>
            <Box
              sx={{
                p: { xs: 2.5, md: 3 },
                borderRadius: 3,
                border: "1px solid var(--app-border)",
                bgcolor: "var(--app-control-bg)",
                display: "grid",
                gap: 2,
              }}
            >
              <Box sx={{ display: "grid", gap: 0.75 }}>
                <Chip
                  label={
                    publicView
                      ? "Public directory pending"
                      : "Client onboarding ready"
                  }
                  size="small"
                  sx={{
                    justifySelf: "start",
                    bgcolor: "var(--app-control-active-bg)",
                    color: "var(--app-fg)",
                  }}
                />
                <Typography
                  sx={{
                    fontSize: 15,
                    fontWeight: 700,
                    color: "var(--app-fg)",
                  }}
                >
                  Start with a real client identity.
                </Typography>
                <Typography
                  sx={{
                    maxWidth: 700,
                    fontSize: 13,
                    color: "var(--app-muted)",
                  }}
                >
                  {publicView
                    ? "This page stays empty until client metadata is intentionally published for public discovery."
                    : "Register the agent, service, or framework that will hold tokens — its slug becomes the actor every plane records against."}
                </Typography>
              </Box>

              {!publicView ? (
                <Box
                  sx={{
                    display: "grid",
                    gap: 1.25,
                    gridTemplateColumns: {
                      xs: "1fr",
                      md: "repeat(3, 1fr)",
                    },
                  }}
                >
                  {[
                    "Register identity",
                    "Mint API token",
                    "Wire into governance",
                  ].map((label, index) => (
                    <Box
                      key={label}
                      sx={{
                        p: 1.5,
                        borderRadius: 2,
                        border: "1px solid var(--app-border)",
                        bgcolor: "var(--app-surface)",
                      }}
                    >
                      <Typography
                        sx={{
                          fontSize: 11,
                          fontWeight: 700,
                          color: "var(--app-muted)",
                        }}
                      >
                        Step {index + 1}
                      </Typography>
                      <Typography
                        sx={{
                          mt: 0.25,
                          fontSize: 13,
                          fontWeight: 700,
                          color: "var(--app-fg)",
                        }}
                      >
                        {label}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : null}
            </Box>
          </Box>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ClientCard({ client }: { client: RegistryClientSummary }) {
  const isSuspended = client.status === "suspended";
  return (
    <Link
      href={`/registry/clients/${encodeURIComponent(client.slug)}`}
      style={{ textDecoration: "none" }}
    >
      <Card
        variant="outlined"
        sx={{
          height: "100%",
          transition: "border-color 120ms",
          "&:hover": { borderColor: "var(--app-accent)" },
        }}
      >
        <CardContent sx={{ display: "grid", gap: 1.5 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            <Typography
              variant="body1"
              sx={{ fontWeight: 700, color: "var(--app-fg)" }}
            >
              {client.display_name || client.slug}
            </Typography>
            <Chip
              label={kindLabel(client.kind)}
              size="small"
              sx={{
                bgcolor: "var(--app-control-active-bg)",
                color: "var(--app-fg)",
                fontWeight: 600,
              }}
            />
          </Box>

          <Typography
            variant="caption"
            sx={{ color: "var(--app-muted)", fontFamily: "monospace" }}
          >
            {client.slug}
          </Typography>

          {client.description ? (
            <Typography
              variant="body2"
              sx={{
                color: "var(--app-muted)",
                display: "-webkit-box",
                overflow: "hidden",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
              }}
            >
              {client.description}
            </Typography>
          ) : null}

          <Divider sx={{ borderColor: "var(--app-border)" }} />

          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            <Box>
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
                Owner
              </Typography>
              <Typography
                variant="caption"
                sx={{ fontWeight: 600, color: "var(--app-fg)" }}
              >
                {client.owner_publisher_id || "—"}
              </Typography>
            </Box>
            <Chip
              label={isSuspended ? "Suspended" : "Active"}
              size="small"
              color={isSuspended ? "warning" : "success"}
              variant={isSuspended ? "filled" : "outlined"}
            />
          </Box>
        </CardContent>
      </Card>
    </Link>
  );
}
