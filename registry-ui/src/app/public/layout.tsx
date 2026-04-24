import type { ReactNode } from "react";
import Link from "next/link";

import { NavIcon } from "@/components/security";
import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";

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
          backgroundImage: "none",
        }}
      >
        <Toolbar sx={{ px: 2 }}>
          <Container maxWidth="lg" disableGutters sx={{ display: "flex", alignItems: "center", gap: 2 }}>
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
              <PublicNavLink href="/public/servers" icon="servers" label="Servers" />
              <PublicNavLink href="/public/clients" icon="clients" label="Clients" />
            </Box>

            <Box sx={{ ml: "auto", display: "flex", alignItems: "center", gap: 1 }}>
              <Link href={signInUrl} style={{ textDecoration: "none" }}>
                <Button
                  size="small"
                  variant="outlined"
                  sx={{
                    borderRadius: 999,
                    borderColor: "var(--app-accent)",
                    color: "var(--app-muted)",
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
                    borderRadius: 999,
                    borderColor: "var(--app-control-border)",
                    bgcolor: "var(--app-control-bg)",
                    color: "var(--app-muted)",
                    "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-control-border)" },
                  }}
                >
                  Console
                </Button>
              </Link>
            </Box>
          </Container>
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: { xs: 3, sm: 4 } }}>
        <Box sx={{ mb: 2, display: { xs: "flex", sm: "none" }, flexWrap: "wrap", gap: 1 }}>
          <MobilePill href="/public/tools" icon="tools" label="Tools" />
          <MobilePill href="/public/publishers" icon="publishers" label="Publishers" />
          <MobilePill href="/public/servers" icon="servers" label="Servers" />
          <MobilePill href="/public/clients" icon="clients" label="Clients" />
        </Box>
        {children}
      </Container>
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
          borderRadius: 999,
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
          borderRadius: 999,
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

