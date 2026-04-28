"use client";

import { useCallback, useMemo } from "react";
import { Box, Card, CardContent, Chip, Divider, Stack, Typography } from "@mui/material";
import type {
  PolicyAnalyticsResponse,
  PolicyGovernanceResponse,
  PolicyManagementResponse,
  PolicyPacksResponse,
  PolicyPromotionsResponse,
  PolicySchemaResponse,
  PolicySimulationScenario,
} from "@/lib/registryClient";

import { PolicyProvider } from "./contexts/PolicyContext";
import { useTabNavigation, type PolicyTabKey } from "./hooks/useTabNavigation";
import { useServerRefresh } from "./hooks/useServerRefresh";
import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";
import { usePolicyApi } from "./hooks/usePolicyApi";
import { usePolicyContext } from "./contexts/PolicyContext";

import { Banner } from "./components/Banner";
import { PolicyKernelIntroHeader } from "./components/PolicyKernelIntroHeader";
import { PolicyTabs } from "./components/PolicyTabs";
// Iter 14.16 — split the legacy OverviewTab into CatalogTab + MetricsTab.
// Iter 14.17 — Live Chain + Tools merge under "Now Live"; Versions +
// Migration merge under "Lifecycle". TabGroup hosts the sub-tabs.
import { CatalogTab } from "./components/tabs/CatalogTab";
import { MetricsTab } from "./components/tabs/MetricsTab";
import { LiveChainTab } from "./components/tabs/LiveChainTab";
import { ProposalLaneTab } from "./components/tabs/ProposalLaneTab";
import { VersionsTab } from "./components/tabs/VersionsTab";
import { ToolsTab } from "./components/tabs/ToolsTab";
import { MigrationTab } from "./components/tabs/MigrationTab";
import { TabGroup } from "./components/TabGroup";

type PolicyState = NonNullable<PolicyManagementResponse["policy"]>;
type PolicyVersionsState = NonNullable<PolicyManagementResponse["versions"]>;
type PolicySchemaState = NonNullable<PolicyManagementResponse["schema"]>;
type PolicyManagerData = Pick<
  PolicyManagementResponse,
  | "policy"
  | "versions"
  | "governance"
  | "schema"
  | "bundles"
  | "packs"
  | "analytics"
  | "environments"
  | "promotions"
  | "simulation_defaults"
>;

export function PolicyManager({
  initialData,
  currentUsername,
  currentRole,
}: {
  initialData: PolicyManagerData;
  currentUsername?: string | null;
  currentRole?: string | null;
}) {
  return (
    <PolicyProvider currentUsername={currentUsername}>
      <PolicyManagerInner initialData={initialData} currentRole={currentRole} />
    </PolicyProvider>
  );
}

// Iter 14.18 — Role → default-tab map. Each role gets a tab that
// matches its primary workflow on this page:
//
// - admin → Metrics: monitoring health is the most common admin task.
// - reviewer → Proposals: reviewers spend their time on the proposal
//   queue; landing them there saves a click.
// - publisher / viewer / unknown → Catalog: picking a bundle is the
//   most common starting point for everyone else.
//
// The user's own choice (persisted in
// ``workspace.policyKernelDefaultTab``) takes precedence over this
// map; this is only the fallback when no preference is set.
const _ROLE_DEFAULT_TAB: Record<string, PolicyTabKey> = {
  admin: "metrics",
  reviewer: "proposals",
};

const _VALID_TAB_KEYS: ReadonlySet<PolicyTabKey> = new Set<PolicyTabKey>([
  "catalog",
  "now-live",
  "proposals",
  "lifecycle",
  "metrics",
]);

