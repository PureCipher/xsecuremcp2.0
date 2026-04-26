import Link from "next/link";
import { getRegistryHealth, getRegistrySession } from "@/lib/registryClient";

import { Box, Button, Card, CardContent, Chip, Divider, Typography } from "@mui/material";
import { RegistryPageHeader } from "@/components/security";

import { AccountSecurityPanel } from "./AccountSecurityPanel";
import { AppThemePreferencesPanel } from "./AppThemePreferencesPanel";
import { UserPreferencesPanel } from "./UserPreferencesPanel";

type SettingsCardModel = {
  title: string;
  description: string;
  status: string;
  href?: string;
  actionLabel?: string;
};

export default async function RegistrySettingsPage() {
  const [health, sessionPayload] = await Promise.all([
    getRegistryHealth(),
    getRegistrySession(),
  ]);
  const authEnabled = sessionPayload?.auth_enabled !== false;
  const session = sessionPayload?.session ?? null;
  const role = authEnabled ? (session?.role ?? "guest") : "open";
  const roleLabel = role === "open" ? "Open local registry" : titleCase(role);
  const canSubmit = authEnabled ? (session?.can_submit ?? false) : true;
  const canReview = authEnabled ? (session?.can_review ?? false) : true;
  const canAdmin = authEnabled ? (session?.can_admin ?? false) : true;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <RegistryPageHeader
        eyebrow="Profile settings"
        title="Workspace preferences"
        description="Review your registry profile and interface appearance. Policy changes remain in the dedicated Policy Kernel."
      />

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
                Profile workspace
              </Typography>
              <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
                {roleLabel} preferences
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Tune account, workspace, and role-specific controls for this registry profile. Items marked backend required need API support before activation.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Chip label={session?.username ?? (authEnabled ? "Guest" : "Local mode")} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
              <Chip label={health?.auth_enabled ? "Auth enabled" : "Open access"} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
              <Chip label={health?.require_moderation ? "Moderation on" : "Moderation off"} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
              <Chip label={`Min: ${health?.minimum_certification ?? "unknown"}`} sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} />
            </Box>
          </Box>

          <Divider />

          <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gap: 2 }}>
            {health ? (
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" } }}>
                <ProfileStat title="Account" value={session?.display_name ?? session?.username ?? roleLabel} detail={`Role: ${roleLabel}`} />
                <ProfileStat title="Authentication" value={health.auth_enabled ? "Enabled" : "Disabled"} detail={health.issuer_id ? `Issuer: ${health.issuer_id}` : "No issuer reported"} />
                <ProfileStat title="Moderation" value={health.require_moderation ? "Required" : "Optional"} detail={`Minimum listing level: ${health.minimum_certification ?? "unknown"}`} />
              </Box>
            ) : (
              <Box sx={{ p: 2.5, borderRadius: 3, border: "1px solid var(--app-border)", bgcolor: "var(--app-control-bg)" }}>
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
                  Registry settings unavailable
                </Typography>
                <Typography sx={{ mt: 0.75, fontSize: 12, color: "var(--app-muted)" }}>
                  Unable to load settings from the registry. Check that the registry is running and reachable.
                </Typography>
              </Box>
            )}
          </Box>

          <Divider />

          <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gap: 2 }}>
            <SectionHeader
              eyebrow="Account security"
              title="Password, sessions, and access keys"
              description="Live session controls plus a precise view of what password and token features need from the backend."
            />
            <AccountSecurityPanel authEnabled={authEnabled} session={session} />

            <Divider />

            <SectionHeader
              eyebrow="Workspace"
              title="Interface preferences"
              description="Server-synced preferences now drive navigation, notifications, publishing, review, and admin shortcuts."
            />
            <AppThemePreferencesPanel />
            <UserPreferencesPanel
              canSubmit={canSubmit}
              canReview={canReview}
              canAdmin={canAdmin}
            />

            <Divider />

            <SectionHeader
              eyebrow="Role settings"
              title={`${roleLabel} controls`}
              description="Role-specific settings are shown based on the current registry session and capability flags."
            />
            <RoleSettingsGrid
              role={role}
              canSubmit={canSubmit}
              canReview={canReview}
              canAdmin={canAdmin}
            />
          </Box>

          <Divider />

          <Box sx={{ px: { xs: 2.5, md: 3 }, py: 1.75, bgcolor: "var(--app-control-bg)" }}>
            <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
              Manage live rules in{" "}
              <Link href="/registry/policy" style={{ color: "inherit", textDecoration: "underline", textUnderlineOffset: 3 }}>
                Policy Kernel
              </Link>
              . Review service status in{" "}
              <Link href="/registry/health" style={{ color: "inherit", textDecoration: "underline", textUnderlineOffset: 3 }}>
                Health
              </Link>
              .
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

