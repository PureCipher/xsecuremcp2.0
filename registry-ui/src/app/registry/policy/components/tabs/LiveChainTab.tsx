"use client";

import { useState } from "react";
import { Box, Button, Card, CardContent, TextField, Typography } from "@mui/material";
import type {
  PolicyConfig,
  PolicyProviderItem,
  PolicySchemaResponse,
} from "@/lib/registryClient";
import { downloadJsonFile } from "../../policyTransfer";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { JsonEditor } from "../JsonEditor";
import { ConfirmModal } from "../ConfirmModal";

type LiveChainTabProps = {
  providers: PolicyProviderItem[];
  schema: PolicySchemaResponse;
  onExportLive: () => Promise<void>;
  onDraftEdit: (index: number, config: PolicyConfig, description: string) => Promise<void>;
  onDraftRemoval: (index: number, reason: string) => Promise<void>;
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function LiveChainTab({
  providers,
  schema,
  onExportLive,
  onDraftEdit,
  onDraftRemoval,
}: LiveChainTabProps) {
  const { busyKey } = usePolicyContext();
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editTexts, setEditTexts] = useState<Record<number, string>>({});
  const [editDescriptions, setEditDescriptions] = useState<Record<number, string>>({});

  // Removal confirmation
  const [removalModal, setRemovalModal] = useState<{
    index: number;
    reason: string;
  } | null>(null);

  async function handleDraftEdit(index: number) {
    const rawText = editTexts[index] ?? prettyJson(providers[index]?.config ?? {});
    const config = JSON.parse(rawText) as PolicyConfig;
    await onDraftEdit(index, config, editDescriptions[index] ?? "");
    setEditingIndex(null);
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: "grid", gap: 0.5 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              Live policy chain
            </Typography>
            <Typography variant="h5" sx={{ fontWeight: 800, color: "var(--app-fg)" }}>
              See what is active right now
            </Typography>
            <Typography variant="body2" sx={{ maxWidth: 900, color: "var(--app-muted)" }}>
              These rules are live today. Draft a change or removal first, then approve and apply it from the Proposals tab.
            </Typography>
          </Box>

          <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => void onExportLive()}
              disabled={busyKey === "export-live"}
              sx={{
                borderRadius: 999,
                borderColor: "var(--app-border)",
                color: "var(--app-muted)",
                "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
              }}
            >
              {busyKey === "export-live" ? "Downloading…" : "Export live JSON"}
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={() => downloadJsonFile("securemcp-policy-schema.json", schema)}
              sx={{
                borderRadius: 999,
                borderColor: "var(--app-border)",
                color: "var(--app-muted)",
                "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
              }}
            >
              Download schema
            </Button>
          </Box>

          <Box sx={{ mt: 3, display: "flex", flexDirection: "column", gap: 2 }}>
            {providers.length === 0 ? (
              <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
                    No providers are active right now. Start by drafting the first rule from the Tools tab.
                  </Typography>
                </CardContent>
              </Card>
            ) : (
              providers.map((provider) => {
                const isEditing = editingIndex === provider.index;
                const editableText =
                  editTexts[provider.index] ?? prettyJson(provider.config ?? {});

                return (
                  <Card
                    key={provider.index}
                    variant="outlined"
                    sx={{
                      borderRadius: 3,
                      borderColor: "var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                      boxShadow: "none",
                    }}
                  >
                    <CardContent sx={{ p: 2.5 }}>
                      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
                        <Box sx={{ display: "grid", gap: 0.5 }}>
                          <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                            Step {provider.index + 1}
                          </Typography>
                          <Typography sx={{ fontSize: 14, fontWeight: 800, color: "var(--app-fg)" }}>
                            {provider.type}
                          </Typography>
                          <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
                            {provider.summary}
                          </Typography>
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            Policy ID: {provider.policy_id ?? "n/a"} · Version: {provider.policy_version ?? "n/a"}
                          </Typography>
                        </Box>

                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => {
                              setEditingIndex(isEditing ? null : provider.index);
                              setEditTexts((current) => ({
                                ...current,
                                [provider.index]: prettyJson(provider.config ?? {}),
                              }));
                            }}
                            disabled={!provider.editable}
                            sx={{
                              borderRadius: 999,
                              borderColor: "var(--app-border)",
                              color: "var(--app-muted)",
                              "&:hover": { bgcolor: "var(--app-hover-bg)", borderColor: "var(--app-border)" },
                            }}
                          >
                            {isEditing ? "Close draft" : provider.editable ? "Draft change" : "Read only"}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={() =>
                              setRemovalModal({ index: provider.index, reason: "No longer needed." })
                            }
                            disabled={busyKey === `remove-${provider.index}`}
                            sx={{ borderRadius: 999 }}
                          >
                            {busyKey === `remove-${provider.index}` ? "Drafting…" : "Draft removal"}
                          </Button>
                        </Box>
                      </Box>

                      {isEditing ? (
                        <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
                          <JsonEditor
                            value={editableText}
                            onChange={(newText) =>
                              setEditTexts((current) => ({
                                ...current,
                                [provider.index]: newText,
                              }))
                            }
                            minHeight="220px"
                          />
                          <TextField
                            size="small"
                            value={editDescriptions[provider.index] ?? ""}
                            onChange={(event) =>
                              setEditDescriptions((current) => ({
                                ...current,
                                [provider.index]: event.target.value,
                              }))
                            }
                            placeholder="What should change and why?"
                          />
                          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                            <Button
                              size="small"
                              variant="contained"
                              onClick={() => void handleDraftEdit(provider.index)}
                              disabled={busyKey === `draft-${provider.index}`}
                              sx={{
                                borderRadius: 999,
                                bgcolor: "var(--app-accent)",
                                color: "var(--app-accent-contrast)",
                                "&:hover": { bgcolor: "var(--app-accent)" },
                              }}
                            >
                              {busyKey === `draft-${provider.index}` ? "Saving draft…" : "Create proposal"}
                            </Button>
                          </Box>
                        </Box>
                      ) : null}
                    </CardContent>
                  </Card>
                );
              })
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Removal confirmation modal */}
      <ConfirmModal
        isOpen={removalModal !== null}
        title="Remove this rule?"
        description={
          removalModal
            ? `This will create a proposal to remove step ${removalModal.index + 1} from the live chain.`
            : ""
        }
        confirmLabel="Draft removal"
        isDangerous
        isLoading={removalModal !== null && busyKey === `remove-${removalModal.index}`}
        onConfirm={async () => {
          if (!removalModal) return;
          await onDraftRemoval(removalModal.index, removalModal.reason);
          setRemovalModal(null);
        }}
        onCancel={() => setRemovalModal(null)}
      >
        <TextField
          fullWidth
          multiline
          minRows={3}
          value={removalModal?.reason ?? ""}
          onChange={(event) =>
            setRemovalModal((prev) =>
              prev ? { ...prev, reason: event.target.value } : null,
            )
          }
          placeholder="Why should this rule be removed?"
        />
      </ConfirmModal>
    </Box>
  );
}