function _resolveDefaultTab(
  storedPreference: string,
  role: string | null | undefined,
): PolicyTabKey {
  // Stored preference wins when valid — guards against legacy values
  // (e.g., "overview" from before Iter 14.16, or any future tab key
  // rename) silently leaving users on a missing tab.
  if (
    storedPreference &&
    (_VALID_TAB_KEYS as ReadonlySet<string>).has(storedPreference)
  ) {
    return storedPreference as PolicyTabKey;
  }
  const roleDefault = role ? _ROLE_DEFAULT_TAB[role] : undefined;
  return roleDefault ?? "catalog";
}

function PolicyManagerInner({
  initialData,
  currentRole,
}: {
  initialData: PolicyManagerData;
  currentRole?: string | null;
}) {
  const { banner, setBanner, setBusyKey, clearBanner } = usePolicyContext();
  const { refresh } = useServerRefresh();
  const { prefs, updateSection } = useRegistryUserPreferences();
  // Iter 14.18 — landing tab respects the user's last choice
  // (persisted) first, then the role default, then the universal
  // fallback ("catalog"). Computed once at mount because
  // ``useTabNavigation`` initializes its state on first render only;
  // a later preference sync from the server lands on the next visit
  // rather than yanking the curator's view mid-session.
  const initialTab = useMemo(
    () =>
      _resolveDefaultTab(
        prefs.workspace.policyKernelDefaultTab,
        currentRole,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const { activeTab, setActiveTab } = useTabNavigation(initialTab);

  // Iter 14.18 — wrap the tab-change handler so a deliberate click
  // also persists the user's pinning. Identity-equal to the
  // underlying setter when nothing has changed yet, so the existing
  // ``<PolicyTabs onTabChange>`` contract isn't disturbed.
  const handleTabChange = useCallback(
    (next: PolicyTabKey) => {
      setActiveTab(next);
      if (prefs.workspace.policyKernelDefaultTab !== next) {
        updateSection("workspace", { policyKernelDefaultTab: next });
      }
    },
    [setActiveTab, updateSection, prefs.workspace.policyKernelDefaultTab],
  );

  // ── Parse initial data ────────────────────────────────────────────
  const policy: PolicyState = initialData?.policy ?? {};
  const versionsState: PolicyVersionsState = initialData?.versions ?? {};
  const schema: PolicySchemaState = initialData?.schema ?? {};
  const governance: PolicyGovernanceResponse = initialData?.governance ?? {};
  const bundleState = initialData?.bundles ?? {};
  const packState: PolicyPacksResponse = initialData?.packs ?? {};
  const analytics: PolicyAnalyticsResponse = initialData?.analytics ?? {};
  const environmentState = initialData?.environments ?? {};
  const promotionState: PolicyPromotionsResponse = initialData?.promotions ?? {};
  const simulationDefaults: PolicySimulationScenario[] =
    initialData?.simulation_defaults ?? [];

  const versions = versionsState.versions ?? [];
  const providers = policy.providers ?? [];
  const proposals = governance.proposals ?? [];
  const currentVersion = versionsState.current_version ?? null;
  const requireApproval = governance.require_approval !== false;
  const requireSimulation = governance.require_simulation === true;
  const bundles = bundleState.bundles ?? [];
  const packs = packState.packs ?? [];
  const environments = environmentState.environments ?? [];
  const promotions = promotionState.promotions ?? [];

  const sortedVersions = useMemo(
    () =>
      versions
        .slice()
        .sort((left, right) => right.version_number - left.version_number),
    [versions],
  );
  const versionNumbers = useMemo(
    () => sortedVersions.map((v) => v.version_number),
    [sortedVersions],
  );

  const activeProposalCount = useMemo(
    () =>
      proposals.filter(
        (p) =>
          !["deployed", "rejected", "withdrawn"].includes(p.status ?? ""),
      ).length,
    [proposals],
  );

  const stats = useMemo(
    () => [
      {
        label: "Live rules",
        value: String(policy.provider_count ?? providers.length ?? 0),
      },
      {
        label: "Live version",
        value: currentVersion ? `v${currentVersion}` : "Not versioned",
      },
      { label: "Saved versions", value: String(versions.length) },
      {
        label: "Pending changes",
        value: String(governance.pending_count ?? activeProposalCount ?? 0),
      },
      { label: "Stale drafts", value: String(governance.stale_count ?? 0) },
    ],
    [
      activeProposalCount,
      currentVersion,
      governance.pending_count,
      governance.stale_count,
      policy.provider_count,
      providers.length,
      versions.length,
    ],
  );

  const liveRuleCount = String(policy.provider_count ?? providers.length ?? 0);
  const liveVersionLabel = currentVersion ? `v${currentVersion}` : "Not versioned";
  const pendingChangeCount = String(governance.pending_count ?? activeProposalCount ?? 0);

  // ── API hook ──────────────────────────────────────────────────────
  const api = usePolicyApi({ setBanner, setBusyKey, refresh });

  // ── Tab content ───────────────────────────────────────────────────
  function renderTab() {
    switch (activeTab) {
      // Iter 14.16 — split Overview into Catalog (picking) and
      // Metrics (monitoring). The data + handlers each tab needs is
      // a strict subset of what Overview took.
      case "catalog":
        return (
          <CatalogTab
            bundles={bundles}
            onStageBundle={(bundleId, title) =>
              api.stageBundle(bundleId, title)
            }
          />
        );
      case "metrics":
        return <MetricsTab analytics={analytics} />;
      // Iter 14.17 — "Now Live" hosts Live Chain + Tools as sub-tabs.
      // Both answer "what's running right now" — Live Chain shows
      // the active provider sequence; Tools is the editor + pack
      // management surface for that same sequence.
      case "now-live":
        return (
          <TabGroup
            tabs={[
              {
                key: "live",
                label: "Live chain",
                content: (
                  <LiveChainTab
                    providers={providers}
                    schema={schema as PolicySchemaResponse}
                    onExportLive={() => api.exportPolicy()}
                    onDraftEdit={(index, config, description) =>
                      api.createProposal({
                        action: "swap",
                        config,
                        targetIndex: index,
                        description,
                      })
                    }
                    onDraftRemoval={(index, reason) =>
                      api.createProposal({
                        action: "remove",
                        targetIndex: index,
                        description: reason,
                      })
                    }
                  />
                ),
              },
              {
                key: "tools",
                label: "Tools & packs",
                content: (
                  <ToolsTab
                    schema={schema as PolicySchemaResponse}
                    packs={packs}
                    versionNumbers={versionNumbers}
                    onCreateProposal={api.createProposal}
                    onImportPolicy={api.importPolicy}
                    onSavePack={api.savePack}
                    onDeletePack={api.deletePack}
                    onStagePack={api.stagePack}
                  />
                ),
              },
            ]}
          />
        );
      case "proposals":
        return (
          <ProposalLaneTab
            proposals={proposals}
            requireApproval={requireApproval}
            requireSimulation={requireSimulation}
            simulationDefaults={simulationDefaults}
            onSimulate={api.simulateProposal}
            onApproveAndDeploy={api.approveAndDeploy}
            onReject={api.rejectProposal}
            onWithdraw={api.withdrawProposal}
            onAssign={api.assignProposal}
          />
        );
      // Iter 14.17 — "Lifecycle" hosts Versions + Migration as
      // sub-tabs. Both answer "how does this change over time" —
      // Versions is the historical record + rollback surface;
      // Migration is the staged-promotion-between-environments flow.
      case "lifecycle":
        return (
          <TabGroup
            tabs={[
              {
                key: "versions",
                label: "Versions",
                badge: versions.length || undefined,
                content: (
                  <VersionsTab
                    versions={sortedVersions}
                    currentVersion={currentVersion}
                    onExportVersion={api.exportPolicy}
                    onRollback={api.rollbackVersion}
                    onLoadDiff={api.loadDiff}
                  />
                ),
              },
              {
                key: "migration",
                label: "Migration",
                content: (
                  <MigrationTab
                    environments={environments}
                    promotions={promotions}
                    versionNumbers={versionNumbers}
                    currentVersion={currentVersion}
                    onCaptureEnvironment={api.captureEnvironment}
                    onStagePromotion={api.stagePromotion}
                    onPreviewMigration={api.previewMigration}
                  />
                ),
              },
            ]}
          />
        );
      default:
        return null;
    }
  }

  return (
    <Stack spacing={2.5}>
      {/* Iter 14.14 — One-sentence orientation for new operators.
          The header reads ``workspace.policyKernelIntroDismissed``
          from RegistryUserPreferences and returns null once a user
          has dismissed it, so power users see no chrome at all. */}
      <PolicyKernelIntroHeader />

      {banner ? (
        <Banner
          tone={banner.tone}
          message={banner.message}
          onDismiss={clearBanner}
        />
      ) : null}

      <Card variant="outlined" sx={{ overflow: "hidden" }}>
        <CardContent sx={{ p: 0 }}>
          <Box
            sx={{
              p: { xs: 2.5, md: 3 },
              display: "flex",
              flexDirection: { xs: "column", lg: "row" },
              alignItems: { xs: "flex-start", lg: "center" },
              justifyContent: "space-between",
              gap: 2.5,
            }}
          >
            <Box sx={{ display: "grid", gap: 0.75, maxWidth: 760 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Policy workspace
              </Typography>
              <Typography variant="h6" sx={{ color: "var(--app-fg)" }}>
                Govern live rules through reviewable changes
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Keep live policy, proposals, versions, tools, and migrations in one controlled workflow.
              </Typography>
            </Box>

            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Chip
                label={requireApproval ? "Approval required" : "Direct deploy enabled"}
                sx={{
                  bgcolor: requireApproval ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                  color: requireApproval ? "var(--app-fg)" : "var(--app-muted)",
                  fontWeight: 700,
                }}
              />
              <Chip
                label={requireSimulation ? "Simulation required" : "Simulation optional"}
                sx={{ bgcolor: "var(--app-control-bg)", color: "var(--app-muted)", fontWeight: 700 }}
              />
            </Box>
          </Box>

          <Box
            sx={{
              px: { xs: 2.5, md: 3 },
              pb: { xs: 2.5, md: 3 },
              display: "grid",
              gap: 1.25,
              gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", xl: "repeat(5, 1fr)" },
            }}
          >
            {stats.map((item) => {
              const emphasized =
                item.value === liveRuleCount ||
                item.value === liveVersionLabel ||
                item.value === pendingChangeCount;
              return (
                <Box
                  key={item.label}
                  sx={{
                    p: 1.75,
                    borderRadius: 2.5,
                    border: "1px solid var(--app-border)",
                    bgcolor: emphasized ? "var(--app-control-bg)" : "var(--app-surface)",
                  }}
                >
                  <Typography sx={{ fontSize: 11, fontWeight: 700, color: "var(--app-muted)" }}>
                    {item.label}
                  </Typography>
                  <Typography sx={{ mt: 0.6, fontSize: 24, lineHeight: 1.1, fontWeight: 750, color: "var(--app-fg)" }}>
                    {item.value}
                  </Typography>
                </Box>
              );
            })}
          </Box>

          <Divider />

          <Box sx={{ px: { xs: 1.5, md: 2 }, bgcolor: "var(--app-control-bg)" }}>
            <PolicyTabs
              activeTab={activeTab}
              // Iter 14.18 — handleTabChange persists the user's
              // pinning to RegistryUserPreferences in addition to
              // updating local state, so the next visit lands on
              // the same tab.
              onTabChange={handleTabChange}
              pendingCount={activeProposalCount}
              versionCount={versions.length}
            />
          </Box>

          <Divider />

          <Box sx={{ p: { xs: 2, md: 2.5 } }}>
            {renderTab()}
          </Box>
        </CardContent>
      </Card>
    </Stack>
  );
}
