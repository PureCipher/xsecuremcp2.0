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
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { highlightJson, JsonEditor } from "./components/JsonEditor";

type PolicyTemplateChoice = {
  key: string;
  title: string;
  summary: string;
};

type GuidedFieldEntry = [string, PolicySchemaFieldSpec];

const surfacePanelSx = {
  borderRadius: 4,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-surface)",
  p: 2.5,
  boxShadow: "0 0 0 1px var(--app-surface-ring)",
} as const;

const nestedPanelSx = {
  borderRadius: 3,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-control-bg)",
  p: 2,
  boxShadow: "0 0 0 1px var(--app-surface-ring)",
} as const;

const hoverTileSx = {
  borderRadius: 3,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-hover-bg)",
  p: 1.5,
  boxShadow: "0 0 0 1px var(--app-surface-ring)",
} as const;

const fieldSx = (fontPx: number) =>
  ({
    "& .MuiOutlinedInput-root": {
      borderRadius: 3,
      bgcolor: "var(--app-chrome-bg)",
      "& fieldset": { borderColor: "var(--app-border)" },
      "&:hover fieldset": { borderColor: "var(--app-border)" },
      "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
    },
    "& .MuiInputBase-input": { fontSize: fontPx, color: "var(--app-fg)" },
    "& .MuiInputLabel-root": { fontSize: fontPx, color: "var(--app-muted)" },
  }) as const;

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
    <Box
      sx={{
        display: "grid",
        gap: 3,
        gridTemplateColumns: { xs: "1fr", xl: "1.1fr 0.9fr" },
      }}
    >
      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Policy analytics
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            See what is blocked, changed, and risky
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            This view keeps reviewer attention on live deny patterns, recent changes, and rollout risk
            before another proposal is approved.
          </Typography>
        </Stack>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" },
          }}
        >
          <Box sx={nestedPanelSx}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Blocked now
            </Typography>
            <Typography sx={{ mt: 1, fontSize: 28, fontWeight: 600, color: "var(--app-fg)" }}>
              {String(
                (analytics.blocked?.audit?.current_deny as number | undefined) ??
                  analytics.overview?.deny_count ??
                  0,
              )}
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 10, color: "var(--app-muted)" }}>
              Denials in the current window
            </Typography>
          </Box>
          <Box sx={nestedPanelSx}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Deny rate
            </Typography>
            <Typography sx={{ mt: 1, fontSize: 28, fontWeight: 600, color: "var(--app-fg)" }}>
              {`${Math.round(
                Number(
                  (analytics.blocked?.audit?.deny_rate as number | undefined) ??
                    (analytics.blocked?.monitor?.window as RegistryPayload | undefined)?.deny_rate ??
                    0,
                ) * 100,
              )}%`}
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 10, color: "var(--app-muted)" }}>
              Recent blocked traffic share
            </Typography>
          </Box>
          <Box sx={nestedPanelSx}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Active risks
            </Typography>
            <Typography sx={{ mt: 1, fontSize: 28, fontWeight: 600, color: "var(--app-fg)" }}>
              {String(analytics.risks?.length ?? 0)}
            </Typography>
            <Typography sx={{ mt: 0.5, fontSize: 10, color: "var(--app-muted)" }}>
              Review items worth attention
            </Typography>
          </Box>
        </Box>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" },
          }}
        >
          <Box sx={nestedPanelSx}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Most blocked resources
            </Typography>
            <Stack component="ul" spacing={1} sx={{ mt: 1.5, pl: 0, m: 0, listStyle: "none" }}>
              {topDeniedResources.slice(0, 4).map((item, index) => (
                <Box
                  component="li"
                  key={`top-denied-${index}`}
                  sx={{
                    ...nestedPanelSx,
                    p: 1.5,
                    bgcolor: "var(--app-hover-bg)",
                    fontSize: 11,
                    color: "var(--app-muted)",
                  }}
                >
                  {String(item.resource_id ?? "unknown")} · {String(item.count ?? 0)} denials
                </Box>
              ))}
              {topDeniedResources.length === 0 ? (
                <Typography component="li" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                  No deny hot spots have been recorded yet.
                </Typography>
              ) : null}
            </Stack>
          </Box>

          <Box sx={nestedPanelSx}>
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Recent version change
            </Typography>
            {analytics.changes?.latest_version_summary ? (
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                  Compared v{analytics.changes.latest_version_from ?? "?"} to v
                  {analytics.changes.latest_version_to ?? "?"}.
                </Typography>
                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                  {String(
                    (analytics.changes.latest_version_summary?.changed_count as number | undefined) ?? 0,
                  )}{" "}
                  changed ·{" "}
                  {String(
                    (analytics.changes.latest_version_summary?.added_count as number | undefined) ?? 0,
                  )}{" "}
                  added ·{" "}
                  {String(
                    (analytics.changes.latest_version_summary?.removed_count as number | undefined) ?? 0,
                  )}{" "}
                  removed
                </Typography>
              </Stack>
            ) : (
              <Typography sx={{ mt: 1.5, fontSize: 11, color: "var(--app-muted)" }}>
                No prior version delta is available yet.
              </Typography>
            )}
            {(analytics.risks ?? []).slice(0, 3).map((risk, index) => (
              <Box
                key={`risk-${index}`}
                sx={{
                  mt: 1.5,
                  ...nestedPanelSx,
                  bgcolor: "var(--app-hover-bg)",
                }}
              >
                <Typography sx={{ fontSize: 11, fontWeight: 600, color: "var(--app-fg)" }}>
                  {risk.title}
                </Typography>
                <Typography
                  sx={{
                    mt: 0.5,
                    fontSize: 10,
                    textTransform: "uppercase",
                    letterSpacing: "0.14em",
                    color: "var(--app-muted)",
                  }}
                >
                  {risk.level}
                </Typography>
                <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>{risk.detail}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        <Box sx={{ ...nestedPanelSx, mt: 2 }}>
          <Stack
            direction="row"
            spacing={1}
            sx={{ flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}
          >
            <Box>
              <Typography
                sx={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Trend history
              </Typography>
              <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                Recent analytics snapshots keep rollouts grounded in how the policy set has actually behaved over
                time.
              </Typography>
            </Box>
            <Chip
              size="small"
              label={`${String(analytics.history?.sample_count ?? 0)} samples`}
              sx={{
                borderRadius: 999,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                bgcolor: "var(--app-surface)",
                color: "var(--app-muted)",
                border: "1px solid var(--app-border)",
              }}
            />
          </Stack>

          <Box
            sx={{
              mt: 2,
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: { xs: "1fr", sm: "repeat(4, 1fr)" },
            }}
          >
            {[
              {
                label: "Eval trend",
                value: String((analytics.history?.deltas?.evaluation_count as number | undefined) ?? 0),
              },
              {
                label: "Deny trend",
                value: String((analytics.history?.deltas?.deny_count as number | undefined) ?? 0),
              },
              {
                label: "Queue trend",
                value: String((analytics.history?.deltas?.pending_proposals as number | undefined) ?? 0),
              },
              {
                label: "Risk trend",
                value: String((analytics.history?.deltas?.risk_count as number | undefined) ?? 0),
              },
            ].map((tile) => (
              <Box key={tile.label} sx={hoverTileSx}>
                <Typography
                  sx={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color: "var(--app-muted)",
                  }}
                >
                  {tile.label}
                </Typography>
                <Typography sx={{ mt: 1, fontSize: 20, fontWeight: 600, color: "var(--app-fg)" }}>
                  {tile.value}
                </Typography>
              </Box>
            ))}
          </Box>

          <Box
            sx={{
              mt: 2,
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: { xs: "1fr", lg: "1.2fr 0.8fr" },
            }}
          >
            <Box sx={hoverTileSx}>
              <Typography
                sx={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Recent snapshots
              </Typography>
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                {((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? [])
                  .slice(-6)
                  .map((snapshot, index) => (
                    <Box key={`analytics-snapshot-${index}`} sx={{ ...nestedPanelSx, p: 1.5 }}>
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                          flexWrap: "wrap",
                          alignItems: "center",
                          justifyContent: "space-between",
                          fontSize: 10,
                          color: "var(--app-muted)",
                        }}
                      >
                        <Typography sx={{ fontSize: 10, color: "inherit" }}>
                          {String(snapshot.captured_at ?? "Unknown time")}
                        </Typography>
                        <Typography sx={{ fontSize: 10, color: "inherit" }}>
                          v{String(snapshot.current_version ?? "live")}
                        </Typography>
                      </Stack>
                      <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>
                        {String(snapshot.deny_count ?? 0)} denials · {String(snapshot.pending_proposals ?? 0)} open
                        proposals · {String(snapshot.risk_count ?? 0)} active risks
                      </Typography>
                    </Box>
                  ))}
                {(((analytics.history?.snapshots as RegistryPayload[] | undefined) ?? []).length === 0) ? (
                  <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                    Trend history will start filling in as this workbench is used and policy changes are reviewed.
                  </Typography>
                ) : null}
              </Stack>
            </Box>

            <Box sx={hoverTileSx}>
              <Typography
                sx={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Recent promotions
              </Typography>
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                {(analytics.history?.recent_promotions ?? []).slice(0, 4).map((promotion, index) => (
                  <Box key={`analytics-promotion-${promotion.promotion_id ?? index}`} sx={{ ...nestedPanelSx, p: 1.5 }}>
                    <Stack
                      direction="row"
                      spacing={1}
                      sx={{ flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}
                    >
                      <Typography sx={{ fontSize: 11, fontWeight: 600, color: "var(--app-fg)" }}>
                        {promotion.source_environment ?? "source"} → {promotion.target_environment ?? "target"}
                      </Typography>
                      <Chip
                        size="small"
                        label={promotion.status ?? "staged"}
                        sx={{
                          borderRadius: 999,
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: "0.16em",
                          textTransform: "uppercase",
                          bgcolor: "var(--app-surface)",
                          color: "var(--app-muted)",
                          border: "1px solid var(--app-border)",
                        }}
                      />
                    </Stack>
                    <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>
                      {promotion.note || "Promotion tracked through the policy workflow."}
                    </Typography>
                  </Box>
                ))}
                {((analytics.history?.recent_promotions ?? []).length === 0) ? (
                  <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                    No environment promotions have been staged yet.
                  </Typography>
                ) : null}
              </Stack>
            </Box>
          </Box>
        </Box>
      </Box>

      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Reusable bundles
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            Start from proven policy packs
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Bundles stage full-chain proposals for common registry operating modes.
          </Typography>
        </Stack>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {bundles.length === 0 ? (
            <Box sx={nestedPanelSx}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                No reusable bundles are available yet.
              </Typography>
            </Box>
          ) : (
            bundles.map((bundle) => (
              <Box key={bundle.bundle_id} component="article" sx={nestedPanelSx}>
                <Stack
                  direction="row"
                  spacing={2}
                  sx={{ flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between" }}
                >
                  <Stack spacing={0.5} sx={{ minWidth: 0, flex: 1 }}>
                    <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 600, color: "var(--app-fg)" }}>
                        {bundle.title ?? bundle.bundle_id}
                      </Typography>
                      <Chip
                        size="small"
                        label={bundle.risk_posture ?? "bundle"}
                        sx={{
                          borderRadius: 999,
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: "0.16em",
                          textTransform: "uppercase",
                          bgcolor: "var(--app-surface)",
                          color: "var(--app-muted)",
                          border: "1px solid var(--app-border)",
                        }}
                      />
                    </Stack>
                    <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                      {bundle.summary ?? bundle.description}
                    </Typography>
                    <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                      {bundle.provider_count ?? 0} steps · Best for{" "}
                      {(bundle.recommended_environments ?? []).join(", ") || "any environment"}
                    </Typography>
                  </Stack>
                  <Button
                    type="button"
                    variant="contained"
                    onClick={() => void onStageBundle(bundle)}
                    disabled={busyKey === `bundle-${bundle.bundle_id}`}
                    sx={{
                      borderRadius: 999,
                      textTransform: "none",
                      fontSize: 11,
                      fontWeight: 700,
                      bgcolor: "var(--app-accent)",
                      color: "var(--app-accent-contrast)",
                      "&:hover": { bgcolor: "var(--app-accent)", opacity: 0.92 },
                    }}
                  >
                    {busyKey === `bundle-${bundle.bundle_id}` ? "Staging…" : "Stage bundle"}
                  </Button>
                </Stack>
                <Stack component="ul" spacing={0.5} sx={{ mt: 1.5, pl: 2, m: 0 }}>
                  {(bundle.provider_summaries ?? []).slice(0, 3).map((summary, index) => (
                    <Typography key={`${bundle.bundle_id}-summary-${index}`} component="li" sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                      • {summary}
                    </Typography>
                  ))}
                </Stack>
              </Box>
            ))
          )}
        </Stack>
      </Box>
    </Box>
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
  const fs = fieldSx(11);

  return (
    <Stack component="aside" spacing={3}>
      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Schema guide
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            See the supported JSON shape
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Use this guide when you hand-edit JSON, prepare imports, or want a quick reminder of the fields each policy
            type supports.
          </Typography>
        </Stack>

        <Box sx={{ ...nestedPanelSx, mt: 2 }}>
          <Typography
            sx={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Common fields
          </Typography>
          <Stack component="ul" spacing={0.5} sx={{ mt: 1, pl: 2, m: 0 }}>
            {commonFieldEntries.map(([fieldName, description]) => (
              <Typography key={fieldName} component="li" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                  {fieldName}
                </Box>
                : {description}
              </Typography>
            ))}
          </Stack>
        </Box>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {policyTypeEntries.map(([typeName, definition]) => (
            <Box key={typeName} sx={nestedPanelSx}>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                <Typography sx={{ fontSize: 11, fontWeight: 600, textTransform: "capitalize", color: "var(--app-fg)" }}>
                  {typeName.replaceAll("_", " ")}
                </Typography>
                {definition.aliases?.length ? (
                  <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                    Aliases: {definition.aliases.join(", ")}
                  </Typography>
                ) : null}
              </Stack>
              <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>{definition.description}</Typography>
              <Stack component="ul" spacing={0.5} sx={{ mt: 1, pl: 2, m: 0 }}>
                {Object.entries(definition.fields ?? {}).map(([fieldName, description]) => (
                  <Typography key={`${typeName}-${fieldName}`} component="li" sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                    <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                      {fieldName}
                    </Box>
                    : {description}
                  </Typography>
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>

        <Box sx={{ ...nestedPanelSx, mt: 2 }}>
          <Typography
            sx={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Composition helpers
          </Typography>
          <Stack component="ul" spacing={1} sx={{ mt: 1, pl: 2, m: 0 }}>
            {compositionEntries.map(([name, definition]) => (
              <Typography key={name} component="li" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                  {name.replaceAll("_", " ")}
                </Box>
                : {definition.description}
                {definition.extra_fields
                  ? ` Extra fields: ${Object.entries(definition.extra_fields)
                      .map(([fieldName, description]) => `${fieldName} (${description})`)
                      .join(", ")}`
                  : ""}
              </Typography>
            ))}
          </Stack>
        </Box>
      </Box>

      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Guided builder
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            Author a rule from the schema
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Pick a policy type, fill in guided fields, and only drop to raw JSON for nested or advanced cases.
          </Typography>
        </Stack>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 2 }}>
          <FormControl fullWidth size="small" sx={fs}>
            <InputLabel id="wb-guided-kind">Builder mode</InputLabel>
            <Select
              labelId="wb-guided-kind"
              label="Builder mode"
              value={guidedKind}
              onChange={(event) => onGuidedKindChange(event.target.value as "policy" | "composition")}
            >
              <MenuItem value="policy">Single policy</MenuItem>
              <MenuItem value="composition">Composition</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth size="small" sx={fs}>
            <InputLabel id="wb-guided-template">Template</InputLabel>
            <Select
              labelId="wb-guided-template"
              label="Template"
              value={guidedSelection}
              onChange={(event) => onGuidedSelectionChange(event.target.value)}
            >
              {(guidedKind === "policy" ? policyTypeEntries : compositionEntries).map(([key]) => (
                <MenuItem key={key} value={key}>
                  {key.replaceAll("_", " ")}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {commonFieldSpecs.map(([fieldName, spec]) => (
            <Stack key={`guided-common-${fieldName}`} spacing={0.5}>
              <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>{spec.label ?? fieldName}</Typography>
              <TextField
                size="small"
                value={formatFieldInput(spec, guidedDraft[fieldName])}
                onChange={(event) => onGuidedCommonFieldChange(fieldName, event.target.value)}
                placeholder={spec.placeholder}
                sx={fs}
              />
              <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>{spec.description}</Typography>
            </Stack>
          ))}
        </Stack>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {guidedFieldSpecs.map(([fieldName, spec]) => {
            const unsupported =
              spec.type === "policy_config" ||
              spec.type === "policy_config_list" ||
              spec.type === "policy_config_map";
            if (unsupported) {
              return (
                <Box key={`guided-field-${fieldName}`} sx={nestedPanelSx}>
                  <Typography sx={{ fontSize: 11, fontWeight: 600, color: "var(--app-fg)" }}>
                    {spec.label ?? fieldName}
                  </Typography>
                  <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>{spec.description}</Typography>
                  <Typography sx={{ mt: 1, fontSize: 10, color: "var(--app-muted)" }}>
                    Nested rules still use the JSON preview below. Start from the starter config and refine the preview
                    if you need compositions or resource-specific children.
                  </Typography>
                </Box>
              );
            }

            const currentValue = guidedDraft[fieldName];
            const inputValue = formatFieldInput(spec, currentValue);
            return (
              <Stack key={`guided-field-${fieldName}`} spacing={0.5}>
                <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>{spec.label ?? fieldName}</Typography>
                {spec.type === "bool" ? (
                  <FormControl fullWidth size="small" sx={fs}>
                    <Select
                      value={inputValue || String(Boolean(spec.default))}
                      onChange={(event) => onGuidedFieldChange(fieldName, event.target.value)}
                    >
                      <MenuItem value="true">True</MenuItem>
                      <MenuItem value="false">False</MenuItem>
                    </Select>
                  </FormControl>
                ) : spec.type === "enum" ? (
                  <FormControl fullWidth size="small" sx={fs}>
                    <Select
                      value={inputValue || String(spec.default ?? "")}
                      onChange={(event) => onGuidedFieldChange(fieldName, event.target.value)}
                    >
                      {(spec.enum ?? []).map((option) => (
                        <MenuItem key={`${fieldName}-${option}`} value={option}>
                          {option}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : spec.type === "json_map" || spec.type === "string_map_string_list" ? (
                  <JsonEditor value={inputValue} onChange={(next) => onGuidedFieldChange(fieldName, next)} minHeight="120px" />
                ) : (
                  <TextField
                    size="small"
                    value={inputValue}
                    onChange={(event) => onGuidedFieldChange(fieldName, event.target.value)}
                    placeholder={spec.placeholder}
                    type={spec.type === "int" ? "number" : "text"}
                    sx={fs}
                  />
                )}
                <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>{spec.description}</Typography>
              </Stack>
            );
          })}
        </Stack>

        <Box sx={{ ...nestedPanelSx, mt: 2 }}>
          <Stack
            direction="row"
            spacing={1}
            sx={{ flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}
          >
            <Typography
              sx={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Guided JSON preview
            </Typography>
            <Button
              type="button"
              variant="outlined"
              onClick={() => onLoadGuidedDraft()}
              sx={{
                borderRadius: 999,
                textTransform: "none",
                fontSize: 10,
                fontWeight: 700,
                borderColor: "var(--app-border)",
                color: "var(--app-muted)",
                "&:hover": { borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", color: "var(--app-fg)" },
              }}
            >
              Load into proposal editor
            </Button>
          </Stack>
          <Box
            component="pre"
            sx={{
              mt: 1.5,
              maxHeight: 280,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              fontSize: 11,
              lineHeight: 1.8,
              color: "var(--app-fg)",
              m: 0,
            }}
            dangerouslySetInnerHTML={{ __html: highlightJson(JSON.stringify(guidedDraft, null, 2)) }}
          />
        </Box>
      </Box>

      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Proposal editor
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            Refine or hand-edit the JSON
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Use the guided builder above or start from a quick template, then create a proposal that reviewers can approve
            before it goes live.
          </Typography>
        </Stack>

        <Box
          sx={{
            mt: 2,
            display: "grid",
            gap: 1,
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" },
          }}
        >
          {templateChoices.map((template) => {
            const selected = selectedTemplate === template.key;
            return (
              <Button
                key={template.key}
                type="button"
                onClick={() => onChooseTemplate(template.key)}
                variant={selected ? "contained" : "outlined"}
                sx={{
                  borderRadius: 3,
                  justifyContent: "flex-start",
                  alignItems: "flex-start",
                  textAlign: "left",
                  textTransform: "none",
                  p: 1.5,
                  fontSize: 11,
                  borderColor: "var(--app-border)",
                  color: selected ? "var(--app-fg)" : "var(--app-muted)",
                  bgcolor: selected ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                  boxShadow: selected ? "0 0 0 1px var(--app-accent)" : "0 0 0 1px var(--app-surface-ring)",
                  "&:hover": {
                    borderColor: "var(--app-border)",
                    bgcolor: "var(--app-hover-bg)",
                    color: "var(--app-fg)",
                  },
                }}
              >
                <Box sx={{ display: "block", width: "100%" }}>
                  <Typography sx={{ display: "block", fontWeight: 600, textTransform: "capitalize", color: "inherit" }}>
                    {template.title}
                  </Typography>
                  <Typography sx={{ mt: 0.5, display: "block", fontSize: 10, color: "var(--app-muted)" }}>
                    {template.summary}
                  </Typography>
                </Box>
              </Button>
            );
          })}
        </Box>

        <Box sx={{ mt: 2 }}>
          <JsonEditor value={createConfigText} onChange={onCreateConfigTextChange} minHeight="280px" hideValidation />
        </Box>

        <TextField
          fullWidth
          size="small"
          value={createDescription}
          onChange={(event) => onCreateDescriptionChange(event.target.value)}
          placeholder="What change should this proposal make?"
          sx={{ ...fs, mt: 1.5, "& .MuiOutlinedInput-root": { borderRadius: 999 } }}
        />

        <Button
          type="button"
          variant="contained"
          onClick={() => void onCreateProposal()}
          disabled={creating}
          sx={{
            mt: 2,
            borderRadius: 999,
            textTransform: "none",
            fontSize: 11,
            fontWeight: 700,
            bgcolor: "var(--app-accent)",
            color: "var(--app-accent-contrast)",
            "&:hover": { bgcolor: "var(--app-accent)", opacity: 0.92 },
          }}
        >
          {creating ? "Creating proposal…" : "Create proposal"}
        </Button>
      </Box>

      <Box sx={surfacePanelSx}>
        <Stack spacing={0.5}>
          <Typography
            sx={{
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Import and export
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            Move policy JSON in and out safely
          </Typography>
          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            Export the live chain or a saved version, then import a snapshot, provider list, or single rule. Imports become
            batch proposals that still go through validation, simulation, approval, and deploy.
          </Typography>
        </Stack>

        <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>
          <Button
            type="button"
            variant="contained"
            onClick={() => void onImportPolicy()}
            disabled={busyKey === "import-policy"}
            sx={{
              borderRadius: 999,
              textTransform: "none",
              fontSize: 11,
              fontWeight: 700,
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)", opacity: 0.92 },
            }}
          >
            {busyKey === "import-policy" ? "Importing…" : "Stage import as proposals"}
          </Button>
          <Button
            component="label"
            variant="outlined"
            sx={{
              borderRadius: 999,
              textTransform: "none",
              fontSize: 10,
              fontWeight: 700,
              borderColor: "var(--app-border)",
              color: "var(--app-muted)",
              cursor: "pointer",
              "&:hover": { borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", color: "var(--app-fg)" },
            }}
          >
            Load JSON file
            <Box
              component="input"
              type="file"
              accept="application/json,.json"
              onChange={(event: ChangeEvent<HTMLInputElement>) => void onImportFile(event)}
              sx={{ display: "none" }}
            />
          </Button>
        </Stack>

        <Box sx={{ mt: 2 }}>
          <JsonEditor
            value={importText}
            onChange={onImportTextChange}
            minHeight="220px"
            placeholder="Paste a policy snapshot, provider list, or single policy rule JSON."
            hideValidation
          />
        </Box>

        <TextField
          fullWidth
          size="small"
          value={importDescriptionPrefix}
          onChange={(event) => onImportDescriptionPrefixChange(event.target.value)}
          placeholder="Imported policy snapshot"
          sx={{ ...fs, mt: 1.5, "& .MuiOutlinedInput-root": { borderRadius: 999 } }}
        />

        <Box sx={{ ...nestedPanelSx, mt: 1.5 }}>
          {importPreview instanceof Error ? (
            <Typography sx={{ fontSize: 11, color: "error.light" }}>{importPreview.message}</Typography>
          ) : importPreview ? (
            <Stack spacing={1}>
              <Typography
                sx={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                  color: "var(--app-muted)",
                }}
              >
                Import preview
              </Typography>
              <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                {importPreview.label} · {importPreview.providerCount}{" "}
                {importPreview.providerCount === 1 ? "provider" : "providers"}
              </Typography>
              <Typography sx={{ fontSize: 10, color: "var(--app-muted)" }}>
                The import will stage a batch proposal against the current live chain instead of changing it directly.
              </Typography>
            </Stack>
          ) : (
            <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
              Paste JSON to see what kind of policy import it is before staging it.
            </Typography>
          )}
        </Box>

        {importPreview && !(importPreview instanceof Error) ? (
          <Button
            type="button"
            variant="outlined"
            onClick={() => onLoadIntoDraft()}
            disabled={importPreview.kind !== "single_provider"}
            sx={{
              mt: 2,
              borderRadius: 999,
              textTransform: "none",
              fontSize: 11,
              fontWeight: 700,
              borderColor: "var(--app-border)",
              color: "var(--app-muted)",
              "&:hover": { borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", color: "var(--app-fg)" },
            }}
          >
            Load single rule into draft
          </Button>
        ) : null}
      </Box>
    </Stack>
  );
}
