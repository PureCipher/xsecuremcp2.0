"use client";

import { useState, useMemo, useEffect, type ChangeEvent } from "react";
import type {
  PolicyConfig,
  PolicyPlugin,
  PolicySchemaResponse,
} from "@/lib/registryClient";
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

  // Plugin-driven templates
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
    return () => { cancelled = true; };
  }, []);

  // Proposal editor state
  const [createTemplate, setCreateTemplate] = useState<string>("allowlist");
  const [createConfigText, setCreateConfigText] = useState("{}");
  const [createDescription, setCreateDescription] = useState("");
  const [creating, setCreating] = useState(false);

  // Import/export state
  const [importText, setImportText] = useState("");
  const [importDescriptionPrefix, setImportDescriptionPrefix] = useState(
    "Imported policy snapshot",
  );

  // Pack state
  const [packSource, setPackSource] = useState<string>("editor");
  const [packTitle, setPackTitle] = useState("");
  const [packSummary, setPackSummary] = useState("");
  const [packDescription, setPackDescription] = useState("");
  const [packTags, setPackTags] = useState("");
  const [packEnvironments, setPackEnvironments] = useState("");

  // Delete pack modal
  const [deletePackModal, setDeletePackModal] = useState<{ id: string; title: string } | null>(null);

  // Build template choices from plugins (preferred) or schema (fallback)
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

  // Unique jurisdictions for the filter dropdown
  const jurisdictions = useMemo(() => {
    const set = new Set<string>();
    for (const choice of templateChoices) {
      if (choice.jurisdiction) set.add(choice.jurisdiction);
    }
    return Array.from(set).sort();
  }, [templateChoices]);

  // Filtered template choices
  const filteredTemplates = useMemo(() => {
    if (pluginFilter === "all") return templateChoices;
    if (pluginFilter === "universal") return templateChoices.filter((c) => !c.jurisdiction);
    return templateChoices.filter((c) => c.jurisdiction === pluginFilter);
  }, [templateChoices, pluginFilter]);

  // Initialize the config text from the first template once loaded
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
        message:
          error instanceof Error
            ? error.message
            : "Unable to create policy proposal.",
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
    <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
      {/* Left column: Guided builder + Proposal editor + Import/Export */}
      <div className="flex flex-col gap-4">
        <GuidedPolicyBuilder
          schema={schema}
          onLoadDraft={(configText) => {
            setCreateConfigText(configText);
          }}
        />

        {/* Proposal editor */}
        <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
              Proposal editor
            </p>
            <h2 className="text-xl font-semibold text-emerald-50">
              Refine or hand-edit the JSON
            </h2>
            <p className="text-xs text-emerald-100/80">
              Use the guided builder above or start from a quick template, then
              create a proposal that reviewers can approve before it goes live.
            </p>
          </div>

          {jurisdictions.length > 0 ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-emerald-200/90">Filter:</span>
              <button
                type="button"
                onClick={() => setPluginFilter("all")}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  pluginFilter === "all"
                    ? "bg-emerald-500 text-emerald-950"
                    : "border border-emerald-700/70 text-emerald-100 hover:bg-emerald-700/20"
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setPluginFilter("universal")}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  pluginFilter === "universal"
                    ? "bg-emerald-500 text-emerald-950"
                    : "border border-emerald-700/70 text-emerald-100 hover:bg-emerald-700/20"
                }`}
              >
                Universal
              </button>
              {jurisdictions.map((j) => (
                <button
                  key={j}
                  type="button"
                  onClick={() => setPluginFilter(j)}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                    pluginFilter === j
                      ? "bg-emerald-500 text-emerald-950"
                      : "border border-emerald-700/70 text-emerald-100 hover:bg-emerald-700/20"
                  }`}
                >
                  {j}
                </button>
              ))}
            </div>
          ) : null}

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {filteredTemplates.map((template) => (
              <button
                key={template.key}
                type="button"
                onClick={() => chooseTemplate(template.key)}
                className={`rounded-2xl px-3 py-3 text-left text-xs ring-1 transition ${
                  createTemplate === template.key
                    ? "bg-emerald-500/15 text-emerald-50 ring-emerald-400/70"
                    : "bg-emerald-950/70 text-emerald-100 ring-emerald-700/70 hover:bg-emerald-900/60"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="block font-semibold capitalize">
                    {template.title}
                  </span>
                  {template.jurisdiction ? (
                    <span className="rounded-full bg-emerald-900/70 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-emerald-300">
                      {template.jurisdiction}
                    </span>
                  ) : null}
                  {template.version ? (
                    <span className="rounded-full bg-emerald-800/60 px-1.5 py-0.5 text-[9px] font-medium tracking-wide text-emerald-400/90">
                      v{template.version}
                    </span>
                  ) : null}
                </div>
                <span className="mt-1 block text-[11px] leading-snug text-emerald-200/80">
                  {template.summary.length > 80
                    ? `${template.summary.slice(0, 80)}…`
                    : template.summary}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-4">
            <JsonEditor
              value={createConfigText}
              onChange={setCreateConfigText}
              minHeight="280px"
            />
          </div>

          <input
            value={createDescription}
            onChange={(event) => setCreateDescription(event.target.value)}
            placeholder="What change should this proposal make?"
            className="mt-3 w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
          />

          <button
            type="button"
            onClick={() => void handleCreateProposal()}
            disabled={creating || busyKey === "create-proposal"}
            className="mt-4 rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
          >
            {creating || busyKey === "create-proposal"
              ? "Creating proposal\u2026"
              : "Create proposal"}
          </button>
        </div>

        {/* Import and export */}
        <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
              Import and export
            </p>
            <h2 className="text-xl font-semibold text-emerald-50">
              Move policy JSON in and out safely
            </h2>
            <p className="text-xs text-emerald-100/80">
              Export the live chain or a saved version, then import a snapshot,
              provider list, or single rule. Imports become batch proposals that
              still go through validation, simulation, approval, and deploy.
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleImportPolicy()}
              disabled={busyKey === "import-policy"}
              className="rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {busyKey === "import-policy"
                ? "Importing\u2026"
                : "Stage import as proposals"}
            </button>
            <label className="cursor-pointer rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30">
              Load JSON file
              <input
                type="file"
                accept="application/json,.json"
                onChange={(event) => void handleImportFile(event)}
                className="sr-only"
              />
            </label>
          </div>

          <div className="mt-4">
            <JsonEditor
              value={importText}
              onChange={setImportText}
              minHeight="220px"
              placeholder="Paste a policy snapshot, provider list, or single policy rule JSON."
            />
          </div>

          <input
            value={importDescriptionPrefix}
            onChange={(event) => setImportDescriptionPrefix(event.target.value)}
            placeholder="Imported policy snapshot"
            className="mt-3 w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
          />

          <div className="mt-3 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
            {importPreview instanceof Error ? (
              <p className="text-xs text-rose-100">{importPreview.message}</p>
            ) : importPreview ? (
              <div className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                  Import preview
                </p>
                <p className="text-xs text-emerald-100/90">
                  {importPreview.label} · {importPreview.providerCount}{" "}
                  {importPreview.providerCount === 1 ? "provider" : "providers"}
                </p>
                <p className="text-[11px] text-emerald-300/90">
                  The import will stage a batch proposal against the current live
                  chain instead of changing it directly.
                </p>
              </div>
            ) : (
              <p className="text-xs text-emerald-100/90">
                Paste JSON to see what kind of policy import it is before staging
                it.
              </p>
            )}
          </div>

          {importPreview && !(importPreview instanceof Error) ? (
            <button
              type="button"
              onClick={() => handleLoadIntoDraft()}
              disabled={importPreview.kind !== "single_provider"}
              className="mt-4 rounded-full border border-emerald-600/80 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
            >
              Load single rule into draft
            </button>
          ) : null}
        </div>
      </div>

      {/* Right column: Private packs */}
      <div className="flex flex-col gap-4">
        <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
              Private packs
            </p>
            <h2 className="text-xl font-semibold text-emerald-50">
              Save reusable policy starting points for your team
            </h2>
            <p className="text-xs text-emerald-100/80">
              Turn a draft, the live chain, or a saved version into a private
              pack that reviewers can stage again later.
            </p>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
              Pack title
              <input
                value={packTitle}
                onChange={(event) => setPackTitle(event.target.value)}
                placeholder="Production baseline"
                className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
              Source
              <select
                value={packSource}
                onChange={(event) => setPackSource(event.target.value)}
                className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              >
                <option value="editor">Current draft editor</option>
                <option value="live">Live policy chain</option>
                {versionNumbers.map((vn) => (
                  <option key={`pack-source-${vn}`} value={`version:${vn}`}>
                    Version {vn}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-3 grid gap-3">
            <input
              value={packSummary}
              onChange={(event) => setPackSummary(event.target.value)}
              placeholder="Short summary for reviewers"
              className="w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
            />
            <textarea
              value={packDescription}
              onChange={(event) => setPackDescription(event.target.value)}
              placeholder="What this pack is for and when to use it"
              className="min-h-[100px] rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-3 text-xs leading-6 text-emerald-50 outline-none focus:border-emerald-400"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={packTags}
                onChange={(event) => setPackTags(event.target.value)}
                placeholder="Tags: registry, strict, rollout"
                className="rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              />
              <input
                value={packEnvironments}
                onChange={(event) => setPackEnvironments(event.target.value)}
                placeholder="Best for: development, staging"
                className="rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={() => void handleSavePack()}
            disabled={busyKey === "save-pack"}
            className="mt-4 rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
          >
            {busyKey === "save-pack" ? "Saving\u2026" : "Save private pack"}
          </button>

          <div className="mt-5 space-y-3">
            {packs.length === 0 ? (
              <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
                <p className="text-xs text-emerald-100/90">
                  No private packs saved yet. Save a draft or the live chain to
                  build a reusable library for the team.
                </p>
              </div>
            ) : (
              packs.map((pack) => (
                <article
                  key={pack.pack_id}
                  className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold text-emerald-50">
                          {pack.title ?? pack.pack_id}
                        </p>
                        <span className="rounded-full bg-emerald-900/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                          private
                        </span>
                      </div>
                      <p className="text-xs text-emerald-100/90">
                        {pack.summary || pack.description || "Saved policy pack"}
                      </p>
                      <p className="text-[11px] text-emerald-300/90">
                        {pack.provider_count ?? 0} rules · revision{" "}
                        {pack.current_revision_number ?? pack.revision_count ?? 1} ·
                        owner {pack.owner ?? "unknown"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleLoadPackIntoDraft(pack)}
                        className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30"
                      >
                        Load
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          void onStagePack(pack.pack_id, pack.title ?? pack.pack_id)
                        }
                        disabled={busyKey === `pack-${pack.pack_id}`}
                        className="rounded-full bg-emerald-500 px-3 py-1 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
                      >
                        {busyKey === `pack-${pack.pack_id}` ? "Staging\u2026" : "Stage"}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setDeletePackModal({
                            id: pack.pack_id,
                            title: pack.title ?? pack.pack_id,
                          })
                        }
                        disabled={busyKey === `pack-delete-${pack.pack_id}`}
                        className="rounded-full border border-rose-500/70 px-3 py-1 text-[11px] font-semibold text-rose-100 transition hover:bg-rose-500/10 disabled:opacity-60"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {(pack.provider_summaries ?? []).length > 0 ? (
                    <ul className="mt-3 space-y-1 text-[11px] text-emerald-200/90">
                      {(pack.provider_summaries ?? []).slice(0, 3).map((summary, index) => (
                        <li key={`${pack.pack_id}-summary-${index}`}>\u2022 {summary}</li>
                      ))}
                    </ul>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Delete pack confirmation modal */}
      <ConfirmModal
        isOpen={deletePackModal !== null}
        title={`Delete "${deletePackModal?.title}"?`}
        description="This will permanently remove the saved pack. This action cannot be undone."
        confirmLabel="Delete pack"
        isDangerous
        isLoading={
          deletePackModal !== null &&
          busyKey === `pack-delete-${deletePackModal.id}`
        }
        onConfirm={async () => {
          if (!deletePackModal) return;
          await onDeletePack(deletePackModal.id);
          setDeletePackModal(null);
        }}
        onCancel={() => setDeletePackModal(null)}
      />
    </div>
  );
}
