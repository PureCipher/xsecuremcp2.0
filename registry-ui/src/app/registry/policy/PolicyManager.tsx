"use client";

import { useMemo } from "react";
import { Stack } from "@mui/material";
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
import { useTabNavigation } from "./hooks/useTabNavigation";
import { useServerRefresh } from "./hooks/useServerRefresh";
import { usePolicyApi } from "./hooks/usePolicyApi";
import { usePolicyContext } from "./contexts/PolicyContext";

import { Banner } from "./components/Banner";
import { StatsBar } from "./components/StatsBar";
import { PolicyTabs } from "./components/PolicyTabs";
import { OverviewTab } from "./components/tabs/OverviewTab";
import { LiveChainTab } from "./components/tabs/LiveChainTab";
import { ProposalLaneTab } from "./components/tabs/ProposalLaneTab";
import { VersionsTab } from "./components/tabs/VersionsTab";
import { ToolsTab } from "./components/tabs/ToolsTab";
import { MigrationTab } from "./components/tabs/MigrationTab";

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
}: {
  initialData: PolicyManagerData;
  currentUsername?: string | null;
}) {
  return (
    <PolicyProvider currentUsername={currentUsername}>
      <PolicyManagerInner initialData={initialData} />
    </PolicyProvider>
  );
}

function PolicyManagerInner({
  initialData,
}: {
  initialData: PolicyManagerData;
}) {
  const { banner, setBanner, setBusyKey, clearBanner } = usePolicyContext();
  const { refresh } = useServerRefresh();
  const { activeTab, setActiveTab } = useTabNavigation("overview");

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

  // ── API hook ──────────────────────────────────────────────────────
  const api = usePolicyApi({ setBanner, setBusyKey, refresh });

  // ── Tab content ───────────────────────────────────────────────────
  function renderTab() {
    switch (activeTab) {
      case "overview":
        return (
          <OverviewTab
            analytics={analytics}
            bundles={bundles}
            onStageBundle={(bundleId, title) =>
              api.stageBundle(bundleId, title)
            }
          />
        );
      case "live":
        return (
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
      case "versions":
        return (
          <VersionsTab
            versions={sortedVersions}
            currentVersion={currentVersion}
            onExportVersion={api.exportPolicy}
            onRollback={api.rollbackVersion}
            onLoadDiff={api.loadDiff}
          />
        );
      case "tools":
        return (
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
        );
      case "migration":
        return (
          <MigrationTab
            environments={environments}
            promotions={promotions}
            versionNumbers={versionNumbers}
            currentVersion={currentVersion}
            onCaptureEnvironment={api.captureEnvironment}
            onStagePromotion={api.stagePromotion}
            onPreviewMigration={api.previewMigration}
          />
        );
      default:
        return null;
    }
  }

  return (
    <Stack spacing={3}>
      {banner ? (
        <Banner
          tone={banner.tone}
          message={banner.message}
          onDismiss={clearBanner}
        />
      ) : null}

      <StatsBar stats={stats} />

      <PolicyTabs
        activeTab={activeTab}
        onTabChange={setActiveTab}
        pendingCount={activeProposalCount}
        versionCount={versions.length}
      />

      {renderTab()}
    </Stack>
  );
}
