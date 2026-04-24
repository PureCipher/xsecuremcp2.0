"use client";

import { useState, useMemo, useEffect, type ChangeEvent } from "react";
import type { PolicyConfig, PolicyPlugin, PolicySchemaResponse } from "@/lib/registryClient";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";
import { parseImportedPolicyJson } from "../../policyTransfer";
import { usePolicyContext } from "../../contexts/PolicyContext";
import { GuidedPolicyBuilder } from "../GuidedPolicyBuilder";
import { JsonEditor } from "../JsonEditor";
import { ConfirmModal } from "../ConfirmModal";

type TemplateChoice = {
  key: string;
  title: string;
  summary: string;
  config: PolicyConfig;
  jurisdiction: string | null;
  category: string;
  version: string | null;
};

type PackItem = {
  pack_id: string;
  title?: string;
  summary?: string;
  description?: string;
  owner?: string;
  provider_count?: number;
  current_revision_number?: number;
  revision_count?: number;
  provider_summaries?: string[];
  snapshot?: { providers?: PolicyConfig[] };
};

type ToolsTabProps = {
  schema: PolicySchemaResponse;
  packs: PackItem[];
  versionNumbers: number[];
  onCreateProposal: (payload: {
    action: "add" | "swap" | "remove" | "replace_chain";
    config?: PolicyConfig;
    targetIndex?: number;
    description: string;
  }) => Promise<void>;
  onImportPolicy: (snapshot: unknown, descriptionPrefix: string) => Promise<void>;
  onSavePack: (body: Record<string, unknown>) => Promise<void>;
  onDeletePack: (packId: string) => Promise<void>;
  onStagePack: (packId: string, title: string) => Promise<void>;
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ToolsTab({
  schema,
  packs,
  versionNumbers,
  onCreateProposal,
  onImportPolicy,
  onSavePack,
  onDeletePack,
  onStagePack,
}: ToolsTabProps) {
  const { busyKey, setBanner } = usePolicyContext();

  const [plugins, setPlugins] = useState<PolicyPlugin[]>([]);
  const [pluginFilter, setPluginFilter] = useState<string>("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/api/policy/plugins");
        if (response.ok) {
          const data = await response.json();
          if (!cancelled && Array.isArray(data?.plugins)) {
            setPlugins(data.plugins as PolicyPlugin[]);
          }
        }
      } catch {
        // Fall back to schema-derived templates
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const [createTemplate, setCreateTemplate] = useState<string>("allowlist");
  const [createConfigText, setCreateConfigText] = useState("{}");
  const [createDescription, setCreateDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const [importText, setImportText] = useState("");
  const [importDescriptionPrefix, setImportDescriptionPrefix] = useState("Imported policy snapshot");

  const [packSource, setPackSource] = useState<string>("editor");
  const [packTitle, setPackTitle] = useState("");
  const [packSummary, setPackSummary] = useState("");
  const [packDescription, setPackDescription] = useState("");
  const [packTags, setPackTags] = useState("");
  const [packEnvironments, setPackEnvironments] = useState("");

  const [deletePackModal, setDeletePackModal] = useState<{ id: string; title: string } | null>(null);

  const templateChoices = useMemo(() => {
    const choices: TemplateChoice[] = [];

    if (plugins.length > 0) {
      for (const plugin of plugins) {
        choices.push({
          key: plugin.type_key,
          title: plugin.display_name || plugin.type_key.replaceAll("_", " "),
          summary: plugin.description || "Policy type",
          config: plugin.starter_config,
          jurisdiction: plugin.jurisdiction,
          category: plugin.category,
          version: plugin.version || null,
        });
      }
    } else if (schema?.policy_types) {
      for (const [typeKey, typeInfo] of Object.entries(schema.policy_types)) {
        choices.push({
          key: typeKey,
          title: typeKey.replaceAll("_", " "),
          summary: typeInfo.description ?? "Policy type",
          config: typeInfo.starter_config ?? { type: typeKey },
          jurisdiction: null,
          category: "general",
          version: null,
        });
      }
    }

    return choices;
  }, [plugins, schema]);

  const jurisdictions = useMemo(() => {
    const set = new Set<string>();
    for (const choice of templateChoices) {
      if (choice.jurisdiction) set.add(choice.jurisdiction);
    }
    return Array.from(set).sort();
  }, [templateChoices]);

  const filteredTemplates = useMemo(() => {
    if (pluginFilter === "all") return templateChoices;
    if (pluginFilter === "universal") return templateChoices.filter((c) => !c.jurisdiction);
    return templateChoices.filter((c) => c.jurisdiction === pluginFilter);
  }, [templateChoices, pluginFilter]);

  useEffect(() => {
    if (templateChoices.length > 0 && createConfigText === "{}") {
      const first = templateChoices[0];
      if (first) {
        setCreateTemplate(first.key);
        setCreateConfigText(prettyJson(first.config));
      }
    }
  }, [templateChoices, createConfigText]);

  const importPreview = useMemo(() => {
    try {
      return parseImportedPolicyJson(importText);
    } catch (error) {
      return error instanceof Error ? error : new Error("Invalid JSON");
    }
  }, [importText]);

  function chooseTemplate(key: string) {
    setCreateTemplate(key);
    const choice = templateChoices.find((c) => c.key === key);
    if (choice) {
      setCreateConfigText(prettyJson(choice.config));
    }
  }

  async function handleCreateProposal() {
    setCreating(true);
    try {
      const config = JSON.parse(createConfigText) as PolicyConfig;
      await onCreateProposal({
        action: "add",
        config,
        description: createDescription,
      });
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to create policy proposal.",
      });
    } finally {
      setCreating(false);
    }
  }

  function handleLoadIntoDraft() {
    if (!(importPreview && !(importPreview instanceof Error))) {
      setBanner({
        tone: "error",
        message: "Paste a single policy rule JSON object before loading it into the draft editor.",
      });
      return;
    }

    const config = importPreview.snapshot.providers?.[0];
    if (!config || importPreview.kind !== "single_provider") {
      setBanner({
        tone: "error",
        message: "Only a single policy rule can be loaded directly into the draft editor.",
      });
      return;
    }

    setCreateConfigText(prettyJson(config));
    setCreateDescription(importDescriptionPrefix);
    setBanner({
      tone: "success",
      message: "Loaded the imported rule into the draft editor.",
    });
  }

  async function handleImportPolicy() {
    if (!importText.trim()) {
      setBanner({ tone: "error", message: "Paste policy JSON before importing it." });
      return;
    }
    if (importPreview instanceof Error) {
      setBanner({ tone: "error", message: importPreview.message });
      return;
    }
    if (!importPreview) {
      setBanner({ tone: "error", message: "Paste policy JSON before importing it." });
      return;
    }
    await onImportPolicy(importPreview.snapshot, importDescriptionPrefix);
  }

  async function handleImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      setImportText(text);
      setBanner({
        tone: "success",
        message: `Loaded ${file.name}. Review the preview before importing it.`,
      });
    } catch {
      setBanner({ tone: "error", message: "Unable to read the selected JSON file." });
    } finally {
      event.target.value = "";
    }
  }

  function handleLoadPackIntoDraft(pack: PackItem) {
    const providers = pack.snapshot?.providers ?? [];
    if (providers.length === 1) {
      setCreateConfigText(prettyJson(providers[0] ?? {}));
      setCreateDescription(pack.title ?? "Saved pack draft");
      setBanner({
        tone: "success",
        message: "Loaded the saved pack into the proposal editor.",
      });
      return;
    }
    setImportText(prettyJson(pack.snapshot ?? {}));
    setImportDescriptionPrefix(pack.title ?? "Imported policy snapshot");
    setBanner({
      tone: "success",
      message: "Loaded the saved pack into the import area. Batch packs stage best through import.",
    });
  }

  async function handleSavePack() {
    if (!packTitle.trim()) {
      setBanner({ tone: "error", message: "Add a title before saving a private pack." });
      return;
    }

    let body: Record<string, unknown> = {
      title: packTitle,
      summary: packSummary,
      description: packDescription,
      tags: splitCsv(packTags),
      recommended_environments: splitCsv(packEnvironments),
      note: `Saved from ${packSource}`,
    };

    if (packSource === "editor") {
      try {
        const parsed = JSON.parse(createConfigText) as PolicyConfig;
        body = {
          ...body,
          snapshot: {
            format: "securemcp-policy-set/v1",
            providers: [parsed],
            metadata: { source: "policy_editor" },
          },
        };
      } catch {
        setBanner({
          tone: "error",
          message: "The proposal editor JSON must be valid before it can be saved as a pack.",
        });
        return;
      }
    } else if (packSource.startsWith("version:")) {
      body = {
        ...body,
        source_version_number: Number(packSource.replace("version:", "")),
      };
    }

    await onSavePack(body);
  }

  return (
    <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", xl: "minmax(0,1.2fr) minmax(0,0.8fr)" } }}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <GuidedPolicyBuilder
          schema={schema}
          onLoadDraft={(configText) => {
            setCreateConfigText(configText);
          }}
        />

        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Box sx={{ display: "grid", gap: 0.5 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Proposal editor
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Refine or hand-edit the JSON
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Use the guided builder above or start from a quick template, then create a proposal that reviewers can approve before it goes live.
              </Typography>
            </Box>

            {jurisdictions.length > 0 ? (
              <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "var(--app-muted)" }}>
                  Filter:
                </Typography>
                <Button
                  type="button"
                  size="small"
                  variant={pluginFilter === "all" ? "contained" : "outlined"}
                  onClick={() => setPluginFilter("all")}
                  sx={{
                    borderRadius: 999,
                    textTransform: "none",
                    fontSize: 11,
                    fontWeight: 800,
                    ...(pluginFilter === "all"
                      ? {}
                      : { borderColor: "var(--app-border)", color: "var(--app-muted)", "&:hover": { bgcolor: "var(--app-hover-bg)" } }),
                  }}
                >
                  All
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant={pluginFilter === "universal" ? "contained" : "outlined"}
                  onClick={() => setPluginFilter("universal")}
                  sx={{
                    borderRadius: 999,
                    textTransform: "none",
                    fontSize: 11,
                    fontWeight: 800,
                    ...(pluginFilter === "universal"
                      ? {}
                      : { borderColor: "var(--app-border)", color: "var(--app-muted)", "&:hover": { bgcolor: "var(--app-hover-bg)" } }),
                  }}
                >
                  Universal
                </Button>
                {jurisdictions.map((j) => (
                  <Button
                    key={j}
                    type="button"
                    size="small"
                    variant={pluginFilter === j ? "contained" : "outlined"}
                    onClick={() => setPluginFilter(j)}
                    sx={{
                      borderRadius: 999,
                      textTransform: "none",
                      fontSize: 11,
                      fontWeight: 800,
                      ...(pluginFilter === j
                        ? {}
                        : { borderColor: "var(--app-border)", color: "var(--app-muted)", "&:hover": { bgcolor: "var(--app-hover-bg)" } }),
                    }}
                  >
                    {j}
                  </Button>
                ))}
              </Box>
            ) : null}

            <Box sx={{ mt: 2, display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              {filteredTemplates.map((template) => (
                <Button
                  key={template.key}
                  type="button"
                  onClick={() => chooseTemplate(template.key)}
                  variant="outlined"
                  sx={{
                    borderRadius: 3,
                    p: 1.5,
                    textAlign: "left",
                    textTransform: "none",
                    justifyContent: "flex-start",
                    borderColor: "var(--app-border)",
                    bgcolor: createTemplate === template.key ? "var(--app-control-active-bg)" : "var(--app-control-bg)",
                    color: createTemplate === template.key ? "var(--app-fg)" : "var(--app-muted)",
                    "&:hover": { bgcolor: "var(--app-hover-bg)", color: "var(--app-fg)" },
                  }}
                >
                  <Box sx={{ display: "grid", gap: 0.75, width: "100%" }}>
                    <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 800, textTransform: "capitalize", color: "inherit" }}>
                        {template.title}
                      </Typography>
                      {template.jurisdiction ? (
                        <Chip
                          size="small"
                          label={template.jurisdiction}
                          sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em" }}
                        />
                      ) : null}
                      {template.version ? (
                        <Chip
                          size="small"
                          label={`v${template.version}`}
                          sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 9, fontWeight: 700 }}
                        />
                      ) : null}
                    </Box>
                    <Typography sx={{ fontSize: 11, lineHeight: 1.35, color: "inherit" }}>
                      {template.summary.length > 80 ? `${template.summary.slice(0, 80)}…` : template.summary}
                    </Typography>
                  </Box>
                </Button>
              ))}
            </Box>

            <Box sx={{ mt: 2 }}>
              <JsonEditor value={createConfigText} onChange={setCreateConfigText} minHeight="280px" />
            </Box>

            <TextField
              value={createDescription}
              onChange={(event) => setCreateDescription(event.target.value)}
              placeholder="What change should this proposal make?"
              size="small"
              fullWidth
              sx={{ mt: 1.5 }}
            />

            <Button
              type="button"
              variant="contained"
              onClick={() => void handleCreateProposal()}
              disabled={creating || busyKey === "create-proposal"}
              sx={{ mt: 2, borderRadius: 999 }}
            >
              {creating || busyKey === "create-proposal" ? "Creating proposal…" : "Create proposal"}
            </Button>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Box sx={{ display: "grid", gap: 0.5 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Import and export
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Move policy JSON in and out safely
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Export the live chain or a saved version, then import a snapshot, provider list, or single rule. Imports become batch proposals that still go through validation, simulation, approval, and deploy.
              </Typography>
            </Box>

            <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Button
                type="button"
                variant="contained"
                onClick={() => void handleImportPolicy()}
                disabled={busyKey === "import-policy"}
                sx={{ borderRadius: 999 }}
              >
                {busyKey === "import-policy" ? "Importing…" : "Stage import as proposals"}
              </Button>

              <Button component="label" variant="outlined" sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}>
                Load JSON file
                <Box component="input" type="file" accept="application/json,.json" hidden onChange={(event) => void handleImportFile(event)} />
              </Button>
            </Box>

            <Box sx={{ mt: 2 }}>
              <JsonEditor
                value={importText}
                onChange={setImportText}
                minHeight="220px"
                placeholder="Paste a policy snapshot, provider list, or single policy rule JSON."
              />
            </Box>

            <TextField
              value={importDescriptionPrefix}
              onChange={(event) => setImportDescriptionPrefix(event.target.value)}
              placeholder="Imported policy snapshot"
              size="small"
              fullWidth
              sx={{ mt: 1.5 }}
            />

            <Card variant="outlined" sx={{ mt: 1.5, borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
              <CardContent sx={{ p: 2 }}>
                {importPreview instanceof Error ? (
                  <Typography sx={{ fontSize: 12, color: "rgb(254, 205, 211)" }}>{importPreview.message}</Typography>
                ) : importPreview ? (
                  <Box sx={{ display: "grid", gap: 1 }}>
                    <Typography variant="overline" sx={{ color: "var(--app-muted)", letterSpacing: "0.16em" }}>
                      Import preview
                    </Typography>
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      {importPreview.label} · {importPreview.providerCount}{" "}
                      {importPreview.providerCount === 1 ? "provider" : "providers"}
                    </Typography>
                    <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                      The import will stage a batch proposal against the current live chain instead of changing it directly.
                    </Typography>
                  </Box>
                ) : (
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    Paste JSON to see what kind of policy import it is before staging it.
                  </Typography>
                )}
              </CardContent>
            </Card>

            {importPreview && !(importPreview instanceof Error) ? (
              <Button
                type="button"
                variant="outlined"
                onClick={() => handleLoadIntoDraft()}
                disabled={importPreview.kind !== "single_provider"}
                sx={{ mt: 2, borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}
              >
                Load single rule into draft
              </Button>
            ) : null}
          </CardContent>
        </Card>
      </Box>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Card variant="outlined" sx={{ borderRadius: 4, borderColor: "var(--app-border)", bgcolor: "var(--app-surface)", boxShadow: "none" }}>
          <CardContent sx={{ p: 2.5 }}>
            <Box sx={{ display: "grid", gap: 0.5 }}>
              <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                Private packs
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                Save reusable policy starting points for your team
              </Typography>
              <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                Turn a draft, the live chain, or a saved version into a private pack that reviewers can stage again later.
              </Typography>
            </Box>

            <Box sx={{ mt: 2, display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <TextField label="Pack title" value={packTitle} onChange={(event) => setPackTitle(event.target.value)} placeholder="Production baseline" size="small" fullWidth />
              <FormControl size="small" fullWidth>
                <InputLabel id="pack-source-label">Source</InputLabel>
                <Select labelId="pack-source-label" label="Source" value={packSource} onChange={(event) => setPackSource(String(event.target.value))}>
                  <MenuItem value="editor">Current draft editor</MenuItem>
                  <MenuItem value="live">Live policy chain</MenuItem>
                  {versionNumbers.map((vn) => (
                    <MenuItem key={`pack-source-${vn}`} value={`version:${vn}`}>
                      Version {vn}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            <Box sx={{ mt: 1.5, display: "grid", gap: 1.5 }}>
              <TextField value={packSummary} onChange={(event) => setPackSummary(event.target.value)} placeholder="Short summary for reviewers" size="small" fullWidth />
              <TextField
                value={packDescription}
                onChange={(event) => setPackDescription(event.target.value)}
                placeholder="What this pack is for and when to use it"
                size="small"
                fullWidth
                multiline
                minRows={4}
              />
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                <TextField value={packTags} onChange={(event) => setPackTags(event.target.value)} placeholder="Tags: registry, strict, rollout" size="small" fullWidth />
                <TextField
                  value={packEnvironments}
                  onChange={(event) => setPackEnvironments(event.target.value)}
                  placeholder="Best for: development, staging"
                  size="small"
                  fullWidth
                />
              </Box>
            </Box>

            <Button type="button" variant="contained" onClick={() => void handleSavePack()} disabled={busyKey === "save-pack"} sx={{ mt: 2, borderRadius: 999 }}>
              {busyKey === "save-pack" ? "Saving…" : "Save private pack"}
            </Button>

            <Box sx={{ mt: 2.5, display: "grid", gap: 1.5 }}>
              {packs.length === 0 ? (
                <Card variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                  <CardContent sx={{ p: 2 }}>
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      No private packs saved yet. Save a draft or the live chain to build a reusable library for the team.
                    </Typography>
                  </CardContent>
                </Card>
              ) : (
                packs.map((pack) => (
                  <Card key={pack.pack_id} variant="outlined" sx={{ borderRadius: 3, borderColor: "var(--app-border)", bgcolor: "var(--app-control-bg)", boxShadow: "none" }}>
                    <CardContent sx={{ p: 2 }}>
                      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, justifyContent: "space-between", alignItems: "flex-start" }}>
                        <Box sx={{ display: "grid", gap: 0.5, minWidth: 240 }}>
                          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1 }}>
                            <Typography sx={{ fontSize: 12, fontWeight: 800, color: "var(--app-fg)" }}>
                              {pack.title ?? pack.pack_id}
                            </Typography>
                            <Chip
                              size="small"
                              label="private"
                              sx={{ borderRadius: 999, bgcolor: "var(--app-surface)", color: "var(--app-muted)", fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.12em" }}
                            />
                          </Box>
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            {pack.summary || pack.description || "Saved policy pack"}
                          </Typography>
                          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                            {pack.provider_count ?? 0} rules · revision {pack.current_revision_number ?? pack.revision_count ?? 1} · owner {pack.owner ?? "unknown"}
                          </Typography>
                        </Box>
                        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                          <Button type="button" variant="outlined" size="small" onClick={() => handleLoadPackIntoDraft(pack)} sx={{ borderRadius: 999, borderColor: "var(--app-border)", color: "var(--app-muted)" }}>
                            Load
                          </Button>
                          <Button
                            type="button"
                            variant="contained"
                            size="small"
                            onClick={() => void onStagePack(pack.pack_id, pack.title ?? pack.pack_id)}
                            disabled={busyKey === `pack-${pack.pack_id}`}
                            sx={{ borderRadius: 999 }}
                          >
                            {busyKey === `pack-${pack.pack_id}` ? "Staging…" : "Stage"}
                          </Button>
                          <Button
                            type="button"
                            variant="outlined"
                            size="small"
                            onClick={() => setDeletePackModal({ id: pack.pack_id, title: pack.title ?? pack.pack_id })}
                            disabled={busyKey === `pack-delete-${pack.pack_id}`}
                            sx={{
                              borderRadius: 999,
                              borderColor: "rgba(251, 113, 133, 0.55)",
                              color: "rgb(254, 205, 211)",
                              "&:hover": { bgcolor: "rgba(244, 63, 94, 0.12)", borderColor: "rgba(251, 113, 133, 0.55)" },
                            }}
                          >
                            Delete
                          </Button>
                        </Box>
                      </Box>
                      {(pack.provider_summaries ?? []).length > 0 ? (
                        <Box component="ul" sx={{ listStyle: "disc", pl: 2, mt: 1.5, mb: 0, color: "var(--app-muted)", fontSize: 11, display: "grid", gap: 0.5 }}>
                          {(pack.provider_summaries ?? []).slice(0, 3).map((summary, index) => (
                            <li key={`${pack.pack_id}-summary-${index}`}>{summary}</li>
                          ))}
                        </Box>
                      ) : null}
                    </CardContent>
                  </Card>
                ))
              )}
            </Box>
          </CardContent>
        </Card>
      </Box>

      <ConfirmModal
        isOpen={deletePackModal !== null}
        title={`Delete "${deletePackModal?.title}"?`}
        description="This will permanently remove the saved pack. This action cannot be undone."
        confirmLabel="Delete pack"
        isDangerous
        isLoading={deletePackModal !== null && busyKey === `pack-delete-${deletePackModal.id}`}
        onConfirm={async () => {
          if (!deletePackModal) return;
          await onDeletePack(deletePackModal.id);
          setDeletePackModal(null);
        }}
        onCancel={() => setDeletePackModal(null)}
      />
    </Box>
  );
}
