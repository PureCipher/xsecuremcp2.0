import Link from "next/link";
import { getRegistryHealth } from "@/lib/registryClient";

import { Box, Card, CardContent, Typography } from "@mui/material";

import { AppThemePreferencesPanel } from "./AppThemePreferencesPanel";
import { CliTerminalPreferencesPanel } from "./CliTerminalPreferencesPanel";

export default async function RegistrySettingsPage() {
  const health = await getRegistryHealth();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box component="header" sx={{ display: "grid", gap: 0.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
          Registry settings
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
          Policy overview
        </Typography>
        <Typography sx={{ mt: 0.5, maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
          Read-only view of how this SecureMCP registry is configured. Use the dedicated Policy page to manage live
          access rules and rollbacks.
        </Typography>
      </Box>

      {health ? (
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
          <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
            <CardContent sx={{ p: 2.5 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Certification & moderation
              </Typography>
              <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                <li>
                  Minimum certification level:{" "}
                  <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                    {health.minimum_certification}
                  </Box>
                </li>
                <li>
                  Moderation required:{" "}
                  <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                    {health.require_moderation ? "Yes" : "No"}
                  </Box>
                </li>
              </Box>
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
            <CardContent sx={{ p: 2.5 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                Authentication
              </Typography>
              <Box component="ul" sx={{ mt: 1.5, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                <li>
                  Auth enabled:{" "}
                  <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                    {health.auth_enabled ? "Yes" : "No"}
                  </Box>
                </li>
                <li>
                  Issuer ID:{" "}
                  <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" }}>
                    {health.issuer_id}
                  </Box>
                </li>
              </Box>
            </CardContent>
          </Card>
        </Box>
      ) : (
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
              Unable to load settings from the registry. Check that the registry is running and reachable.
            </Typography>
          </CardContent>
        </Card>
      )}

      <AppThemePreferencesPanel />
      <CliTerminalPreferencesPanel />

      <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
        Policy changes now live in{" "}
        <Link href="/registry/policy" className="underline">
          Policy
        </Link>
        . For a live snapshot of counts and status, see{" "}
        <Link href="/registry/health" className="underline">
          Health
        </Link>
        .
      </Typography>
    </Box>
  );
}
