"use client";

import { useState } from "react";
import type {
  PolicyVersionDiffResponse,
} from "@/lib/registryClient";
import { usePolicyContext } from "../../contexts/PolicyContext";
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
    <div className="flex flex-col gap-4">
      {/* Version history */}
      <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
            Version history
          </p>
          <h2 className="text-xl font-semibold text-emerald-50">
            Roll back with confidence
          </h2>
          <p className="max-w-2xl text-xs text-emerald-100/80">
            Every live apply creates a saved version of the policy chain. Roll back when
            a change needs to be reversed quickly.
          </p>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          {versions.length === 0 ? (
            <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
              <p className="text-xs text-emerald-100/90">
                No saved versions yet. The first live policy change will create one
                automatically.
              </p>
            </div>
          ) : (
            sortedVersions.map((version) => {
              const isCurrent = version.version_number === currentVersion;
              return (
                <article
                  key={version.version_id}
                  className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-semibold text-emerald-50">
                          Version {version.version_number}
                        </span>
                        {isCurrent ? (
                          <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
                            Live now
                          </span>
                        ) : null}
                      </div>
                      <p className="text-xs text-emerald-100/90">
                        {version.description || "No description recorded."}
                      </p>
                      <p className="text-[11px] text-emerald-300/90">
                        Saved by {version.author || "unknown"} ·{" "}
                        {formatTimestamp(version.created_at)}
                      </p>
                    </div>
                    {!isCurrent ? (
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void onExportVersion(version.version_number)}
                          disabled={busyKey === `export-${version.version_number}`}
                          className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                        >
                          {busyKey === `export-${version.version_number}`
                            ? "Downloading\u2026"
                            : "Export JSON"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setRollbackReason("");
                            setRollbackModal(version.version_number);
                          }}
                          disabled={busyKey === `rollback-${version.version_number}`}
                          className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                        >
                          {busyKey === `rollback-${version.version_number}`
                            ? "Rolling back\u2026"
                            : "Roll back"}
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void onExportVersion(version.version_number)}
                        disabled={busyKey === `export-${version.version_number}`}
                        className="rounded-full border border-emerald-600/80 px-3 py-1 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                      >
                        {busyKey === `export-${version.version_number}`
                          ? "Downloading\u2026"
                          : "Export JSON"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })
          )}
        </div>
      </div>

      {/* Version diff */}
      <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
            Version diff
          </p>
          <h2 className="text-xl font-semibold text-emerald-50">See what changed</h2>
          <p className="max-w-2xl text-xs text-emerald-100/80">
            Compare two saved versions before you roll back or stage another change.
          </p>
        </div>

        {versionNumbers.length < 2 ? (
          <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
            <p className="text-xs text-emerald-100/90">
              You need at least two saved versions before comparison is useful.
            </p>
          </div>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
              <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
                From version
                <select
                  value={diffFrom}
                  onChange={(event) => setDiffFrom(Number(event.target.value))}
                  className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
                >
                  {versionNumbers.map((versionNumber) => (
                    <option key={`from-${versionNumber}`} value={versionNumber}>
                      Version {versionNumber}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs text-emerald-100/90">
                To version
                <select
                  value={diffTo}
                  onChange={(event) => setDiffTo(Number(event.target.value))}
                  className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
                >
                  {versionNumbers.map((versionNumber) => (
                    <option key={`to-${versionNumber}`} value={versionNumber}>
                      Version {versionNumber}
                    </option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                onClick={() => void handleLoadDiff()}
                disabled={diffLoading}
                className="self-end rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
              >
                {diffLoading ? "Comparing\u2026" : "Compare versions"}
              </button>
            </div>

            <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
              {versionDiff?.diff ? (
                <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-emerald-50">
                  {prettyJson(versionDiff.diff)}
                </pre>
              ) : (
                <p className="text-xs text-emerald-100/90">
                  Choose two versions to inspect the saved diff before you act on it.
                </p>
              )}
            </div>
          </>
        )}
      </div>

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
        <input
          value={rollbackReason}
          onChange={(event) => setRollbackReason(event.target.value)}
          placeholder="Why are you rolling back?"
          className="w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-xs text-emerald-50 outline-none focus:border-emerald-400"
        />
      </ConfirmModal>
    </div>
  );
}
