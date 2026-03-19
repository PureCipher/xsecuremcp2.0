"use client";

import type { ChangeEvent } from "react";

import type {
  PolicyAnalyticsResponse,
  PolicyBundleItem,
  PolicyConfig,
  PolicySchemaFieldSpec,
  PolicySchemaType,
  RegistryPayload,
} from "@/lib/registryClient";
import type { ImportedPolicyPreview } from "./policyTransfer";
import { formatFieldInput } from "./policyTransfer";

type PolicyTemplateChoice = {
  key: string;
  title: string;
  summary: string;
};

type GuidedFieldEntry = [string, PolicySchemaFieldSpec];

export function PolicyAnalyticsBundlesSection({
  analytics,
  topDeniedResources,
  bundles,
  busyKey,
  onStageBundle,
}: {
  analytics: PolicyAnalyticsResponse;
  topDeniedResources: RegistryPayload[];
  bundles: PolicyBundleItem[];
  busyKey: string | null;
  onStageBundle: (bundle: PolicyBundleItem) => void | Promise<void>;
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Policy analytics
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            See what is blocked, changed, and risky
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            This view keeps reviewer attention on live deny patterns, recent
            changes, and rollout risk before another proposal is approved.
          </p>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Blocked now
            </p>
            <p className="mt-2 text-2xl font-semibold text-[--app-fg]">
              {String(
                (analytics.blocked?.audit?.current_deny as number | undefined) ??
                  analytics.overview?.deny_count ??
                  0,
              )}
            </p>
            <p className="mt-1 text-[10px] text-[--app-muted]">
              Denials in the current window
            </p>
          </div>
          <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Deny rate
            </p>
            <p className="mt-2 text-2xl font-semibold text-[--app-fg]">
              {`${Math.round(
                Number(
                  (analytics.blocked?.audit?.deny_rate as number | undefined) ??
                    (analytics.blocked?.monitor?.window as RegistryPayload | undefined)
                      ?.deny_rate ??
                    0,
                ) * 100,
              )}%`}
            </p>
            <p className="mt-1 text-[10px] text-[--app-muted]">
              Recent blocked traffic share
            </p>
          </div>
          <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Active risks
            </p>
            <p className="mt-2 text-2xl font-semibold text-[--app-fg]">
              {String(analytics.risks?.length ?? 0)}
            </p>
            <p className="mt-1 text-[10px] text-[--app-muted]">
              Review items worth attention
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr,1fr]">
          <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Most blocked resources
            </p>
            <ul className="mt-3 space-y-2 text-[11px] text-[--app-muted]">
              {topDeniedResources.slice(0, 4).map((item, index) => (
                <li
                  key={`top-denied-${index}`}
                  className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                >
                  {String(item.resource_id ?? "unknown")} ·{" "}
                  {String(item.count ?? 0)} denials
                </li>
              ))}
              {topDeniedResources.length === 0 ? (
                <li className="text-[11px] text-[--app-muted]">
                  No deny hot spots have been recorded yet.
                </li>
              ) : null}
            </ul>
          </div>

          <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Recent version change
            </p>
            {analytics.changes?.latest_version_summary ? (
              <div className="mt-3 space-y-2 text-[11px] text-[--app-muted]">
                <p>
                  Compared v{analytics.changes.latest_version_from ?? "?"} to v
                  {analytics.changes.latest_version_to ?? "?"}.
                </p>
                <p>
                  {String(
                    (analytics.changes.latest_version_summary
                      ?.changed_count as number | undefined) ?? 0,
                  )}{" "}
                  changed ·{" "}
                  {String(
                    (analytics.changes.latest_version_summary
                      ?.added_count as number | undefined) ?? 0,
                  )}{" "}
                  added ·{" "}
                  {String(
                    (analytics.changes.latest_version_summary
                      ?.removed_count as number | undefined) ?? 0,
                  )}{" "}
                  removed
                </p>
              </div>
            ) : (
              <p className="mt-3 text-[11px] text-[--app-muted]">
                No prior version delta is available yet.
              </p>
            )}
            {(analytics.risks ?? []).slice(0, 3).map((risk, index) => (
              <div
                key={`risk-${index}`}
                className="mt-3 rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]"
              >
                <p className="text-[11px] font-semibold text-[--app-fg]">
                  {risk.title}
                </p>
                <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-[--app-muted]">
                  {risk.level}
                </p>
                <p className="mt-2 text-[11px] text-[--app-muted]">
                  {risk.detail}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Trend history
              </p>
              <p className="mt-1 text-[11px] text-[--app-muted]">
                Recent analytics snapshots keep rollouts grounded in how the
                policy set has actually behaved over time.
              </p>
            </div>
            <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              {String(analytics.history?.sample_count ?? 0)} samples
            </span>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Eval trend
              </p>
              <p className="mt-2 text-lg font-semibold text-[--app-fg]">
                {String(
                  (analytics.history?.deltas?.evaluation_count as number | undefined) ??
                    0,
                )}
              </p>
            </div>
            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Deny trend
              </p>
              <p className="mt-2 text-lg font-semibold text-[--app-fg]">
                {String(
                  (analytics.history?.deltas?.deny_count as number | undefined) ?? 0,
                )}
              </p>
            </div>
            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Queue trend
              </p>
              <p className="mt-2 text-lg font-semibold text-[--app-fg]">
                {String(
                  (analytics.history?.deltas?.pending_proposals as
                    | number
                    | undefined) ?? 0,
                )}
              </p>
            </div>
            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Risk trend
              </p>
              <p className="mt-2 text-lg font-semibold text-[--app-fg]">
                {String(
                  (analytics.history?.deltas?.risk_count as number | undefined) ?? 0,
                )}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr,0.8fr]">
            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Recent snapshots
              </p>
              <div className="mt-3 space-y-2">
                {((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? [])
                  .slice(-6)
                  .map((snapshot, index) => (
                    <div
                      key={`analytics-snapshot-${index}`}
                      className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-[--app-muted]">
                        <span>{String(snapshot.captured_at ?? "Unknown time")}</span>
                        <span>v{String(snapshot.current_version ?? "live")}</span>
                      </div>
                      <p className="mt-2 text-[11px] text-[--app-muted]">
                        {String(snapshot.deny_count ?? 0)} denials ·{" "}
                        {String(snapshot.pending_proposals ?? 0)} open proposals ·{" "}
                        {String(snapshot.risk_count ?? 0)} active risks
                      </p>
                    </div>
                  ))}
                {(((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? [])
                  .length === 0) ? (
                  <p className="text-[11px] text-[--app-muted]">
                    Trend history will start filling in as this workbench is
                    used and policy changes are reviewed.
                  </p>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-[--app-border] bg-[--app-hover-bg] p-3 ring-1 ring-[--app-surface-ring]">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[--app-muted]">
                Recent promotions
              </p>
              <div className="mt-3 space-y-2">
                {(analytics.history?.recent_promotions ?? []).slice(0, 4).map((promotion, index) => (
                  <div
                    key={`analytics-promotion-${promotion.promotion_id ?? index}`}
                    className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] px-3 py-2 ring-1 ring-[--app-surface-ring]"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] font-semibold text-[--app-fg]">
                        {promotion.source_environment ?? "source"} →{" "}
                        {promotion.target_environment ?? "target"}
                      </p>
                      <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                        {promotion.status ?? "staged"}
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] text-[--app-muted]">
                      {promotion.note || "Promotion tracked through the policy workflow."}
                    </p>
                  </div>
                ))}
                {((analytics.history?.recent_promotions ?? []).length === 0) ? (
                  <p className="text-[11px] text-[--app-muted]">
                    No environment promotions have been staged yet.
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Reusable bundles
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            Start from proven policy packs
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            Bundles stage full-chain proposals for common registry operating
            modes.
          </p>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          {bundles.length === 0 ? (
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <p className="text-[12px] text-[--app-muted]">
                No reusable bundles are available yet.
              </p>
            </div>
          ) : (
            bundles.map((bundle) => (
              <article
                key={bundle.bundle_id}
                className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[12px] font-semibold text-[--app-fg]">
                        {bundle.title ?? bundle.bundle_id}
                      </p>
                      <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                        {bundle.risk_posture ?? "bundle"}
                      </span>
                    </div>
                    <p className="text-[11px] text-[--app-muted]">
                      {bundle.summary ?? bundle.description}
                    </p>
                    <p className="text-[10px] text-[--app-muted]">
                      {bundle.provider_count ?? 0} steps · Best for{" "}
                      {(bundle.recommended_environments ?? []).join(", ") ||
                        "any environment"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void onStageBundle(bundle)}
                    disabled={busyKey === `bundle-${bundle.bundle_id}`}
                    className="rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
                  >
                    {busyKey === `bundle-${bundle.bundle_id}`
                      ? "Staging…"
                      : "Stage bundle"}
                  </button>
                </div>
                <ul className="mt-3 space-y-1 text-[10px] text-[--app-muted]">
                  {(bundle.provider_summaries ?? [])
                    .slice(0, 3)
                    .map((summary, index) => (
                      <li key={`${bundle.bundle_id}-summary-${index}`}>
                        • {summary}
                      </li>
                    ))}
                </ul>
              </article>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

export function PolicyWorkbenchSidebar({
  commonFieldEntries,
  policyTypeEntries,
  compositionEntries,
  commonFieldSpecs,
  guidedKind,
  guidedSelection,
  onGuidedKindChange,
  onGuidedSelectionChange,
  guidedDraft,
  guidedFieldSpecs,
  onGuidedCommonFieldChange,
  onGuidedFieldChange,
  onLoadGuidedDraft,
  templateChoices,
  selectedTemplate,
  onChooseTemplate,
  createConfigText,
  onCreateConfigTextChange,
  createDescription,
  onCreateDescriptionChange,
  creating,
  onCreateProposal,
  importText,
  onImportTextChange,
  importDescriptionPrefix,
  onImportDescriptionPrefixChange,
  importPreview,
  onImportFile,
  onImportPolicy,
  onLoadIntoDraft,
  busyKey,
}: {
  commonFieldEntries: Array<[string, string]>;
  policyTypeEntries: Array<[string, PolicySchemaType]>;
  compositionEntries: Array<[string, PolicySchemaType]>;
  commonFieldSpecs: Array<[string, PolicySchemaFieldSpec]>;
  guidedKind: "policy" | "composition";
  guidedSelection: string;
  onGuidedKindChange: (nextKind: "policy" | "composition") => void;
  onGuidedSelectionChange: (selection: string) => void;
  guidedDraft: PolicyConfig;
  guidedFieldSpecs: GuidedFieldEntry[];
  onGuidedCommonFieldChange: (fieldName: string, value: string) => void;
  onGuidedFieldChange: (fieldName: string, value: string) => void;
  onLoadGuidedDraft: () => void;
  templateChoices: PolicyTemplateChoice[];
  selectedTemplate: string;
  onChooseTemplate: (templateName: string) => void;
  createConfigText: string;
  onCreateConfigTextChange: (value: string) => void;
  createDescription: string;
  onCreateDescriptionChange: (value: string) => void;
  creating: boolean;
  onCreateProposal: () => void | Promise<void>;
  importText: string;
  onImportTextChange: (value: string) => void;
  importDescriptionPrefix: string;
  onImportDescriptionPrefixChange: (value: string) => void;
  importPreview: ImportedPolicyPreview | Error | null;
  onImportFile: (event: ChangeEvent<HTMLInputElement>) => void | Promise<void>;
  onImportPolicy: () => void | Promise<void>;
  onLoadIntoDraft: () => void;
  busyKey: string | null;
}) {
  return (
    <aside className="flex flex-col gap-4">
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Schema guide
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            See the supported JSON shape
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            Use this guide when you hand-edit JSON, prepare imports, or want a
            quick reminder of the fields each policy type supports.
          </p>
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
            Common fields
          </p>
          <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
            {commonFieldEntries.map(([fieldName, description]) => (
              <li key={fieldName}>
                <span className="font-semibold text-[--app-fg]">{fieldName}</span>:{" "}
                {description}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-4 grid gap-3">
          {policyTypeEntries.map(([typeName, definition]) => (
            <div
              key={typeName}
              className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[11px] font-semibold capitalize text-[--app-fg]">
                  {typeName.replaceAll("_", " ")}
                </p>
                {definition.aliases?.length ? (
                  <span className="text-[10px] text-[--app-muted]">
                    Aliases: {definition.aliases.join(", ")}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-[11px] text-[--app-muted]">
                {definition.description}
              </p>
              <ul className="mt-2 space-y-1 text-[10px] text-[--app-muted]">
                {Object.entries(definition.fields ?? {}).map(
                  ([fieldName, description]) => (
                    <li key={`${typeName}-${fieldName}`}>
                      <span className="font-semibold text-[--app-fg]">
                        {fieldName}
                      </span>
                      : {description}
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
            Composition helpers
          </p>
          <ul className="mt-2 space-y-2 text-[11px] text-[--app-muted]">
            {compositionEntries.map(([name, definition]) => (
              <li key={name}>
                <span className="font-semibold text-[--app-fg]">
                  {name.replaceAll("_", " ")}
                </span>
                : {definition.description}
                {definition.extra_fields
                  ? ` Extra fields: ${Object.entries(definition.extra_fields)
                      .map(
                        ([fieldName, description]) =>
                          `${fieldName} (${description})`,
                      )
                      .join(", ")}`
                  : ""}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Guided builder
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            Author a rule from the schema
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            Pick a policy type, fill in guided fields, and only drop to raw
            JSON for nested or advanced cases.
          </p>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-[11px] text-[--app-muted]">
            Builder mode
            <select
              value={guidedKind}
              onChange={(event) =>
                onGuidedKindChange(
                  event.target.value as "policy" | "composition",
                )
              }
              className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
            >
              <option value="policy">Single policy</option>
              <option value="composition">Composition</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[11px] text-[--app-muted]">
            Template
            <select
              value={guidedSelection}
              onChange={(event) => onGuidedSelectionChange(event.target.value)}
              className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
            >
              {(guidedKind === "policy"
                ? policyTypeEntries
                : compositionEntries
              ).map(([key]) => (
                <option key={key} value={key}>
                  {key.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 grid gap-3">
          {commonFieldSpecs.map(([fieldName, spec]) => (
            <label
              key={`guided-common-${fieldName}`}
              className="flex flex-col gap-1 text-[11px] text-[--app-muted]"
            >
              {spec.label ?? fieldName}
              <input
                value={formatFieldInput(spec, guidedDraft[fieldName])}
                onChange={(event) =>
                  onGuidedCommonFieldChange(fieldName, event.target.value)
                }
                placeholder={spec.placeholder}
                className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
              <span className="text-[10px] text-[--app-muted]">
                {spec.description}
              </span>
            </label>
          ))}
        </div>

        <div className="mt-4 grid gap-3">
          {guidedFieldSpecs.map(([fieldName, spec]) => {
            const unsupported =
              spec.type === "policy_config" ||
              spec.type === "policy_config_list" ||
              spec.type === "policy_config_map";
            if (unsupported) {
              return (
                <div
                  key={`guided-field-${fieldName}`}
                  className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
                >
                  <p className="text-[11px] font-semibold text-[--app-fg]">
                    {spec.label ?? fieldName}
                  </p>
                  <p className="mt-2 text-[11px] text-[--app-muted]">
                    {spec.description}
                  </p>
                  <p className="mt-2 text-[10px] text-[--app-muted]">
                    Nested rules still use the JSON preview below. Start from
                    the starter config and refine the preview if you need
                    compositions or resource-specific children.
                  </p>
                </div>
              );
            }

            const currentValue = guidedDraft[fieldName];
            const inputValue = formatFieldInput(spec, currentValue);
            return (
              <label
                key={`guided-field-${fieldName}`}
                className="flex flex-col gap-1 text-[11px] text-[--app-muted]"
              >
                {spec.label ?? fieldName}
                {spec.type === "bool" ? (
                  <select
                    value={inputValue || String(Boolean(spec.default))}
                    onChange={(event) =>
                      onGuidedFieldChange(fieldName, event.target.value)
                    }
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : spec.type === "enum" ? (
                  <select
                    value={inputValue || String(spec.default ?? "")}
                    onChange={(event) =>
                      onGuidedFieldChange(fieldName, event.target.value)
                    }
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
                  >
                    {(spec.enum ?? []).map((option) => (
                      <option key={`${fieldName}-${option}`} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : spec.type === "json_map" ||
                  spec.type === "string_map_string_list" ? (
                  <textarea
                    value={inputValue}
                    onChange={(event) =>
                      onGuidedFieldChange(fieldName, event.target.value)
                    }
                    className="min-h-[120px] rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-3 font-mono text-[11px] leading-6 text-[--app-fg] outline-none focus:border-[--app-accent]"
                  />
                ) : (
                  <input
                    value={inputValue}
                    onChange={(event) =>
                      onGuidedFieldChange(fieldName, event.target.value)
                    }
                    placeholder={spec.placeholder}
                    type={spec.type === "int" ? "number" : "text"}
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
                  />
                )}
                <span className="text-[10px] text-[--app-muted]">
                  {spec.description}
                </span>
              </label>
            );
          })}
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Guided JSON preview
            </p>
            <button
              type="button"
              onClick={() => onLoadGuidedDraft()}
              className="rounded-full border border-[--app-border] px-3 py-1 text-[10px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
            >
              Load into proposal editor
            </button>
          </div>
          <pre className="mt-3 max-h-[280px] overflow-auto whitespace-pre-wrap break-words text-[11px] leading-6 text-[--app-fg]">
            {JSON.stringify(guidedDraft, null, 2)}
          </pre>
        </div>
      </div>

      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Proposal editor
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            Refine or hand-edit the JSON
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            Use the guided builder above or start from a quick template, then
            create a proposal that reviewers can approve before it goes live.
          </p>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {templateChoices.map((template) => (
            <button
              key={template.key}
              type="button"
              onClick={() => onChooseTemplate(template.key)}
              className={`rounded-2xl border border-[--app-border] px-3 py-3 text-left text-[11px] ring-1 transition ${
                selectedTemplate === template.key
                  ? "bg-[--app-control-active-bg] text-[--app-fg] ring-[--app-accent]"
                  : "bg-[--app-control-bg] text-[--app-muted] ring-[--app-surface-ring] hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
              }`}
            >
              <span className="block font-semibold capitalize">
                {template.title}
              </span>
              <span className="mt-1 block text-[10px] text-[--app-muted]">
                {template.summary}
              </span>
            </button>
          ))}
        </div>

        <textarea
          value={createConfigText}
          onChange={(event) => onCreateConfigTextChange(event.target.value)}
          className="mt-4 min-h-[280px] w-full rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-3 font-mono text-[11px] leading-6 text-[--app-fg] outline-none focus:border-[--app-accent]"
        />

        <input
          value={createDescription}
          onChange={(event) => onCreateDescriptionChange(event.target.value)}
          placeholder="What change should this proposal make?"
          className="mt-3 w-full rounded-full border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
        />

        <button
          type="button"
          onClick={() => void onCreateProposal()}
          disabled={creating}
          className="mt-4 rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
        >
          {creating ? "Creating proposal…" : "Create proposal"}
        </button>
      </div>

      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Import and export
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            Move policy JSON in and out safely
          </h2>
          <p className="text-[11px] text-[--app-muted]">
            Export the live chain or a saved version, then import a snapshot,
            provider list, or single rule. Imports become batch proposals that
            still go through validation, simulation, approval, and deploy.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onImportPolicy()}
            disabled={busyKey === "import-policy"}
            className="rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
          >
            {busyKey === "import-policy"
              ? "Importing…"
              : "Stage import as proposals"}
          </button>
          <label className="cursor-pointer rounded-full border border-[--app-border] px-3 py-1 text-[10px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]">
            Load JSON file
            <input
              type="file"
              accept="application/json,.json"
              onChange={(event) => void onImportFile(event)}
              className="sr-only"
            />
          </label>
        </div>

        <textarea
          value={importText}
          onChange={(event) => onImportTextChange(event.target.value)}
          placeholder="Paste a policy snapshot, provider list, or single policy rule JSON."
          className="mt-4 min-h-[220px] w-full rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-3 font-mono text-[11px] leading-6 text-[--app-fg] outline-none focus:border-[--app-accent]"
        />

        <input
          value={importDescriptionPrefix}
          onChange={(event) =>
            onImportDescriptionPrefixChange(event.target.value)
          }
          placeholder="Imported policy snapshot"
          className="mt-3 w-full rounded-full border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-[11px] text-[--app-fg] outline-none focus:border-[--app-accent]"
        />

        <div className="mt-3 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          {importPreview instanceof Error ? (
            <p className="text-[11px] text-rose-100">{importPreview.message}</p>
          ) : importPreview ? (
            <div className="space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                Import preview
              </p>
              <p className="text-[11px] text-[--app-muted]">
                {importPreview.label} · {importPreview.providerCount}{" "}
                {importPreview.providerCount === 1 ? "provider" : "providers"}
              </p>
              <p className="text-[10px] text-[--app-muted]">
                The import will stage a batch proposal against the current live
                chain instead of changing it directly.
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-[--app-muted]">
              Paste JSON to see what kind of policy import it is before staging
              it.
            </p>
          )}
        </div>

        {importPreview && !(importPreview instanceof Error) ? (
          <button
            type="button"
            onClick={() => onLoadIntoDraft()}
            disabled={importPreview.kind !== "single_provider"}
            className="mt-4 rounded-full border border-[--app-border] px-4 py-2 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-60"
          >
            Load single rule into draft
          </button>
        ) : null}
      </div>
    </aside>
  );
}
