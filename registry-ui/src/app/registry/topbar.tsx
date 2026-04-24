"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppBar, Box, ButtonBase, IconButton, Toolbar, Typography } from "@mui/material";

import { NavIcon } from "@/components/security";

import { RegistryNotifications } from "./RegistryNotifications";

export function RegistryTopBar({
  authEnabled,
  hasSession,
  canSubmit,
  canReview,
  canAdmin,
  cliActive,
  healthActive,
  settingsActive,
  onMenuToggle,
  menuOpen,
  onBrandClick,
}: {
  authEnabled: boolean;
  hasSession: boolean;
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
  cliActive?: boolean;
  healthActive?: boolean;
  settingsActive?: boolean;
  onMenuToggle?: () => void;
  menuOpen?: boolean;
  onBrandClick?: () => void;
}) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const actionFx =
    "transition active:translate-y-[1px] active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[--app-accent] focus-visible:ring-offset-2 focus-visible:ring-offset-[--app-chrome-bg]";
  const roleLabel = !authEnabled
    ? "OPEN"
    : !hasSession
      ? "GUEST"
    : canAdmin
      ? "ADMIN"
      : canReview
        ? "REVIEWER"
        : canSubmit
          ? "PUBLISHER"
          : "VIEWER";

  async function handleLogout() {
    setSigningOut(true);
    try {
      await fetch("/api/logout", { method: "POST" });
    } catch {
      // ignore – we still send the user back to login
    }
    router.push("/login");
  }

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        height: 56,
        bgcolor: "var(--app-chrome-bg)",
        color: "var(--app-fg)",
        borderBottom: "1px solid var(--app-chrome-border)",
      }}
    >
      <Toolbar sx={{ minHeight: 56, px: 2, gap: 1.5 }}>
        <IconButton
          onClick={onMenuToggle}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          sx={{
            display: { xs: "inline-flex", sm: "none" },
            border: "1px solid var(--app-control-border)",
            bgcolor: "var(--app-control-bg)",
          }}
        >
          <Typography variant="overline" sx={{ letterSpacing: "0.12em" }}>
            {menuOpen ? "Close" : "Menu"}
          </Typography>
        </IconButton>

        <ButtonBase
          onClick={onBrandClick}
          sx={{
            borderRadius: 3,
            px: 0.5,
            py: 0.5,
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            "&:hover": { bgcolor: "var(--app-hover-bg)" },
          }}
          aria-label="Toggle sidebar"
        >
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              display: "grid",
              placeItems: "center",
              fontSize: 11,
              fontWeight: 900,
              letterSpacing: "0.16em",
            }}
          >
            PC
          </Box>
          <Box sx={{ lineHeight: 1.1, minWidth: 0, display: { xs: "none", sm: "block" } }}>
            <Typography
              noWrap
              variant="overline"
              sx={{ letterSpacing: "0.18em", color: "var(--app-muted)" }}
            >
              PureCipher
            </Typography>
            <Typography noWrap variant="body2" sx={{ color: "var(--app-fg)" }}>
              Secured MCP Registry
            </Typography>
          </Box>
        </ButtonBase>

        <Box sx={{ flex: 1 }} />

        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <TopAction href="/public/tools" label="Public">
            <NavIcon name="tools" className="h-4 w-4" />
          </TopAction>

          {!authEnabled || hasSession ? (
            <Box sx={{ display: { xs: "none", sm: "block" } }}>
              <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
                <RegistryNotifications />
                <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--app-muted)" }}>
                  Notify
                </Typography>
              </Box>
            </Box>
          ) : (
            <TopAction href="/login" label="Notify">
              <NavIcon name="notify" className="h-4 w-4" />
            </TopAction>
          )}

          <Box sx={{ display: { xs: "none", sm: "block" } }}>
            <TopAction href="/registry/cli" label="CLI" active={!!cliActive}>
              <NavIcon name="cli" className="h-4 w-4" />
            </TopAction>
          </Box>
          <TopAction href="/registry/health" label="Health" active={!!healthActive}>
            <NavIcon name="health" className="h-4 w-4" />
          </TopAction>
          <TopAction href="/registry/settings" label="Settings" active={!!settingsActive}>
            <NavIcon name="settings" className="h-4 w-4" />
          </TopAction>

          <Box sx={{ display: { xs: "none", sm: "block" } }}>
            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
              <Box
                sx={{
                  px: 1.2,
                  py: 0.4,
                  borderRadius: 999,
                  bgcolor: "var(--app-control-active-bg)",
                  border: "1px solid var(--app-control-border)",
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                {roleLabel}
              </Box>
              <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--app-muted)" }}>
                Role
              </Typography>
            </Box>
          </Box>

          {authEnabled && hasSession ? (
            <Box sx={{ display: { xs: "none", sm: "flex" }, flexDirection: "column", alignItems: "center", gap: 0.5 }}>
              <IconButton
                onClick={handleLogout}
                disabled={signingOut}
                aria-label="Sign out"
                sx={{
                  border: "1px solid var(--app-accent)",
                  color: "var(--app-muted)",
                  "&:hover": { bgcolor: "var(--app-control-active-bg)" },
                }}
              >
                <NavIcon name="access" className="h-4 w-4" />
              </IconButton>
              <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--app-muted)" }}>
                {signingOut ? "…" : "Sign out"}
              </Typography>
            </Box>
          ) : authEnabled ? (
            <Box sx={{ display: { xs: "none", sm: "flex" }, flexDirection: "column", alignItems: "center", gap: 0.5 }}>
              <Link href="/login" legacyBehavior passHref>
                <IconButton
                  component="a"
                  aria-label="Sign in"
                  sx={{
                    border: "1px solid var(--app-accent)",
                    color: "var(--app-muted)",
                    "&:hover": { bgcolor: "var(--app-control-active-bg)" },
                  }}
                >
                  <NavIcon name="access" className="h-4 w-4" />
                </IconButton>
              </Link>
              <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--app-muted)" }}>
                Sign in
              </Typography>
            </Box>
          ) : null}
        </Box>
      </Toolbar>
    </AppBar>
  );
}

function TopAction({
  href,
  label,
  active,
  children,
}: {
  href: string;
  label: string;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: { xs: "none", sm: "flex" }, flexDirection: "column", alignItems: "center", gap: 0.5 }}>
      <Link href={href} legacyBehavior passHref>
        <IconButton
          component="a"
          sx={{
            border: "1px solid",
            borderColor: active ? "var(--app-accent)" : "var(--app-control-border)",
            bgcolor: active ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
            color: active ? "var(--app-fg)" : "var(--app-muted)",
            "&:hover": { bgcolor: "var(--app-hover-bg)" },
          }}
        >
          {children}
        </IconButton>
      </Link>
      <Typography variant="caption" sx={{ textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--app-muted)" }}>
        {label}
      </Typography>
    </Box>
  );
}
