import type { ReactNode } from "react";
import Link from "next/link";

import { NavIcon } from "@/components/security";
import { AppBar, Box, Button, Toolbar, Typography } from "@mui/material";

// Iter 14.27 — Edge-to-edge public pages.
//
// Previously the public registry wrapped its toolbar and body in
// MUI ``<Container maxWidth="lg">`` (1200px), which centered
// content with empty 200-300px gutters on standard 1440 / 1920
// monitors. The pages felt narrow and over-padded on wide screens
// while still cramped on mobile.
//
// New treatment: a shared responsive padding scale that breathes
// at every viewport, with a soft ceiling at 1600px so ultra-wide
// monitors don't stretch line lengths past readability. The
// ceiling is generous enough that 1440 / 1920 displays render
// fully edge-aware with comfortable margins, not Container-style
// chunks of empty space.
const SHELL_SX = {
  width: "100%",
  maxWidth: 1600,
  mx: "auto",
  px: { xs: 2, sm: 3, md: 4, xl: 6 },
} as const;

export default function PublicLayout({ children }: { children: ReactNode }) {
  const consoleUrl = process.env.NEXT_PUBLIC_CONSOLE_URL ?? "/registry/app";
  const signInUrl = process.env.NEXT_PUBLIC_CONSOLE_SIGNIN_URL ?? "/login";

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "var(--app-bg)", color: "text.primary" }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: "var(--app-chrome-bg)",
          color: "text.primary",
          borderBottom: "1px solid var(--app-chrome-border)",
          backdropFilter: "blur(18px)",
          backgroundImage: "none",
          boxShadow: "0 10px 30px rgba(15, 23, 42, 0.04)",
        }}
      >
        <Toolbar disableGutters sx={{ ...SHELL_SX, display: "flex", alignItems: "center", gap: 2 }}>
            <Link href="/public/tools" aria-label="Public registry home" style={{ textDecoration: "none", color: "inherit" }}>
              <Box
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 1.5,
                  px: 0.5,
                  py: 0.5,
                  borderRadius: 2.5,
                  "&:hover": { bgcolor: "var(--app-hover-bg)" },
                }}
              >
                <Box
                  sx={{
                    width: 36,
                    height: 36,
                    borderRadius: 2,
                    bgcolor: "var(--app-accent)",
                    color: "var(--app-accent-contrast)",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 900,
                    letterSpacing: "0.16em",
                  }}
                >
                  PC
                </Box>
                <Box sx={{ minWidth: 0, lineHeight: 1.1 }}>
                  <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }} noWrap>
                    PureCipher
                  </Typography>
                  <Typography sx={{ fontSize: 12, color: "text.primary" }} noWrap>
                    Public Registry
                  </Typography>
                </Box>
              </Box>
            </Link>

            <Box sx={{ display: { xs: "none", sm: "flex" }, alignItems: "center", gap: 1 }}>
              <PublicNavLink href="/public/tools" icon="tools" label="Tools" />
              <PublicNavLink href="/public/publishers" icon="publishers" label="Publishers" />
              {/* Iter 14.28 — dropped "Servers" pill. The
                  ``/public/servers`` route was a duplicate of
                  ``/public/publishers`` (same backend list); the
                  per-server detail page's PublicServerDetailTabs
                  now render on the publisher detail page. Old URLs
                  redirect to ``/public/publishers/*``. */}
              {/* /public/clients is hidden until the backend client
                  directory ships — surfacing a nav link to a dead-end
                  empty state erodes trust. The route still resolves
                  for any old bookmarks. */}
            </Box>

            <Box sx={{ ml: "auto", display: "flex", alignItems: "center", gap: 1 }}>
              <Link href={signInUrl} style={{ textDecoration: "none" }}>
                <Button
                  size="small"
                  variant="outlined"
                  sx={{
                    borderRadius: 2.5,
                    borderColor: "var(--app-accent)",
                    color: "var(--app-muted)",
                    fontWeight: 700,
                    "&:hover": { bgcolor: "var(--app-control-active-bg)", borderColor: "var(--app-accent)" },
                  }}
                >
                  Sign in
                </Button>
              </Link>
              <Link href={consoleUrl} style={{ textDecoration: "none" }}>
                <Button
                  size="small"
                  variant="outlined"
                  sx={{
                    display: { xs: "none", sm: "inline-flex" },
                    borderRadius: 2.5,
                    borderColor: "var(--app-control-border)",
                    bgcolor: "var(--app-control-bg)",
                    color: "var(--app-muted)",
                    fontWeight: 700,
                    "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
                  }}
                >
                  Console
                </Button>
              </Link>
            </Box>
        </Toolbar>
      </AppBar>

      <Box sx={{ ...SHELL_SX, py: { xs: 3, sm: 4 } }}>
        <Box sx={{ mb: 2, display: { xs: "flex", sm: "none" }, flexWrap: "wrap", gap: 1 }}>
          <MobilePill href="/public/tools" icon="tools" label="Tools" />
          <MobilePill href="/public/publishers" icon="publishers" label="Publishers" />
          {/* Iter 14.28 — Servers pill dropped (consolidated). */}
          {/* Clients pill hidden — see desktop nav comment above. */}
        </Box>
        {children}
      </Box>
    </Box>
  );
}

function PublicNavLink({
  href,
  icon,
  label,
}: {
  href: string;
  icon: Parameters<typeof NavIcon>[0]["name"];
  label: string;
}) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Button
        size="small"
        variant="outlined"
        startIcon={<NavIcon name={icon} />}
        sx={{
          borderRadius: 2.5,
          borderColor: "var(--app-control-border)",
          bgcolor: "var(--app-control-bg)",
          color: "var(--app-muted)",
          fontSize: 11,
          fontWeight: 900,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
        }}
      >
        {label}
      </Button>
    </Link>
  );
}

function MobilePill({
  href,
  icon,
  label,
}: {
  href: string;
  icon: Parameters<typeof NavIcon>[0]["name"];
  label: string;
}) {
  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Button
        size="small"
        variant="outlined"
        startIcon={<NavIcon name={icon} />}
        sx={{
          borderRadius: 2.5,
          borderColor: "var(--app-control-border)",
          bgcolor: "var(--app-control-bg)",
          color: "var(--app-muted)",
          fontSize: 11,
          fontWeight: 900,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
        }}
      >
        {label}
      </Button>
    </Link>
  );
}