function ProfileStat({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
      }}
    >
      <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--app-muted)" }}>
        {title}
      </Typography>
      <Typography sx={{ mt: 1, fontSize: 18, lineHeight: 1, fontWeight: 850, color: "var(--app-fg)" }}>
        {value}
      </Typography>
      <Typography sx={{ mt: 0.75, fontSize: 12, color: "var(--app-muted)", wordBreak: "break-word" }}>
        {detail}
      </Typography>
    </Box>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <Box sx={{ display: "grid", gap: 0.5, maxWidth: 780 }}>
      <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
        {eyebrow}
      </Typography>
      <Typography sx={{ fontSize: 16, fontWeight: 850, color: "var(--app-fg)" }}>
        {title}
      </Typography>
      <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
        {description}
      </Typography>
    </Box>
  );
}

function SettingsActionCard({
  title,
  description,
  status,
  href,
  actionLabel,
}: {
  title: string;
  description: string;
  status: string;
  href?: string;
  actionLabel?: string;
}) {
  const content = (
    <Box
      sx={{
        height: "100%",
        p: 2,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 1.25,
        alignContent: "space-between",
      }}
    >
      <Box>
        <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1.5 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 850, color: "var(--app-fg)" }}>
            {title}
          </Typography>
          <Chip
            size="small"
            label={status}
            sx={{
              bgcolor: status === "Available" ? "var(--app-control-active-bg)" : "var(--app-surface)",
              color: "var(--app-muted)",
              fontSize: 10,
              fontWeight: 800,
            }}
          />
        </Box>
        <Typography sx={{ mt: 0.75, fontSize: 12, lineHeight: 1.55, color: "var(--app-muted)" }}>
          {description}
        </Typography>
      </Box>
      {href ? (
        <Button component="span" size="small" variant="outlined" sx={{ justifySelf: "start" }}>
          {actionLabel ?? "Open"}
        </Button>
      ) : null}
    </Box>
  );

  if (!href) return content;

  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      {content}
    </Link>
  );
}

function RoleSettingsGrid({
  role,
  canSubmit,
  canReview,
  canAdmin,
}: {
  role: string;
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
}) {
  const common: SettingsCardModel[] = [];

  const publisher: SettingsCardModel[] = canSubmit
    ? [
        {
          title: "Publisher profile",
          description: "Manage organization name, support contact, and publisher metadata.",
          status: "Available",
          href: "/registry/publishers",
          actionLabel: "View publishers",
        },
        {
          title: "Publishing defaults",
          description: "Default certification target is now stored locally above. Server and OpenAPI defaults still need backend profile storage.",
          status: "Partially available",
        },
        {
          title: "Signing material",
          description: "Show publisher key fingerprint and guide key rotation.",
          status: "Backend required",
        },
      ]
    : [];

  const reviewer: SettingsCardModel[] = canReview
    ? [
        {
          title: "Review queue preferences",
          description: "Default review lane and high-risk preference are now stored locally above.",
          status: "Available",
          href: "/registry/review",
          actionLabel: "Open queue",
        },
        {
          title: "Decision templates",
          description: "Reusable approval, rejection, and needs-changes notes for consistent reviews.",
          status: "Planned",
        },
        {
          title: "Reviewer identity",
          description: "Configure display name/signature used in moderation audit logs.",
          status: "Backend required",
        },
      ]
    : [];

  const admin: SettingsCardModel[] = canAdmin
    ? [
        {
          title: "User management",
          description: "Invite users, assign roles, deactivate accounts, and force password resets.",
          status: "Available",
          href: "/registry/access",
          actionLabel: "Open users",
        },
        {
          title: "Password policy",
          description: "Set minimum password rules, reset expiry, session lifetime, and lockout policy.",
          status: "Backend required",
        },
        {
          title: "Security controls",
          description: "Configure token expiry, audit retention, and key rotation reminders.",
          status: "Backend required",
        },
        {
          title: "Registry policy",
          description: "Manage live access rules, policy bundles, proposals, and rollback controls.",
          status: "Available",
          href: "/registry/policy",
          actionLabel: "Open policy",
        },
        {
          title: "Control planes",
          description: "Toggle the four opt-in SecureMCP control planes (Contract Broker, Consent Graph, Provenance Ledger, Reflexive Core) on or off at runtime. Persisted across restart.",
          status: "Available",
          href: "/registry/settings/control-planes",
          actionLabel: "Manage planes",
        },
      ]
    : [];

  const roleCards: SettingsCardModel[] = [...common, ...publisher, ...reviewer, ...admin];

  return (
    <Box sx={{ display: "grid", gap: 1.5 }}>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
        <Chip label={`Current role: ${titleCase(role)}`} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
        {canSubmit ? <Chip label="Publisher capability" sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} /> : null}
        {canReview ? <Chip label="Reviewer capability" sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} /> : null}
        {canAdmin ? <Chip label="Admin capability" sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }} /> : null}
      </Box>

      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))", xl: "repeat(3, minmax(0, 1fr))" } }}>
        {roleCards.map((card) => (
          <SettingsActionCard
            key={`${card.title}-${card.status}`}
            title={card.title}
            description={card.description}
            status={card.status}
            href={card.href}
            actionLabel={card.actionLabel}
          />
        ))}
      </Box>
    </Box>
  );
}

function titleCase(value: string) {
  if (!value) return "Unknown";
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
