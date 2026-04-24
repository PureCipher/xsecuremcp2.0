"use client";

import { useState, useMemo } from "react";
import type {
  PolicyMigrationPreviewResponse,
} from "@/lib/registryClient";
import { Box, Button, Card, CardContent, Chip, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";
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

function migrationRiskSx(level: string | undefined): Record<string, unknown> {
  switch (level?.toLowerCase()) {
    case "critical":
      return { bgcolor: "rgba(239, 68, 68, 0.12)", color: "rgb(254, 202, 202)", border: "1px solid rgba(248, 113, 113, 0.45)" };
    case "high":
      return { bgcolor: "rgba(244, 63, 94, 0.12)", color: "rgb(254, 205, 211)", border: "1px solid rgba(251, 113, 133, 0.45)" };
    case "medium":
      return { bgcolor: "rgba(245, 158, 11, 0.12)", color: "rgb(253, 230, 138)", border: "1px solid rgba(251, 191, 36, 0.45)" };
    case "low":
      return { bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", border: "1px solid var(--app-accent)" };
    default:
      return { bgcolor: "rgba(113, 113, 122, 0.12)", color: "rgb(228, 228, 231)", border: "1px solid rgba(161, 161, 170, 0.35)" };
  }
}

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
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Environment promotion */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Environment promotion
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Move policy safely across development, staging, and production
            </Typography>
            <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
              Capture a baseline for each environment, preview the change, then stage a promotion proposal through the same approval workflow.
            </Typography>
          </Box>

          <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1.5, alignItems: "center" }}>
            <FormControl size="small" sx={{ minWidth: 220 }}>
              <InputLabel id="capture-source">Capture source</InputLabel>
              <Select
                labelId="capture-source"
                label="Capture source"
                value={captureSource}
                onChange={(event) => setCaptureSource(String(event.target.value))}
              >
                <MenuItem value="live">Live policy chain</MenuItem>
                {versionNumbers.map((vn) => (
                  <MenuItem key={`capture-source-${vn}`} value={`version:${vn}`}>
                    Version {vn}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr 1fr" } }}>
            {environments.map((environment) => (
              <Card
                key={environment.environment_id}
                variant="outlined"
                sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
              >
                <CardContent sx={{ p: 2 }}>
                  <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                    <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                      {environment.title ?? environment.environment_id}
                    </Typography>
                    <Chip
                      size="small"
                      label={`v${String(environment.current_version_number ?? "—")}`}
                      sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em" }}
                    />
                  </Box>
                  <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                    {environment.description}
                  </Typography>
                  <Typography sx={{ mt: 1.5, fontSize: 11, color: "var(--app-muted)" }}>
                    {environment.current_source_label ?? "No captured baseline yet"}
                  </Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                    Captures: {String(environment.capture_count ?? 0)}
                  </Typography>
                  <Box sx={{ mt: 1.5 }}>
                    <Button
                      type="button"
                      variant="outlined"
                      size="small"
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
                      sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                    >
                      {busyKey === `capture-${environment.environment_id}` ? "Capturing…" : "Capture baseline"}
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            ))}
          </Box>

          <Card variant="outlined" sx={{ mt: 2.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
            <CardContent sx={{ p: 2 }}>
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr 1fr" } }}>
                <FormControl size="small" fullWidth>
                  <InputLabel id="promotion-source-env">Source environment</InputLabel>
                  <Select
                    labelId="promotion-source-env"
                    label="Source environment"
                    value={promotionSourceEnvironment}
                    onChange={(event) => setPromotionSourceEnvironment(String(event.target.value))}
                  >
                    {environments.map((env) => (
                      <MenuItem key={`promotion-source-${env.environment_id}`} value={env.environment_id}>
                        {env.title ?? env.environment_id}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl size="small" fullWidth>
                  <InputLabel id="promotion-target-env">Target environment</InputLabel>
                  <Select
                    labelId="promotion-target-env"
                    label="Target environment"
                    value={promotionTargetEnvironment}
                    onChange={(event) => setPromotionTargetEnvironment(String(event.target.value))}
                  >
                    {environments.map((env) => (
                      <MenuItem key={`promotion-target-${env.environment_id}`} value={env.environment_id}>
                        {env.title ?? env.environment_id}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <TextField
                  label="Promotion note"
                  value={promotionDescription}
                  onChange={(event) => setPromotionDescription(event.target.value)}
                  placeholder="Why is this moving forward?"
                  size="small"
                  fullWidth
                />
              </Box>

              <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
                <Button
                  type="button"
                  variant="outlined"
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
                    setMigrationTarget(targetVersion ? `version:${targetVersion}` : "live");
                    setMigrationEnvironment(promotionTargetEnvironment);
                    void handlePreviewMigration();
                  }}
                  disabled={busyKey === "migration-preview"}
                  sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                >
                  {busyKey === "migration-preview" ? "Previewing…" : "Preview environment promotion"}
                </Button>
                <Button
                  type="button"
                  variant="contained"
                  onClick={() => void onStagePromotion(promotionSourceEnvironment, promotionTargetEnvironment, promotionDescription)}
                  disabled={busyKey === "stage-promotion"}
                  sx={{ borderRadius: 999 }}
                >
                  {busyKey === "stage-promotion" ? "Staging…" : "Stage promotion"}
                </Button>
              </Box>
            </CardContent>
          </Card>

          <Box sx={{ mt: 2.5, display: "grid", gap: 1.5 }}>
            <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Recent promotion activity
            </Typography>
            {promotions.length === 0 ? (
              <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    No promotions have been staged yet.
                  </Typography>
                </CardContent>
              </Card>
            ) : (
              promotions.slice(0, 5).map((promotion) => (
                <Card
                  key={promotion.promotion_id}
                  variant="outlined"
                  sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
                >
                  <CardContent sx={{ p: 2 }}>
                    <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                        {promotion.source_environment ?? "source"} → {promotion.target_environment ?? "target"}
                      </Typography>
                      <Chip
                        size="small"
                        label={promotion.status ?? "staged"}
                        sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em" }}
                      />
                    </Box>
                    <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                      {promotion.note || "Promotion tracked through proposal governance."}
                    </Typography>
                    <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>
                      Source v{String(promotion.source_version_number ?? "—")}
                      {promotion.deployed_version_number ? ` · deployed as v${String(promotion.deployed_version_number)}` : ""}
                    </Typography>
                  </CardContent>
                </Card>
              ))
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Migration preview */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Migration preview
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Plan promotion between versions and environments
            </Typography>
            <Typography sx={{ maxWidth: 900, fontSize: 12, color: "var(--app-muted)" }}>
              Compare a live chain or saved version against the current target and see what will change, what is risky, and what the chosen environment expects.
            </Typography>
          </Box>

          <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr 1fr auto" }, alignItems: "end" }}>
            <FormControl size="small" fullWidth>
              <InputLabel id="migration-source">Source</InputLabel>
              <Select
                labelId="migration-source"
                label="Source"
                value={migrationSource}
                onChange={(event) => setMigrationSource(String(event.target.value))}
              >
                <MenuItem value="live">Live policy</MenuItem>
                {versionNumbers.map((vn) => (
                  <MenuItem key={`migration-source-${vn}`} value={`version:${vn}`}>
                    Version {vn}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" fullWidth>
              <InputLabel id="migration-target">Compare against</InputLabel>
              <Select
                labelId="migration-target"
                label="Compare against"
                value={migrationTarget}
                onChange={(event) => setMigrationTarget(String(event.target.value))}
              >
                <MenuItem value="live">Current live chain</MenuItem>
                {versionNumbers.map((vn) => (
                  <MenuItem key={`migration-target-${vn}`} value={`version:${vn}`}>
                    Version {vn}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" fullWidth>
              <InputLabel id="migration-env">Target environment</InputLabel>
              <Select
                labelId="migration-env"
                label="Target environment"
                value={migrationEnvironment}
                onChange={(event) => setMigrationEnvironment(String(event.target.value))}
              >
                {environments.map((env) => (
                  <MenuItem key={env.environment_id} value={env.environment_id}>
                    {env.title ?? env.environment_id}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Button
              type="button"
              variant="contained"
              onClick={() => void handlePreviewMigration()}
              disabled={busyKey === "migration-preview"}
              sx={{ borderRadius: 999 }}
            >
              {busyKey === "migration-preview" ? "Previewing…" : "Preview migration"}
            </Button>
          </Box>

          <Card variant="outlined" sx={{ mt: 2, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
            <CardContent sx={{ p: 2 }}>
              {migrationPreview?.summary ? (
                <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,0.9fr) minmax(0,1.1fr)" } }}>
                  <Box sx={{ display: "grid", gap: 2 }}>
                    <Box>
                      <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Migration summary
                      </Typography>
                      <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                        {migrationPreview.source?.label} → {migrationPreview.target?.label}
                      </Typography>
                      <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                        {String((migrationPreview.summary.changed_count as number | undefined) ?? 0)} changed ·{" "}
                        {String((migrationPreview.summary.added_count as number | undefined) ?? 0)} added ·{" "}
                        {String((migrationPreview.summary.removed_count as number | undefined) ?? 0)} removed
                      </Typography>
                    </Box>

                    <Box>
                      <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Environment fit
                      </Typography>
                      <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                        {migrationPreview.environment?.description}
                      </Typography>
                      {(migrationPreview.environment?.required_controls ?? []).length > 0 ? (
                        <Box component="ul" sx={{ listStyle: "disc", pl: 2, mt: 1, mb: 0, color: "var(--app-muted)", fontSize: 11, display: "grid", gap: 0.5 }}>
                          {(migrationPreview.environment?.required_controls ?? []).map((item) => (
                            <li key={`required-control-${item}`}>{item}</li>
                          ))}
                        </Box>
                      ) : null}
                    </Box>
                  </Box>

                  <Box sx={{ display: "grid", gap: 2 }}>
                    <Box>
                      <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Recommendations
                      </Typography>
                      {(migrationPreview.recommendations ?? []).length > 0 ? (
                        <Box component="ul" sx={{ listStyle: "disc", pl: 2, mt: 1, mb: 0, color: "var(--app-muted)", fontSize: 12, display: "grid", gap: 0.5 }}>
                          {(migrationPreview.recommendations ?? []).map((item) => (
                            <li key={`migration-recommendation-${item}`}>{item}</li>
                          ))}
                        </Box>
                      ) : (
                        <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                          No recommendations.
                        </Typography>
                      )}
                    </Box>

                    {(migrationPreview.risks ?? []).length > 0 ? (
                      <Box>
                        <Typography sx={{ fontSize: 10, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                          Risks
                        </Typography>
                        <Box sx={{ mt: 1, display: "grid", gap: 1 }}>
                          {(migrationPreview.risks ?? []).slice(0, 4).map((risk, index) => (
                            <Card
                              key={`migration-risk-${index}`}
                              variant="outlined"
                              sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}
                            >
                              <CardContent sx={{ p: 1.5 }}>
                                <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                                  <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                                    {risk.title}
                                  </Typography>
                                  <Chip
                                    size="small"
                                    label={risk.level}
                                    sx={{
                                      borderRadius: 999,
                                      fontSize: 10,
                                      fontWeight: 800,
                                      textTransform: "uppercase",
                                      letterSpacing: "0.12em",
                                      height: 22,
                                      ...migrationRiskSx(risk.level),
                                    }}
                                  />
                                </Box>
                                <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                                  {risk.detail}
                                </Typography>
                              </CardContent>
                            </Card>
                          ))}
                        </Box>
                      </Box>
                    ) : null}
                  </Box>
                </Box>
              ) : (
                <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                  Choose a source, comparison target, and environment profile to preview promotion risk.
                </Typography>
              )}
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </Box>
  );
}
