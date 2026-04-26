"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, Divider, FormControl, FormControlLabel, InputLabel, MenuItem, Select, Switch, Typography } from "@mui/material";

import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";

export function UserPreferencesPanel({
  canSubmit,
  canReview,
  canAdmin,
}: {
  canSubmit: boolean;
  canReview: boolean;
  canAdmin: boolean;
}) {
  const router = useRouter();
  const { prefs, updateSection, resetPrefs, serverStatus, serverError } = useRegistryUserPreferences();
  const storageLabel =
    serverStatus === "synced"
      ? "Stored on server"
      : serverStatus === "syncing"
        ? "Syncing"
        : serverStatus === "local"
          ? "Local fallback"
          : "Loading";

  return (
    <Card variant="outlined" component="section" sx={{ overflow: "hidden" }}>
      <CardContent sx={{ p: 0 }}>
        <Box
          sx={{
            p: { xs: 2, md: 2.5 },
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          <Box sx={{ display: "grid", gap: 0.6, maxWidth: 760 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              User preferences
            </Typography>
            <Typography sx={{ fontSize: 16, fontWeight: 850, color: "var(--app-fg)" }}>
              Notifications, defaults, and role workflow preferences
            </Typography>
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Preferences sync to your registry account and fall back to this browser if the server is unavailable.
            </Typography>
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignSelf: { xs: "flex-start", md: "center" } }}>
            <Chip label={storageLabel} sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
            <Button size="small" variant="outlined" onClick={resetPrefs}>Reset</Button>
          </Box>
        </Box>

        <Divider />

        <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 2 }}>
          {serverStatus === "local" && serverError ? (
            <Alert severity="info" sx={{ borderRadius: 3 }}>
              Server preferences are unavailable right now, so changes are saved locally. {serverError}
            </Alert>
          ) : null}

          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
            <PreferenceGroup title="Notification preferences" badge={storageLabel}>
              <PreferenceSwitch
                label="Publisher updates"
                description="Submission approved, rejected, or needs changes."
                checked={prefs.notifications.publishUpdates}
                onChange={(value) => updateSection("notifications", { publishUpdates: value })}
              />
              <PreferenceSwitch
                label="Review queue"
                description="New submissions, resubmissions, and review escalations."
                checked={prefs.notifications.reviewQueue}
                onChange={(value) => updateSection("notifications", { reviewQueue: value })}
              />
              <PreferenceSwitch
                label="Policy changes"
                description="Proposal, deployment, rollback, and governance changes."
                checked={prefs.notifications.policyChanges}
                onChange={(value) => updateSection("notifications", { policyChanges: value })}
              />
              <PreferenceSwitch
                label="Security alerts"
                description="Revocations, health issues, and high-risk registry events."
                checked={prefs.notifications.securityAlerts}
                onChange={(value) => updateSection("notifications", { securityAlerts: value })}
              />
            </PreferenceGroup>

            <PreferenceGroup title="Workspace defaults" badge={storageLabel}>
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                <FormControl size="small" fullWidth>
                  <InputLabel id="default-landing-label">Default landing</InputLabel>
                  <Select
                    labelId="default-landing-label"
                    label="Default landing"
                    value={prefs.workspace.defaultLandingPage}
                    onChange={(event) => updateSection("workspace", { defaultLandingPage: event.target.value })}
                  >
                    <MenuItem value="/registry/app">Tools</MenuItem>
                    <MenuItem value="/registry/publish/mine">Publisher listings</MenuItem>
                    <MenuItem value="/registry/review">Review queue</MenuItem>
                    <MenuItem value="/registry/health">Health</MenuItem>
                    <MenuItem value="/registry/settings">Settings</MenuItem>
                  </Select>
                </FormControl>

                <FormControl size="small" fullWidth>
                  <InputLabel id="density-label">Density</InputLabel>
                  <Select
                    labelId="density-label"
                    label="Density"
                    value={prefs.workspace.density}
                    onChange={(event) => updateSection("workspace", { density: event.target.value as "comfortable" | "compact" })}
                  >
                    <MenuItem value="comfortable">Comfortable</MenuItem>
                    <MenuItem value="compact">Compact</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Default landing is honored after sign-in. Density adjusts vertical rhythm across cards, tables, and list items.
              </Typography>
            </PreferenceGroup>
          </Box>

          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "repeat(3, minmax(0, 1fr))" } }}>
            {canSubmit ? (
              <PreferenceGroup title="Publisher defaults" badge="Publisher">
                <FormControl size="small" fullWidth>
                  <InputLabel id="publisher-certification-label">Certification target</InputLabel>
                  <Select
                    labelId="publisher-certification-label"
                    label="Certification target"
                    value={prefs.publisher.defaultCertification}
                    onChange={(event) => updateSection("publisher", { defaultCertification: event.target.value as "basic" | "standard" | "advanced" })}
                  >
                    <MenuItem value="basic">Basic</MenuItem>
                    <MenuItem value="standard">Standard</MenuItem>
                    <MenuItem value="advanced">Advanced</MenuItem>
                  </Select>
                </FormControl>
                <PreferenceSwitch
                  label="Open my listings first"
                  description="Prefer publisher-owned listing view when entering publish workflows."
                  checked={prefs.publisher.openMineFirst}
                  onChange={(value) => updateSection("publisher", { openMineFirst: value })}
                />
              </PreferenceGroup>
            ) : null}

            {canReview ? (
              <PreferenceGroup title="Reviewer defaults" badge="Reviewer">
                <FormControl size="small" fullWidth>
                  <InputLabel id="reviewer-lane-label">Default lane</InputLabel>
                  <Select
                    labelId="reviewer-lane-label"
                    label="Default lane"
                    value={prefs.reviewer.defaultLane}
                    onChange={(event) => updateSection("reviewer", { defaultLane: event.target.value as "pending" | "approved" | "rejected" })}
                  >
                    <MenuItem value="pending">Pending</MenuItem>
                    <MenuItem value="approved">Approved</MenuItem>
                    <MenuItem value="rejected">Rejected</MenuItem>
                  </Select>
                </FormControl>
                <PreferenceSwitch
                  label="High risk first"
                  description="Prioritize items needing closer reviewer attention."
                  checked={prefs.reviewer.highRiskFirst}
                  onChange={(value) => updateSection("reviewer", { highRiskFirst: value })}
                />
              </PreferenceGroup>
            ) : null}

            {canAdmin ? (
              <PreferenceGroup title="Admin defaults" badge="Admin">
                <FormControl size="small" fullWidth>
                  <InputLabel id="admin-view-label">Default admin view</InputLabel>
                  <Select
                    labelId="admin-view-label"
                    label="Default admin view"
                    value={prefs.admin.defaultAdminView}
                    onChange={(event) => updateSection("admin", { defaultAdminView: event.target.value as "health" | "policy" | "settings" })}
                  >
                    <MenuItem value="health">Health</MenuItem>
                    <MenuItem value="policy">Policy Kernel</MenuItem>
                    <MenuItem value="settings">Settings</MenuItem>
                  </Select>
                </FormControl>
                <PreferenceSwitch
                  label="Require confirmations"
                  description="Keep extra confirmation steps for destructive admin actions."
                  checked={prefs.admin.requireConfirmations}
                  onChange={(value) => updateSection("admin", { requireConfirmations: value })}
                />
                <Button
                  type="button"
                  variant="outlined"
                  onClick={() => router.push(adminDefaultPath(prefs.admin.defaultAdminView))}
                  sx={{ justifySelf: "start", textTransform: "none" }}
                >
                  Open default admin view
                </Button>
              </PreferenceGroup>
            ) : null}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

function adminDefaultPath(view: "health" | "policy" | "settings") {
  if (view === "policy") return "/registry/policy";
  if (view === "settings") return "/registry/settings";
  return "/registry/health";
}

function PreferenceGroup({
  title,
  badge,
  children,
}: {
  title: string;
  badge: string;
  children: ReactNode;
}) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 3,
        border: "1px solid var(--app-border)",
        bgcolor: "var(--app-control-bg)",
        display: "grid",
        gap: 1.5,
        alignContent: "start",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 850, color: "var(--app-fg)" }}>
          {title}
        </Typography>
        <Chip size="small" label={badge} sx={{ bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800 }} />
      </Box>
      {children}
    </Box>
  );
}

function PreferenceSwitch({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
      <Box>
        <Typography sx={{ fontSize: 13, fontWeight: 750, color: "var(--app-fg)" }}>
          {label}
        </Typography>
        <Typography sx={{ mt: 0.25, fontSize: 12, lineHeight: 1.45, color: "var(--app-muted)" }}>
          {description}
        </Typography>
      </Box>
      <FormControlLabel
        control={<Switch checked={checked} onChange={(event) => onChange(event.target.checked)} />}
        label=""
        sx={{ m: 0 }}
      />
    </Box>
  );
}
