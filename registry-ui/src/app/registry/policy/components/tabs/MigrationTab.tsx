"use client";

import { useState, useMemo } from "react";
import type {
  PolicyMigrationPreviewResponse,
} from "@/lib/registryClient";
import { usePolicyContext } from "../../contexts/PolicyContext";

type EnvironmentItem = {
  environment_id: string;
  title?: string;
  description?: string;
  current_version_number?: number | null;
  current_source_label?: string;
  capture_count?: number;
};

type PromotionItem = {
  promotion_id?: string;
  source_environment?: string;
  target_environment?: string;
  source_version_number?: number | null;
  deployed_version_number?: number | null;
  status?: string;
  note?: string;
};

type MigrationTabProps = {
  environments: EnvironmentItem[];
  promotions: PromotionItem[];
  versionNumbers: number[];
  currentVersion: number | null;
  onCaptureEnvironment: (environmentId: string, sourceVersionNumber: number | null, note: string) => Promise<void>;
  onStagePromotion: (source: string, target: string, description: string) => Promise<void>;
  onPreviewMigration: (
    sourceVersion: number | null,
    targetVersion: number | null,
    targetEnvironment: string,
  ) => Promise<PolicyMigrationPreviewResponse | null>;
};

export function MigrationTab({
  environments,
  promotions,
  versionNumbers,
  currentVersion,
  onCaptureEnvironment,
  onStagePromotion,
  onPreviewMigration,
}: MigrationTabProps) {
  const { busyKey, setBanner } = usePolicyContext();

  const [captureSource, setCaptureSource] = useState<string>(
    currentVersion ? `version:${currentVersion}` : "live",
  );
  const [promotionSourceEnvironment, setPromotionSourceEnvironment] = useState<string>(
    environments[0]?.environment_id ?? "development",
  );
  const [promotionTargetEnvironment, setPromotionTargetEnvironment] = useState<string>(
    environments[1]?.environment_id ?? environments[0]?.environment_id ?? "staging",
  );
  const [promotionDescription, setPromotionDescription] = useState("");

  const [migrationSource, setMigrationSource] = useState<string>("live");
  const [migrationTarget, setMigrationTarget] = useState<string>(
    currentVersion ? `version:${currentVersion}` : "live",
  );
  const [migrationEnvironment, setMigrationEnvironment] = useState<string>(
    environments[1]?.environment_id ?? environments[0]?.environment_id ?? "staging",
  );
  const [migrationPreview, setMigrationPreview] =
    useState<PolicyMigrationPreviewResponse | null>(null);

  const environmentMap = useMemo(
    () =>
      Object.fromEntries(
        environments.map((env) => [env.environment_id, env]),
      ),
    [environments],
  );

  function parseCaptureVersionNumber(source: string): number | null {
    return source === "live" ? null : Number(source.replace("version:", ""));
  }

  async function handlePreviewMigration() {
    const sourceVersion =
      migrationSource === "live" ? null : Number(migrationSource.replace("version:", ""));
    const targetVersion =
      migrationTarget === "live" ? null : Number(migrationTarget.replace("version:", ""));
    const result = await onPreviewMigration(sourceVersion, targetVersion, migrationEnvironment);
    setMigrationPreview(result);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Environment promotion */}
      <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
            Environment promotion
          </p>
          <h2 className="text-xl font-semibold text-emerald-50">
            Move policy safely across development, staging, and production
          </h2>
          <p className="text-xs text-emerald-100/80">
            Capture a baseline for each environment, preview the change, then
            stage a promotion proposal through the same approval workflow.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <label className="flex items-center gap-2 text-xs text-emerald-100/90">
            <span>Capture source</span>
            <select
              value={captureSource}
              onChange={(event) => setCaptureSource(event.target.value)}
              className="rounded-full border border-emerald-700/70 bg-emerald-950 px-3 py-1 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            >
              <option value="live">Live policy chain</option>
              {versionNumbers.map((vn) => (
                <option key={`capture-source-${vn}`} value={`version:${vn}`}>
                  Version {vn}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {environments.map((environment) => (
            <article
              key={environment.environment_id}
              className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-emerald-50">
                  {environment.title ?? environment.environment_id}
                </p>
                <span className="rounded-full bg-emerald-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                  v{String(environment.current_version_number ?? "\u2014")}
                </span>
              </div>
              <p className="mt-2 text-xs text-emerald-100/90">
                {environment.description}
              </p>
              <p className="mt-3 text-[11px] text-emerald-300/90">
                {environment.current_source_label ?? "No captured baseline yet"}
              </p>
              <p className="mt-1 text-[11px] text-emerald-300/90">
                Captures: {String(environment.capture_count ?? 0)}
              </p>
              <button
                type="button"
                onClick={() =>
                  void onCaptureEnvironment(
                    environment.environment_id,
                    parseCaptureVersionNumber(captureSource),
                    captureSource === "live"
                      ? "Captured live policy chain."
                      : `Captured ${captureSource}.`,
                  )
                }
                disabled={busyKey === `capture-${environment.environment_id}`}
                className="mt-4 rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
              >
                {busyKey === `capture-${environment.environment_id}`
                  ? "Capturing\u2026"
                  : "Capture baseline"}
              </button>
            </article>
          ))}
        </div>

        {/* Promotion form */}
        <div className="mt-5 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
              Source environment
              <select
                value={promotionSourceEnvironment}
                onChange={(event) => setPromotionSourceEnvironment(event.target.value)}
                className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              >
                {environments.map((env) => (
                  <option key={`promotion-source-${env.environment_id}`} value={env.environment_id}>
                    {env.title ?? env.environment_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
              Target environment
              <select
                value={promotionTargetEnvironment}
                onChange={(event) => setPromotionTargetEnvironment(event.target.value)}
                className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              >
                {environments.map((env) => (
                  <option key={`promotion-target-${env.environment_id}`} value={env.environment_id}>
                    {env.title ?? env.environment_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
              Promotion note
              <input
                value={promotionDescription}
                onChange={(event) => setPromotionDescription(event.target.value)}
                placeholder="Why is this moving forward?"
                className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                const sourceVersion =
                  environmentMap[promotionSourceEnvironment]?.current_version_number;
                const targetVersion =
                  environmentMap[promotionTargetEnvironment]?.current_version_number;
                if (!sourceVersion) {
                  setBanner({
                    tone: "error",
                    message:
                      "Capture a baseline for the source environment before previewing a promotion.",
                  });
                  return;
                }
                setMigrationSource(`version:${sourceVersion}`);
                setMigrationTarget(
                  targetVersion ? `version:${targetVersion}` : "live",
                );
                setMigrationEnvironment(promotionTargetEnvironment);
                void handlePreviewMigration();
              }}
              disabled={busyKey === "migration-preview"}
              className="rounded-full border border-emerald-600/80 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
            >
              {busyKey === "migration-preview"
                ? "Previewing\u2026"
                : "Preview environment promotion"}
            </button>
            <button
              type="button"
              onClick={() => void onStagePromotion(promotionSourceEnvironment, promotionTargetEnvironment, promotionDescription)}
              disabled={busyKey === "stage-promotion"}
              className="rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {busyKey === "stage-promotion" ? "Staging\u2026" : "Stage promotion"}
            </button>
          </div>
        </div>

        {/* Recent promotions */}
        <div className="mt-5 space-y-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
            Recent promotion activity
          </p>
          {promotions.length === 0 ? (
            <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
              <p className="text-xs text-emerald-100/90">
                No promotions have been staged yet.
              </p>
            </div>
          ) : (
            promotions.slice(0, 5).map((promotion) => (
              <article
                key={promotion.promotion_id}
                className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-emerald-50">
                    {promotion.source_environment ?? "source"} \u2192{" "}
                    {promotion.target_environment ?? "target"}
                  </p>
                  <span className="rounded-full bg-emerald-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                    {promotion.status ?? "staged"}
                  </span>
                </div>
                <p className="mt-2 text-xs text-emerald-100/90">
                  {promotion.note || "Promotion tracked through proposal governance."}
                </p>
                <p className="mt-2 text-[11px] text-emerald-300/90">
                  Source v{String(promotion.source_version_number ?? "\u2014")}
                  {promotion.deployed_version_number
                    ? ` \u00b7 deployed as v${String(promotion.deployed_version_number)}`
                    : ""}
                </p>
              </article>
            ))
          )}
        </div>
      </div>

      {/* Migration preview */}
      <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
            Migration preview
          </p>
          <h2 className="text-xl font-semibold text-emerald-50">
            Plan promotion between versions and environments
          </h2>
          <p className="max-w-2xl text-xs text-emerald-100/80">
            Compare a live chain or saved version against the current target and see
            what will change, what is risky, and what the chosen environment expects.
          </p>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr,1fr,1fr,auto]">
          <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
            Source
            <select
              value={migrationSource}
              onChange={(event) => setMigrationSource(event.target.value)}
              className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            >
              <option value="live">Live policy</option>
              {versionNumbers.map((vn) => (
                <option key={`migration-source-${vn}`} value={`version:${vn}`}>
                  Version {vn}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
            Compare against
            <select
              value={migrationTarget}
              onChange={(event) => setMigrationTarget(event.target.value)}
              className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            >
              <option value="live">Current live chain</option>
              {versionNumbers.map((vn) => (
                <option key={`migration-target-${vn}`} value={`version:${vn}`}>
                  Version {vn}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
            Target environment
            <select
              value={migrationEnvironment}
              onChange={(event) => setMigrationEnvironment(event.target.value)}
              className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            >
              {environments.map((env) => (
                <option key={env.environment_id} value={env.environment_id}>
                  {env.title ?? env.environment_id}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => void handlePreviewMigration()}
            disabled={busyKey === "migration-preview"}
            className="self-end rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
          >
            {busyKey === "migration-preview" ? "Previewing\u2026" : "Preview migration"}
          </button>
        </div>

        <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
          {migrationPreview?.summary ? (
            <div className="grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
              <div className="space-y-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                    Migration summary
                  </p>
                  <p className="mt-2 text-xs text-emerald-100/90">
                    {migrationPreview.source?.label} \u2192 {migrationPreview.target?.label}
                  </p>
                  <p className="mt-1 text-[11px] text-emerald-300/90">
                    {String(
                      (migrationPreview.summary.changed_count as number | undefined) ?? 0,
                    )}{" "}
                    changed \u00b7{" "}
                    {String(
                      (migrationPreview.summary.added_count as number | undefined) ?? 0,
                    )}{" "}
                    added \u00b7{" "}
                    {String(
                      (migrationPreview.summary.removed_count as number | undefined) ?? 0,
                    )}{" "}
                    removed
                  </p>
                </div>

                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                    Environment fit
                  </p>
                  <p className="mt-2 text-xs text-emerald-100/90">
                    {migrationPreview.environment?.description}
                  </p>
                  <ul className="mt-2 space-y-1 text-[11px] text-emerald-200/90">
                    {(migrationPreview.environment?.required_controls ?? []).map((item) => (
                      <li key={`required-control-${item}`}>\u2022 {item}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                    Recommendations
                  </p>
                  <ul className="mt-2 space-y-1 text-xs text-emerald-100/90">
                    {(migrationPreview.recommendations ?? []).map((item) => (
                      <li key={`migration-recommendation-${item}`}>\u2022 {item}</li>
                    ))}
                  </ul>
                </div>

                {(migrationPreview.risks ?? []).length > 0 ? (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                      Risks
                    </p>
                    <ul className="mt-2 space-y-2 text-xs text-emerald-100/90">
                      {(migrationPreview.risks ?? []).slice(0, 4).map((risk, index) => (
                        <li
                          key={`migration-risk-${index}`}
                          className="rounded-2xl bg-emerald-900/20 px-3 py-2 ring-1 ring-emerald-700/30"
                        >
                          <span className="font-semibold text-emerald-50">
                            {risk.title}
                          </span>{" "}
                          <span className="text-[10px] uppercase tracking-[0.14em] text-emerald-300">
                            {risk.level}
                          </span>
                          <p className="mt-1 text-xs text-emerald-100/90">
                            {risk.detail}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <p className="text-xs text-emerald-100/90">
              Choose a source, comparison target, and environment profile to preview
              promotion risk.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
