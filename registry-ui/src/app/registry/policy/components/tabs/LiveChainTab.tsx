"use client";

import { useState } from "react";
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
    <div className="flex flex-col gap-4">
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="flex flex-col gap-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Live policy chain
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            See what is active right now
          </h2>
          <p className="max-w-2xl text-xs text-[--app-muted]">
            These rules are live today. Draft a change or removal first, then approve
            and apply it from the Proposals tab.
          </p>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onExportLive()}
            disabled={busyKey === "export-live"}
            className="rounded-full border border-[--app-border] px-3 py-1 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:opacity-60"
          >
            {busyKey === "export-live" ? "Downloading\u2026" : "Export live JSON"}
          </button>
          <button
            type="button"
            onClick={() => downloadJsonFile("securemcp-policy-schema.json", schema)}
            className="rounded-full border border-[--app-border] px-3 py-1 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
          >
            Download schema
          </button>
        </div>

        <div className="mt-5 flex flex-col gap-4">
          {providers.length === 0 ? (
            <div className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
              <p className="text-xs text-[--app-muted]">
                No providers are active right now. Start by drafting the first rule
                from the Tools tab.
              </p>
            </div>
          ) : (
            providers.map((provider) => {
              const isEditing = editingIndex === provider.index;
              const editableText =
                editTexts[provider.index] ?? prettyJson(provider.config ?? {});

              return (
                <article
                  key={provider.index}
                  className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-[--app-surface] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
                          Step {provider.index + 1}
                        </span>
                        <span className="text-xs font-semibold text-[--app-fg]">
                          {provider.type}
                        </span>
                      </div>
                      <p className="text-xs text-[--app-muted]">{provider.summary}</p>
                      <p className="text-[11px] text-[--app-muted]">
                        Policy ID: {provider.policy_id ?? "n/a"} · Version:{" "}
                        {provider.policy_version ?? "n/a"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingIndex(isEditing ? null : provider.index);
                          setEditTexts((current) => ({
                            ...current,
                            [provider.index]: prettyJson(provider.config ?? {}),
                          }));
                        }}
                        disabled={!provider.editable}
                        className="rounded-full border border-[--app-border] px-3 py-1 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isEditing
                          ? "Close draft"
                          : provider.editable
                            ? "Draft change"
                            : "Read only"}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setRemovalModal({ index: provider.index, reason: "No longer needed." })
                        }
                        disabled={busyKey === `remove-${provider.index}`}
                        className="rounded-full border border-rose-500/80 px-3 py-1 text-[11px] font-semibold text-rose-100 transition hover:bg-rose-500/10 disabled:opacity-60"
                      >
                        {busyKey === `remove-${provider.index}` ? "Drafting\u2026" : "Draft removal"}
                      </button>
                    </div>
                  </div>

                  {isEditing ? (
                    <div className="mt-4 flex flex-col gap-3">
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
                      <input
                        value={editDescriptions[provider.index] ?? ""}
                        onChange={(event) =>
                          setEditDescriptions((current) => ({
                            ...current,
                            [provider.index]: event.target.value,
                          }))
                        }
                        placeholder="What should change and why?"
                        className="rounded-full border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
                      />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleDraftEdit(provider.index)}
                          disabled={busyKey === `draft-${provider.index}`}
                          className="rounded-full bg-[--app-accent] px-4 py-2 text-[11px] font-semibold text-[--app-accent-contrast] transition hover:opacity-90 disabled:opacity-60"
                        >
                          {busyKey === `draft-${provider.index}` ? "Saving draft\u2026" : "Create proposal"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })
          )}
        </div>
      </div>

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
        <textarea
          value={removalModal?.reason ?? ""}
          onChange={(event) =>
            setRemovalModal((prev) =>
              prev ? { ...prev, reason: event.target.value } : null,
            )
          }
          placeholder="Why should this rule be removed?"
          className="min-h-[80px] w-full rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-3 text-xs leading-6 text-[--app-fg] outline-none focus:border-[--app-accent]"
        />
      </ConfirmModal>
    </div>
  );
}
