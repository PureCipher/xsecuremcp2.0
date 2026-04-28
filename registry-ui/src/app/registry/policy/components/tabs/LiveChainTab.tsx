"use client";

import { useCallback, useState } from "react";
import { Box, Button, Card, CardContent, TextField, Tooltip, Typography } from "@mui/material";
import type {
  PolicyConfig,
  PolicyProviderItem,
  PolicySchemaResponse,
} from "@/lib/registryClient";
import { downloadJsonFile } from "../../policyTransfer";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { JsonEditor } from "../JsonEditor";
import { ConfirmModal } from "../ConfirmModal";

/**
 * Iter 14.20 — Live chain flow visualization.
 *
 * Originally the Live Chain panel was a vertical list of provider
 * cards; the order of providers (and therefore the order in which
 * a request hits each rule) was implied by card order but never
 * shown explicitly. For a curator skimming the page, "the chain
 * is a pipeline" wasn't legible.
 *
 * This component renders the same providers as a flow diagram
 * placed above the detail cards: an entry node ("Request"), one
 * chip per provider with arrow connectors between, and a terminal
 * outcome chip. Clicking a chip scrolls the detail card for that
 * provider into view and briefly highlights it, so the flow viz
 * acts as both an orientation device and a navigation surface.
 *
 * Responsive: horizontal row on wide screens, vertical column on
 * narrow ones. The detail cards beneath remain the action surface
 * for editing / removing individual providers.
 */
