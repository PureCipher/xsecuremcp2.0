"use client";

import { useState } from "react";
import type {
  PolicyVersionDiffResponse,
} from "@/lib/registryClient";
import { Box, Button, Card, CardContent, Chip, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from "@mui/material";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { highlightJson } from "../JsonEditor";
import { ConfirmModal } from "../ConfirmModal";

type VersionItem = {
  version_id: string;
  version_number: number;
  description?: string;
  author?: string;
  created_at?: string;
};

type VersionsTabProps = {
  versions: VersionItem[];
  currentVersion: number | null;
  onExportVersion: (versionNumber?: number) => Promise<void>;
  onRollback: (versionNumber: number, reason: string) => Promise<void>;
  onLoadDiff: (v1: number, v2: number) => Promise<PolicyVersionDiffResponse | null>;
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function VersionsTab({
  versions,
  currentVersion,
  onExportVersion,
  onRollback,
  onLoadDiff,
}: VersionsTabProps) {
  const { busyKey } = usePolicyContext();

  const sortedVersions = versions
    .slice()
    .sort((left, right) => right.version_number - left.version_number);
  const versionNumbers = sortedVersions.map((v) => v.version_number);

  const [rollbackModal, setRollbackModal] = useState<number | null>(null);
  const [rollbackReason, setRollbackReason] = useState("");
  const [diffFrom, setDiffFrom] = useState<number | "">(
    versionNumbers[1] ?? versionNumbers[0] ?? "",
  );
  const [diffTo, setDiffTo] = useState<number | "">(versionNumbers[0] ?? "");
  const [diffLoading, setDiffLoading] = useState(false);
  const [versionDiff, setVersionDiff] = useState<PolicyVersionDiffResponse | null>(null);

  async function handleLoadDiff() {
    if (diffFrom === "" || diffTo === "") return;
    setDiffLoading(true);
    try {
      const result = await onLoadDiff(diffFrom, diffTo);
      setVersionDiff(result);
    } finally {
      setDiffLoading(false);
    }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Version history */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Version history
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              Roll back with confidence
            </Typography>
            <Typography sx={{ maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
              Every live apply creates a saved version of the policy chain. Roll back when a change needs to be reversed quickly.
            </Typography>
          </Box>

          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            {versions.length === 0 ? (
              <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    No saved versions yet. The first live policy change will create one automatically.
                  </Typography>
                </CardContent>
              </Card>
            ) : (
              sortedVersions.map((version) => {
                const isCurrent = version.version_number === currentVersion;
                return (
                  <Card
                    key={version.version_id}
                    variant="outlined"
                    sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}
                  >
                    <CardContent sx={{ p: 2 }}>
                      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, justifyContent: "space-between", alignItems: "flex-start" }}>
                        <Box sx={{ display: "grid", gap: 0.5, minWidth: 240 }}>
                          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                            <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                              Version {version.version_number}
                            </Typography>
                            {isCurrent ? (
                              <Chip
                                size="small"
                                label="Live now"
                                sx={{
                                  borderRadius: 999,
                                  bgcolor: "var(--app-control-active-bg)",
                                  color: "var(--app-fg)",
                                  fontSize: 10,
                                  fontWeight: 800,
                                  textTransform: "uppercase",
                                  letterSpacing: "0.12em",
                                }}
                              />
                            ) : null}
                          </Box>
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            {version.description || "No description recorded."}
                          </Typography>
                          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                            Saved by {version.author || "unknown"} · {formatTimestamp(version.created_at)}
                          </Typography>
                        </Box>

                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                          <Button
                            type="button"
                            variant="outlined"
                            size="small"
                            onClick={() => void onExportVersion(version.version_number)}
                            disabled={busyKey === `export-${version.version_number}`}
                            sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                          >
                            {busyKey === `export-${version.version_number}` ? "Downloading…" : "Export JSON"}
                          </Button>
                          {!isCurrent ? (
                            <Button
                              type="button"
                              variant="outlined"
                              size="small"
                              onClick={() => {
                                setRollbackReason("");
                                setRollbackModal(version.version_number);
                              }}
                              disabled={busyKey === `rollback-${version.version_number}`}
                              sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
                            >
                              {busyKey === `rollback-${version.version_number}` ? "Rolling back…" : "Roll back"}
                            </Button>
                          ) : null}
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Version diff */}
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 2.5 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography sx={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--app-muted)" }}>
              Version diff
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
              See what changed
            </Typography>
            <Typography sx={{ maxWidth: 720, fontSize: 12, color: "var(--app-muted)" }}>
              Compare two saved versions before you roll back or stage another change.
            </Typography>
          </Box>

          {versionNumbers.length < 2 ? (
            <Card variant="outlined" sx={{ mt: 2, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
              <CardContent sx={{ p: 2 }}>
                <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                  You need at least two saved versions before comparison is useful.
                </Typography>
              </CardContent>
            </Card>
          ) : (
            <>
              <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr auto" }, alignItems: "end" }}>
                <FormControl size="small" fullWidth>
                  <InputLabel id="policy-diff-from">From version</InputLabel>
                  <Select
                    labelId="policy-diff-from"
                    label="From version"
                    value={diffFrom}
                    onChange={(event) => setDiffFrom(Number(event.target.value))}
                  >
                    {versionNumbers.map((versionNumber) => (
                      <MenuItem key={`from-${versionNumber}`} value={versionNumber}>
                        Version {versionNumber}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <FormControl size="small" fullWidth>
                  <InputLabel id="policy-diff-to">To version</InputLabel>
                  <Select
                    labelId="policy-diff-to"
                    label="To version"
                    value={diffTo}
                    onChange={(event) => setDiffTo(Number(event.target.value))}
                  >
                    {versionNumbers.map((versionNumber) => (
                      <MenuItem key={`to-${versionNumber}`} value={versionNumber}>
                        Version {versionNumber}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Button
                  type="button"
                  variant="contained"
                  onClick={() => void handleLoadDiff()}
                  disabled={diffLoading}
                  sx={{ borderRadius: 999 }}
                >
                  {diffLoading ? "Comparing…" : "Compare"}
                </Button>
              </Box>

              <Card variant="outlined" sx={{ mt: 2, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  {versionDiff?.diff ? (
                    <Box
                      component="pre"
                      sx={{
                        maxHeight: 360,
                        overflow: "auto",
                        whiteSpace: "pre-wrap",
                        overflowWrap: "anywhere",
                        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        fontSize: 12,
                        lineHeight: 1.8,
                        color: "var(--app-fg)",
                        m: 0,
                      }}
                      dangerouslySetInnerHTML={{
                        __html: highlightJson(prettyJson(versionDiff.diff)),
                      }}
                    />
                  ) : (
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      Choose two versions to inspect the saved diff before you act on it.
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </CardContent>
      </Card>

      {/* Rollback confirmation modal */}
      <ConfirmModal
        isOpen={rollbackModal !== null}
        title={`Roll back to version ${rollbackModal}?`}
        description="This will revert the live policy chain to the selected version. A new version entry will be created."
        confirmLabel="Roll back"
        isDangerous
        isLoading={rollbackModal !== null && busyKey === `rollback-${rollbackModal}`}
        onConfirm={async () => {
          if (rollbackModal === null) return;
          await onRollback(rollbackModal, rollbackReason);
          setRollbackModal(null);
        }}
        onCancel={() => setRollbackModal(null)}
      >
        <TextField
          value={rollbackReason}
          onChange={(event) => setRollbackReason(event.target.value)}
          placeholder="Why are you rolling back?"
          size="small"
          fullWidth
        />
      </ConfirmModal>
    </Box>
  );
}
