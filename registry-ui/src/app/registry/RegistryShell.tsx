"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect, useMemo, useState } from "react";

import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Toolbar,
  Typography,
} from "@mui/material";

import { NavIcon } from "@/components/security";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";
import type { RegistryPersonaId } from "@/lib/registryPersona";
import { RegistryTopBar } from "./topbar";

type Props = {
  authEnabled: boolean;
  hasSession: boolean;
  persona: RegistryPersonaId;
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
  /** Sidebar + publish page: publisher and admin only when auth is on. */
  canPublishConsole: boolean;
  publisherHasListings: boolean;
  children: React.ReactNode;
};

type NavItem = {
  href: string;
  label: string;
  icon: Parameters<typeof NavIcon>[0]["name"];
  enabled: boolean;
  active: boolean;
};

export function RegistryShell({
  authEnabled,
  hasSession,
  persona,
  canSubmit,
  canReview,
  canAdmin,
  canPublishConsole,
  publisherHasListings,
  children,
}: Props) {
  const pathname = usePathname();
  const { prefs } = useRegistryUserPreferences();
  const publisherOnly = canPublishConsole && !canReview && !canAdmin;
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const year = new Date().getFullYear();

  useLayoutEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.registryPersona = persona;
    return () => {
      document.documentElement.removeAttribute("data-registry-persona");
    };
  }, [persona]);

  const catalogItems: NavItem[] = useMemo(
    () => [
      {
        href: "/registry/app",
        label: "Tools",
        icon: "tools",
        enabled: !publisherOnly,
        active: pathname.startsWith("/registry/app"),
      },
      {
        href: "/registry/publishers",
        label: "Publishers",
        icon: "publishers",
        enabled: !publisherOnly,
        active: pathname.startsWith("/registry/publishers"),
      },
      {
        href: "/registry/servers",
        label: "MCP Servers",
        icon: "servers",
        enabled: canAdmin || (!canPublishConsole && !canReview),
        active: pathname.startsWith("/registry/servers"),
      },
      // /registry/clients is gated behind NEXT_PUBLIC_REGISTRY_SHOW_CLIENTS
      // until the onboard wizard's "coming soon" buttons are wired up.
      // Surfacing the link to a dead-end wizard erodes user trust.
      {
        href: "/registry/clients",
        label: "Clients",
        icon: "clients",
        enabled:
          (canAdmin || (!canPublishConsole && !canReview)) &&
          process.env.NEXT_PUBLIC_REGISTRY_SHOW_CLIENTS === "1",
        active: pathname.startsWith("/registry/clients"),
      },
    ],
    [pathname, canPublishConsole, canReview, canAdmin, publisherOnly],
  );

  const publisherItems: NavItem[] = useMemo(
    () => {
      const mine: NavItem = {
        href: "/registry/publish/mine",
        label: "My listings",
        icon: "tools",
        enabled: canPublishConsole,
        active: pathname.startsWith("/registry/publish/mine"),
      };
      const getStarted: NavItem = {
        href: "/registry/publish/get-started",
        label: "Get started",
        icon: "publish",
        enabled: canPublishConsole && !publisherHasListings,
        active: pathname.startsWith("/registry/publish/get-started"),
      };
      const publish: NavItem = {
        href: "/registry/publish",
        label: "Publish",
        icon: "publish",
        enabled: canPublishConsole,
        active:
          pathname.startsWith("/registry/publish") &&
          !pathname.startsWith("/registry/publish/get-started") &&
          !pathname.startsWith("/registry/publish/mine"),
      };
      const onboard: NavItem = {
        href: "/registry/onboard",
        label: "Onboard third-party",
        icon: "publish",
        enabled: canPublishConsole,
        active: pathname.startsWith("/registry/onboard"),
      };
      const ordered = prefs.publisher.openMineFirst
        ? [mine, getStarted, publish, onboard]
        : [publish, getStarted, mine, onboard];
      return ordered;
    },
    [pathname, canPublishConsole, publisherHasListings, prefs.publisher.openMineFirst],
  );

  const reviewerItems: NavItem[] = useMemo(
    () => [
      {
        href: "/registry/review",
        label: "Review",
        icon: "review",
        enabled: canReview,
        active: pathname.startsWith("/registry/review"),
      },
      {
        href: "/registry/policy",
        label: "Policy Kernel",
        icon: "policy",
        enabled: canReview,
        active: pathname.startsWith("/registry/policy"),
      },
      {
        href: "/registry/provenance",
        label: "Provenance Ledger",
        icon: "provenance",
        enabled: canReview,
        active: pathname.startsWith("/registry/provenance"),
      },
    ],
    [pathname, canReview],
  );

  const adminItems: NavItem[] = useMemo(
    () => [
      {
        href: "/registry/access",
        label: "Access Studio",
        icon: "access",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/access"),
      },
      {
        href: "/registry/contracts",
        label: "Contract Broker",
        icon: "contracts",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/contracts"),
      },
      {
        href: "/registry/reflexive",
        label: "Reflexive Core",
        icon: "reflexive",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/reflexive"),
      },
      {
        href: "/registry/consent",
        label: "Consent Graph",
        icon: "consent",
        enabled: canAdmin,
        active: pathname.startsWith("/registry/consent"),
      },
    ],
    [pathname, canAdmin],
  );

  function closeMobileSidebar() {
    setMobileSidebarOpen(false);
  }

  const drawerExpanded = 240;
  const drawerCollapsed = 76;
  const drawerWidth = sidebarCollapsed ? drawerCollapsed : drawerExpanded;

  function renderNavSection(
    title: string,
    items: NavItem[],
    opts?: { onNavigate?: () => void; collapsed?: boolean },
  ) {
    const collapsed = opts?.collapsed ?? false;
    const visible = items.filter((i) => i.enabled);
    if (visible.length === 0) return null;

    return (
      <List
        dense
        subheader={
          <ListSubheader
            component="div"
            sx={{
              bgcolor: "transparent",
              color: "var(--app-muted)",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              lineHeight: 1,
              pb: 0.75,
            }}
          >
            {collapsed ? " " : title}
          </ListSubheader>
        }
        sx={{ px: 1 }}
      >
        {visible.map((item) => (
          <ListItemButton
            key={item.href}
            component="a"
            href={item.href}
            onClick={opts?.onNavigate}
            selected={item.active}
            sx={{
              borderRadius: 2.5,
              mb: 0.35,
              py: 1,
              minHeight: 42,
              "&.Mui-selected": { bgcolor: "var(--app-control-active-bg)" },
              "&.Mui-selected:hover": { bgcolor: "var(--app-control-active-bg)" },
              "&:hover": { bgcolor: "var(--app-hover-bg)" },
              color: item.active ? "var(--app-fg)" : "var(--app-muted)",
            }}
          >
            <ListItemIcon sx={{ minWidth: collapsed ? 0 : 40, mr: collapsed ? 0 : 0.5, color: "inherit" }}>
              <NavIcon name={item.icon} />
            </ListItemIcon>
            {collapsed ? null : (
              <ListItemText
                primary={
                  <Typography component="span" sx={{ fontSize: 13, fontWeight: item.active ? 700 : 600 }}>
                    {item.label}
                  </Typography>
                }
              />
            )}
          </ListItemButton>
        ))}
      </List>
    );
  }

  return (
    <Box sx={{ height: "100vh", bgcolor: "var(--app-bg)", color: "var(--app-fg)" }}>
      <RegistryTopBar
        authEnabled={authEnabled}
        hasSession={hasSession}
        canSubmit={canSubmit}
        canReview={canReview}
        canAdmin={canAdmin}
        cliActive={pathname.startsWith("/registry/cli")}
        healthActive={pathname.startsWith("/registry/health")}
        settingsActive={pathname.startsWith("/registry/settings")}
        onMenuToggle={() => setMobileSidebarOpen((open) => !open)}
        menuOpen={mobileSidebarOpen}
        onBrandClick={() => {
          if (typeof window !== "undefined" && window.innerWidth < 640) {
            setMobileSidebarOpen((open) => !open);
          } else {
            setSidebarCollapsed((collapsed) => !collapsed);
          }
        }}
      />

      <Box
        sx={{
          position: "fixed",
          top: 64,
          bottom: 36,
          left: 0,
          right: 0,
          display: "flex",
          overflow: "hidden",
        }}
      >
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: "none", sm: "block" },
            width: drawerWidth,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: drawerWidth,
              boxSizing: "border-box",
              bgcolor: "var(--app-chrome-bg)",
              borderRight: "1px solid var(--app-chrome-border)",
              color: "var(--app-fg)",
              boxShadow: "12px 0 30px rgba(15, 23, 42, 0.03)",
            },
          }}
        >
          <Toolbar sx={{ minHeight: 8 }} />
          <Box sx={{ px: 1.25, pt: 1.5, display: "grid", gap: 1.75 }}>
            {renderNavSection("Catalog", catalogItems, { collapsed: sidebarCollapsed })}
            {renderNavSection("Publisher", publisherItems, { collapsed: sidebarCollapsed })}
            {renderNavSection("Reviewer", reviewerItems, { collapsed: sidebarCollapsed })}
            {renderNavSection("Admin", adminItems, { collapsed: sidebarCollapsed })}
          </Box>
        </Drawer>

        <Drawer
          variant="temporary"
          open={mobileSidebarOpen}
          onClose={closeMobileSidebar}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", sm: "none" },
            "& .MuiDrawer-paper": {
              width: 280,
              bgcolor: "var(--app-chrome-bg)",
              color: "var(--app-fg)",
              borderRight: "1px solid var(--app-chrome-border)",
            },
          }}
        >
          <Toolbar sx={{ minHeight: 8 }} />
          <Box sx={{ px: 1.25, pt: 1.5, display: "grid", gap: 1.75 }}>
            {renderNavSection("Catalog", catalogItems, { onNavigate: closeMobileSidebar })}
            {renderNavSection("Publisher", publisherItems, { onNavigate: closeMobileSidebar })}
            {renderNavSection("Reviewer", reviewerItems, { onNavigate: closeMobileSidebar })}
            {renderNavSection("Admin", adminItems, { onNavigate: closeMobileSidebar })}
          </Box>
        </Drawer>

        <Box
          component="main"
          sx={{
            flex: 1,
            overflowY: "auto",
            px: { xs: 2, sm: 3, lg: 4 },
            py: { xs: 2.5, sm: 3.5 },
            pb: 8,
          }}
        >
          {children}
        </Box>
      </Box>

      <Box
        component="footer"
        sx={{
          position: "fixed",
          left: 0,
          right: 0,
          bottom: 0,
          height: 36,
          borderTop: "1px solid var(--app-chrome-border)",
          bgcolor: "var(--app-chrome-bg)",
          px: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "var(--app-muted)",
          fontSize: 11,
          zIndex: 1200,
          backdropFilter: "blur(18px)",
        }}
      >
        <span>© {year} PureCipher. All rights reserved.</span>
        <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
          Secured MCP Registry
        </Box>
      </Box>
    </Box>
  );
}