function LiveChainFlow({
  providers,
  failClosed,
}: {
  providers: PolicyProviderItem[];
  failClosed?: boolean;
}) {
  const handleJump = useCallback((index: number) => {
    const target = document.getElementById(`live-chain-step-${index}`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    // Brief highlight so the card the curator just landed on is
    // visually distinct from its neighbors. Removed after 1.5s so
    // it doesn't linger as a permanent state.
    target.dataset.flashHighlight = "true";
    window.setTimeout(() => {
      delete target.dataset.flashHighlight;
    }, 1500);
  }, []);

  if (providers.length === 0) return null;

  // Chip renders a compact node: step number + provider type + policy_id.
  // Kept narrow so 4-6 providers fit on one row at common viewport widths.
  const FlowNode = ({ provider }: { provider: PolicyProviderItem }) => (
    <Tooltip title={provider.summary || provider.type} placement="top">
      <Box
        component="button"
        type="button"
        onClick={() => handleJump(provider.index)}
        aria-label={`Jump to step ${provider.index + 1}: ${provider.type}`}
        sx={{
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 0.25,
          minWidth: 110,
          px: 1.5,
          py: 1,
          bgcolor: "var(--app-control-bg)",
          color: "var(--app-fg)",
          border: "1px solid var(--app-border)",
          borderRadius: 2,
          cursor: "pointer",
          transition: "border-color 120ms ease, background-color 120ms ease",
          "&:hover": {
            borderColor: "var(--app-accent)",
            bgcolor: "var(--app-control-active-bg)",
          },
          "&:focus-visible": {
            outline: "2px solid var(--app-accent)",
            outlineOffset: 2,
          },
        }}
      >
        <Typography
          sx={{
            fontSize: 9,
            fontWeight: 800,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Step {provider.index + 1}
        </Typography>
        <Typography
          sx={{
            fontSize: 12.5,
            fontWeight: 700,
            color: "var(--app-fg)",
            fontFamily:
              "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            lineHeight: 1.2,
            wordBreak: "break-word",
            textAlign: "center",
          }}
        >
          {provider.type}
        </Typography>
        {provider.policy_id ? (
          <Typography
            sx={{
              fontSize: 10,
              color: "var(--app-muted)",
              maxWidth: 140,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {provider.policy_id}
          </Typography>
        ) : null}
      </Box>
    </Tooltip>
  );

  // Terminal outcome chip. Without per-edge deny stats we can't
  // highlight the dominant deny path, but we *can* tell the curator
  // what happens when the chain reaches the end without an explicit
  // verdict — that's the fail-closed/fail-open default.
  const outcomeLabel = failClosed ? "Default deny" : "Default allow";
  const outcomeColors = failClosed
    ? { bg: "rgba(244, 63, 94, 0.10)", fg: "#b91c1c", border: "rgba(248, 113, 113, 0.4)" }
    : { bg: "var(--app-control-active-bg)", fg: "var(--app-fg)", border: "var(--app-accent)" };

  return (
    <Box
      sx={{
        mt: 3,
        p: 2,
        border: "1px solid var(--app-border)",
        borderRadius: 3,
        bgcolor: "var(--app-surface)",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          mb: 1.5,
          gap: 1,
          flexWrap: "wrap",
        }}
      >
        <Typography
          sx={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "var(--app-muted)",
          }}
        >
          Pipeline
        </Typography>
        <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
          Request flows top-to-bottom on narrow screens, left-to-right on wide ones.
        </Typography>
      </Box>
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          alignItems: { xs: "stretch", md: "center" },
          gap: 1,
          overflowX: { md: "auto" },
          py: 0.5,
        }}
      >
        {/* Entry node: where the request enters */}
        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: 82,
            px: 1.25,
            py: 1,
            bgcolor: "var(--app-control-bg)",
            border: "1px dashed var(--app-border)",
            borderRadius: 2,
            color: "var(--app-muted)",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Request
        </Box>
        <FlowArrow />

        {providers.map((provider, idx) => (
          <Box
            key={provider.index}
            sx={{
              display: "flex",
              flexDirection: { xs: "column", md: "row" },
              alignItems: "center",
              gap: 1,
            }}
          >
            <FlowNode provider={provider} />
            {idx < providers.length - 1 ? <FlowArrow /> : <FlowArrow />}
          </Box>
        ))}

        {/* Terminal outcome */}
        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: 110,
            px: 1.5,
            py: 1,
            bgcolor: outcomeColors.bg,
            border: `1px solid ${outcomeColors.border}`,
            borderRadius: 2,
            color: outcomeColors.fg,
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {outcomeLabel}
        </Box>
      </Box>
    </Box>
  );
}

/**
 * Iter 14.20 — Arrow connector between flow nodes. Rotates between
 * "right" (horizontal layout, ≥md) and "down" (vertical layout, <md)
 * via responsive transform.
 */
function FlowArrow() {
  return (
    <Box
      aria-hidden
      sx={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--app-muted)",
        flexShrink: 0,
      }}
    >
      <Box
        component="svg"
        width={20}
        height={20}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        sx={{
          transform: { xs: "rotate(90deg)", md: "none" },
        }}
      >
        <line x1={5} y1={12} x2={19} y2={12} />
        <polyline points="13 6 19 12 13 18" />
      </Box>
    </Box>
  );
}

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

          {/* Iter 14.20 — Flow visualization band. Rendered above the
              detail cards so the chain order is the first thing the
              curator sees. ``failClosed`` would normally come from
              policy state, but LiveChainTab doesn't receive it; the
              terminal node defaults to "Default allow" until that
              prop is plumbed through. */}
          <LiveChainFlow providers={providers} />

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
                    id={`live-chain-step-${provider.index}`}
                    variant="outlined"
                    sx={{
                      borderRadius: 3,
                      borderColor: "var(--app-border)",
                      bgcolor: "var(--app-control-bg)",
                      boxShadow: "none",
                      // Iter 14.20 — flash-highlight when reached via
                      // the flow chip click. The data-attribute is
                      // toggled imperatively in handleJump above; CSS
                      // here drives the visual feedback.
                      transition:
                        "border-color 600ms ease, box-shadow 600ms ease",
                      "&[data-flash-highlight=\"true\"]": {
                        borderColor: "var(--app-accent)",
                        boxShadow:
                          "0 0 0 2px rgba(99, 102, 241, 0.18)",
                      },
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
