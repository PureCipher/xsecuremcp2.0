"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppBar, Box, ButtonBase, Divider, IconButton, Menu, MenuItem, Toolbar, Typography } from "@mui/material";

import { NavIcon } from "@/components/security";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";

import { RegistryNotifications } from "./RegistryNotifications";

const topActionButtonSx = {
  width: 36,
  height: 36,
  p: 0,
  border: "1px solid",
  borderRadius: 2.5,
  boxShadow: "0 8px 20px rgba(15, 23, 42, 0.06)",
};

const topActionLabelSx = {
  fontSize: 11,
  lineHeight: 1,
  fontWeight: 650,
  letterSpacing: "0.02em",
  color: "var(--app-muted)",
};

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
  const { prefs } = useRegistryUserPreferences();
  const [signingOut, setSigningOut] = useState(false);
  const [profileAnchor, setProfileAnchor] = useState<HTMLElement | null>(null);
  const profileMenuOpen = Boolean(profileAnchor);
  const preferredLanding = normalizeRegistryLanding(prefs.workspace.defaultLandingPage) ?? "/registry/app";
  const preferredLandingLabel = landingLabel(preferredLanding);
  const roleLabel = !authEnabled
    ? "Open"
    : !hasSession
      ? "Guest"
    : canAdmin
      ? "Admin"
      : canReview
        ? "Reviewer"
        : canSubmit
          ? "Publisher"
          : "Viewer";

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
        height: 64,
        bgcolor: "var(--app-chrome-bg)",
        color: "var(--app-fg)",
        borderBottom: "1px solid var(--app-chrome-border)",
        backdropFilter: "blur(18px)",
        boxShadow: "0 10px 30px rgba(15, 23, 42, 0.04)",
      }}
    >
      <Toolbar sx={{ minHeight: 64, px: { xs: 1.5, sm: 2.5 }, gap: 1.5 }}>
        <IconButton
          onClick={onMenuToggle}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          sx={{
            display: { xs: "inline-flex", sm: "none" },
            width: 36,
            height: 36,
            borderRadius: 2.5,
            border: "1px solid var(--app-control-border)",
            bgcolor: "var(--app-control-bg)",
          }}
        >
          <Typography sx={{ fontSize: 10, fontWeight: 700, lineHeight: 1 }}>
            {menuOpen ? "Close" : "Menu"}
          </Typography>
        </IconButton>

        <ButtonBase
          onClick={onBrandClick}
          sx={{
            borderRadius: 3,
            px: 0.75,
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
              borderRadius: 2.5,
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              display: "grid",
              placeItems: "center",
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: "0.02em",
              boxShadow: "0 12px 28px var(--app-active-ring)",
            }}
          >
            PC
          </Box>
          <Box sx={{ lineHeight: 1.1, minWidth: 0, display: { xs: "none", sm: "block" } }}>
            <Typography
              noWrap
              variant="overline"
              sx={{ display: "block", lineHeight: 1.1, color: "var(--app-muted)" }}
            >
              PureCipher
            </Typography>
            <Typography noWrap variant="body2" sx={{ color: "var(--app-fg)", fontWeight: 700 }}>
              Secured MCP Registry
            </Typography>
          </Box>
        </ButtonBase>

        <Box sx={{ flex: 1 }} />

        <Box sx={{ display: "flex", alignItems: "center", gap: { xs: 0.75, sm: 1.25 } }}>
          <TopAction href="/public/tools" label="Public">
            <NavIcon name="tools" className="h-4 w-4" />
          </TopAction>

          {!authEnabled || hasSession ? (
            <Box sx={{ display: { xs: "none", sm: "block" } }}>
              <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
                <RegistryNotifications />
                <Typography sx={topActionLabelSx}>
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

          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
            <IconButton
              onClick={(event) => setProfileAnchor(event.currentTarget)}
              aria-label="Open profile menu"
              aria-controls={profileMenuOpen ? "registry-profile-menu" : undefined}
              aria-haspopup="menu"
              aria-expanded={profileMenuOpen}
              sx={{
                ...topActionButtonSx,
                borderColor: profileMenuOpen || settingsActive ? "var(--app-accent)" : "var(--app-control-border)",
                bgcolor: profileMenuOpen || settingsActive ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                color: profileMenuOpen || settingsActive ? "var(--app-fg)" : "var(--app-muted)",
                "&:hover": { bgcolor: "var(--app-hover-bg)" },
              }}
            >
              <NavIcon name="access" className="h-4 w-4" />
            </IconButton>
            <Typography sx={topActionLabelSx}>
              Profile
            </Typography>
          </Box>

          <Menu
            id="registry-profile-menu"
            anchorEl={profileAnchor}
            open={profileMenuOpen}
            onClose={() => setProfileAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
            slotProps={{
              paper: {
                sx: {
                  mt: 1,
                  minWidth: 240,
                  border: "1px solid var(--app-border)",
                  borderRadius: 3,
                  bgcolor: "var(--app-surface)",
                  color: "var(--app-fg)",
                  backgroundImage: "none",
                  boxShadow: "0 22px 60px rgba(15, 23, 42, 0.16)",
                  overflow: "hidden",
                },
              },
            }}
          >
            <Box sx={{ px: 1.75, py: 1.5, bgcolor: "var(--app-control-bg)" }}>
              <Typography sx={{ fontSize: 13, fontWeight: 800, color: "var(--app-fg)" }}>
                Profile
              </Typography>
              <Typography sx={{ mt: 0.25, fontSize: 12, color: "var(--app-muted)" }}>
                {roleLabel} registry access
              </Typography>
            </Box>
            <Divider />
            <MenuItem
              onClick={() => {
                setProfileAnchor(null);
                router.push(preferredLanding);
              }}
            >
              <Box sx={{ mr: 1.25, display: "grid", placeItems: "center", color: "var(--app-muted)" }}>
                <NavIcon name="tools" className="h-4 w-4" />
              </Box>
              <Box>
                <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                  Preferred home
                </Typography>
                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                  {preferredLandingLabel}
                </Typography>
              </Box>
            </MenuItem>
            <MenuItem
              selected={settingsActive}
              onClick={() => {
                setProfileAnchor(null);
                router.push("/registry/settings");
              }}
            >
              <Box sx={{ mr: 1.25, display: "grid", placeItems: "center", color: "var(--app-muted)" }}>
                <NavIcon name="settings" className="h-4 w-4" />
              </Box>
              <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                Settings
              </Typography>
            </MenuItem>
            {authEnabled ? (
              hasSession ? (
                <MenuItem
                  disabled={signingOut}
                  onClick={() => {
                    setProfileAnchor(null);
                    void handleLogout();
                  }}
                >
                  <Box sx={{ mr: 1.25, display: "grid", placeItems: "center", color: "var(--app-muted)" }}>
                    <NavIcon name="access" className="h-4 w-4" />
                  </Box>
                  <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                    {signingOut ? "Signing out..." : "Sign out"}
                  </Typography>
                </MenuItem>
              ) : (
                <MenuItem
                  onClick={() => {
                    setProfileAnchor(null);
                    router.push("/login");
                  }}
                >
                    <Box sx={{ mr: 1.25, display: "grid", placeItems: "center", color: "var(--app-muted)" }}>
                    <NavIcon name="access" className="h-4 w-4" />
                  </Box>
                  <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                    Sign in
                  </Typography>
                </MenuItem>
              )
            ) : null}
            <Divider />
            <Box sx={{ px: 1.5, py: 1 }}>
              <Box
                sx={{
                  display: "inline-flex",
                  px: 1,
                  py: 0.45,
                  borderRadius: 2,
                  bgcolor: "var(--app-control-active-bg)",
                  border: "1px solid var(--app-control-border)",
                  fontSize: 11,
                  lineHeight: 1,
                  fontWeight: 700,
                  letterSpacing: "0.01em",
                  color: "var(--app-muted)",
                }}
              >
                {roleLabel}
              </Box>
            </Box>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

function normalizeRegistryLanding(value: string | undefined): string | null {
  if (!value?.startsWith("/registry/")) return null;
  if (value.includes("://") || value.includes("\\")) return null;
  return value;
}

function landingLabel(path: string): string {
  if (path === "/registry/publish/mine") return "Publisher listings";
  if (path === "/registry/review") return "Review queue";
  if (path === "/registry/health") return "Health";
  if (path === "/registry/settings") return "Settings";
  return "Trusted tools";
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
            ...topActionButtonSx,
            borderColor: active ? "var(--app-accent)" : "var(--app-control-border)",
            bgcolor: active ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
            color: active ? "var(--app-fg)" : "var(--app-muted)",
            "&:hover": { bgcolor: "var(--app-hover-bg)" },
          }}
        >
          {children}
        </IconButton>
      </Link>
      <Typography sx={topActionLabelSx}>
        {label}
      </Typography>
    </Box>
  );
}
