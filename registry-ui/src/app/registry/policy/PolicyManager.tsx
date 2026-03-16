"use client";

import { useMemo, useState } from "react";
import type {
  PolicyConfig,
  PolicyGovernanceSummary,
  PolicyManagementResponse,
  PolicyProviderItem,
  PolicyVersionDiffResponse,
  PolicyVersionItem,
} from "@/lib/registryClient";

type PolicyTemplateName =
  | "allowlist"
  | "denylist"
  | "rbac"
  | "rate_limit"
  | "time_based";

type PolicyState = {
  provider_count?: number;
  providers?: PolicyProviderItem[];
  governance?: PolicyGovernanceSummary | null;
};

type PolicyVersionsState = {
  current_version?: number | null;
  versions?: PolicyVersionItem[];
};

type PolicyManagerData = Pick<PolicyManagementResponse, "policy" | "versions">;

const POLICY_TEMPLATES: Record<PolicyTemplateName, PolicyConfig> = {
  allowlist: {
    type: "allowlist",
    policy_id: "allowlist-policy",
    version: "1.0.0",
    allowed: ["tool:*"],
  },
  denylist: {
    type: "denylist",
    policy_id: "denylist-policy",
    version: "1.0.0",
    denied: ["tool:admin-*"],
  },
  rbac: {
    type: "rbac",
    policy_id: "rbac-policy",
    version: "1.0.0",
    role_mappings: {
      admin: ["*"],
      reviewer: ["call_tool", "read_resource"],
    },
    default_decision: "deny",
  },
  rate_limit: {
    type: "rate_limit",
    policy_id: "rate-limit-policy",
    version: "1.0.0",
    max_requests: 200,
    window_seconds: 3600,
  },
  time_based: {
    type: "time_based",
    policy_id: "business-hours-policy",
    version: "1.0.0",
    allowed_days: [0, 1, 2, 3, 4],
    start_hour: 9,
    end_hour: 17,
    utc_offset_hours: 0,
  },
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Unknown time";
  }

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function PolicyManager({ initialData }: { initialData: PolicyManagerData }) {
  const policy: PolicyState = initialData?.policy ?? {};
  const versionsState: PolicyVersionsState = initialData?.versions ?? {};
  const versions = versionsState.versions ?? [];
  const providers = policy.providers ?? [];
  const currentVersion = versionsState.current_version ?? null;
  const governance = policy.governance ?? null;
  const sortedVersions = versions.slice().sort((left, right) => right.version_number - left.version_number);
  const versionNumbers = sortedVersions.map((version) => version.version_number);

  const [banner, setBanner] = useState<{ tone: "success" | "error"; message: string } | null>(
    null,
  );
  const [creating, setCreating] = useState(false);
  const [createReason, setCreateReason] = useState("");
  const [createTemplate, setCreateTemplate] = useState<PolicyTemplateName>("allowlist");
  const [createConfigText, setCreateConfigText] = useState(
    prettyJson(POLICY_TEMPLATES.allowlist),
  );
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editTexts, setEditTexts] = useState<Record<number, string>>({});
  const [editReasons, setEditReasons] = useState<Record<number, string>>({});
  const [rollbackReason, setRollbackReason] = useState("");
  const [diffFrom, setDiffFrom] = useState<number | "">(
    versionNumbers[1] ?? versionNumbers[0] ?? "",
  );
  const [diffTo, setDiffTo] = useState<number | "">(versionNumbers[0] ?? "");
  const [diffLoading, setDiffLoading] = useState(false);
  const [versionDiff, setVersionDiff] = useState<PolicyVersionDiffResponse | null>(null);

  const stats = useMemo(
    () => [
      {
        label: "Live providers",
        value: String(policy.provider_count ?? providers.length ?? 0),
      },
      {
        label: "Current version",
        value: currentVersion ? `v${currentVersion}` : "Not versioned",
      },
      {
        label: "Pending proposals",
        value:
          governance?.enabled && typeof governance.pending_count === "number"
            ? String(governance.pending_count)
            : "0",
      },
    ],
    [currentVersion, governance?.enabled, governance?.pending_count, policy.provider_count, providers.length],
  );

  function chooseTemplate(name: PolicyTemplateName) {
    setCreateTemplate(name);
    setCreateConfigText(prettyJson(POLICY_TEMPLATES[name]));
  }

  async function handleCreate() {
    setBanner(null);
    setCreating(true);
    try {
      const config = JSON.parse(createConfigText) as PolicyConfig;
      const response = await fetch("/api/policy/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          reason: createReason,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Unable to add policy provider.");
      }
      setBanner({ tone: "success", message: "Policy provider added." });
      window.location.reload();
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to add policy provider.",
      });
    } finally {
      setCreating(false);
    }
  }

  async function handleSave(index: number) {
    setBanner(null);
    setBusyKey(`save-${index}`);
    try {
      const rawText = editTexts[index] ?? prettyJson(providers[index]?.config ?? {});
      const config = JSON.parse(rawText) as PolicyConfig;
      const response = await fetch(`/api/policy/providers/${index}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          config,
          reason: editReasons[index] ?? "",
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Unable to update policy provider.");
      }
      setBanner({ tone: "success", message: "Policy provider updated." });
      window.location.reload();
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to update policy provider.",
      });
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDelete(index: number) {
    const confirmed = window.confirm("Remove this provider from the live policy chain?");
    if (!confirmed) {
      return;
    }

    setBanner(null);
    setBusyKey(`delete-${index}`);
    try {
      const response = await fetch(`/api/policy/providers/${index}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: editReasons[index] ?? "",
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Unable to remove policy provider.");
      }
      setBanner({ tone: "success", message: "Policy provider removed." });
      window.location.reload();
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to remove policy provider.",
      });
    } finally {
      setBusyKey(null);
    }
  }

  async function handleRollback(versionNumber: number) {
    const confirmed = window.confirm(`Roll back the live policy chain to version ${versionNumber}?`);
    if (!confirmed) {
      return;
    }

    setBanner(null);
    setBusyKey(`rollback-${versionNumber}`);
    try {
      const response = await fetch("/api/policy/rollback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version_number: versionNumber,
          reason: rollbackReason,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Unable to roll back policy version.");
      }
      setBanner({ tone: "success", message: `Rolled back to version ${versionNumber}.` });
      window.location.reload();
    } catch (error) {
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to roll back policy version.",
      });
    } finally {
      setBusyKey(null);
    }
  }

  async function handleLoadDiff() {
    if (diffFrom === "" || diffTo === "") {
      setBanner({
        tone: "error",
        message: "Pick two saved versions before comparing them.",
      });
      return;
    }

    setBanner(null);
    setDiffLoading(true);
    try {
      const response = await fetch(`/api/policy/diff?v1=${diffFrom}&v2=${diffTo}`, {
        cache: "no-store",
      });
      const payload = (await response.json().catch(() => ({}))) as PolicyVersionDiffResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "Unable to compare policy versions.");
      }
      setVersionDiff(payload);
    } catch (error) {
      setVersionDiff(null);
      setBanner({
        tone: "error",
        message: error instanceof Error ? error.message : "Unable to compare policy versions.",
      });
    } finally {
      setDiffLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {banner ? (
        <section
          className={`rounded-3xl p-4 ring-1 ${
            banner.tone === "success"
              ? "bg-emerald-900/40 text-emerald-50 ring-emerald-600/60"
              : "bg-rose-950/40 text-rose-50 ring-rose-700/60"
          }`}
        >
          <p className="text-[12px] font-medium">{banner.message}</p>
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        {stats.map((item) => (
          <div
            key={item.label}
            className="rounded-3xl bg-emerald-900/40 p-4 ring-1 ring-emerald-700/60"
          >
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
              {item.label}
            </p>
            <p className="mt-2 text-2xl font-semibold text-emerald-50">{item.value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.3fr,0.9fr]">
        <div className="flex flex-col gap-4">
          <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <div className="flex flex-col gap-1">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
                Live policy chain
              </p>
              <h2 className="text-xl font-semibold text-emerald-50">
                Edit the rules that gate live access
              </h2>
              <p className="max-w-2xl text-[11px] text-emerald-100/80">
                Each provider runs in order. Update the JSON for a provider, save the change,
                and the registry will capture a new version automatically.
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-4">
              {providers.length === 0 ? (
                <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
                  <p className="text-[12px] text-emerald-100/90">
                    No providers are active right now. Add one from the policy starter panel.
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
                      className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-emerald-900/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                              Step {provider.index + 1}
                            </span>
                            <span className="text-[12px] font-semibold text-emerald-50">
                              {provider.type}
                            </span>
                          </div>
                          <p className="text-[11px] text-emerald-100/90">{provider.summary}</p>
                          <p className="text-[10px] text-emerald-300/90">
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
                            className="rounded-full border border-emerald-600/80 px-3 py-1 text-[10px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {isEditing ? "Close editor" : provider.editable ? "Edit rule" : "Read only"}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDelete(provider.index)}
                            disabled={busyKey === `delete-${provider.index}`}
                            className="rounded-full border border-rose-500/80 px-3 py-1 text-[10px] font-semibold text-rose-100 transition hover:bg-rose-500/10 disabled:opacity-60"
                          >
                            {busyKey === `delete-${provider.index}` ? "Removing…" : "Remove"}
                          </button>
                        </div>
                      </div>

                      {isEditing ? (
                        <div className="mt-4 flex flex-col gap-3">
                          <textarea
                            value={editableText}
                            onChange={(event) =>
                              setEditTexts((current) => ({
                                ...current,
                                [provider.index]: event.target.value,
                              }))
                            }
                            className="min-h-[220px] rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-3 font-mono text-[11px] leading-6 text-emerald-50 outline-none focus:border-emerald-400"
                          />
                          <input
                            value={editReasons[provider.index] ?? ""}
                            onChange={(event) =>
                              setEditReasons((current) => ({
                                ...current,
                                [provider.index]: event.target.value,
                              }))
                            }
                            placeholder="Why are you changing this rule?"
                            className="rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-[11px] text-emerald-50 outline-none focus:border-emerald-400"
                          />
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => void handleSave(provider.index)}
                              disabled={busyKey === `save-${provider.index}`}
                              className="rounded-full bg-emerald-500 px-4 py-2 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
                            >
                              {busyKey === `save-${provider.index}` ? "Saving…" : "Save live change"}
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

          <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <div className="space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
                Version history
              </p>
              <h2 className="text-xl font-semibold text-emerald-50">Roll back with confidence</h2>
              <p className="max-w-2xl text-[11px] text-emerald-100/80">
                Every change creates a saved version of the active policy chain. Roll back when
                a change needs to be reversed quickly.
              </p>
            </div>

            <input
              value={rollbackReason}
              onChange={(event) => setRollbackReason(event.target.value)}
              placeholder="Optional rollback reason"
              className="mt-4 w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-[11px] text-emerald-50 outline-none focus:border-emerald-400"
            />

            <div className="mt-4 flex flex-col gap-3">
              {versions.length === 0 ? (
                <div className="rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
                  <p className="text-[12px] text-emerald-100/90">
                    No saved versions yet. The first policy change will create one automatically.
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
                            <span className="text-[12px] font-semibold text-emerald-50">
                              Version {version.version_number}
                            </span>
                            {isCurrent ? (
                              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-100">
                                Live now
                              </span>
                            ) : null}
                          </div>
                          <p className="text-[11px] text-emerald-100/90">
                            {version.description || "No description recorded."}
                          </p>
                          <p className="text-[10px] text-emerald-300/90">
                            Saved by {version.author || "unknown"} · {formatTimestamp(version.created_at)}
                          </p>
                        </div>
                        {!isCurrent ? (
                          <button
                            type="button"
                            onClick={() => void handleRollback(version.version_number)}
                            disabled={busyKey === `rollback-${version.version_number}`}
                            className="rounded-full border border-emerald-600/80 px-3 py-1 text-[10px] font-semibold text-emerald-100 transition hover:bg-emerald-700/30 disabled:opacity-60"
                          >
                            {busyKey === `rollback-${version.version_number}`
                              ? "Rolling back…"
                              : "Roll back"}
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </div>

          <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <div className="space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
                Version diff
              </p>
              <h2 className="text-xl font-semibold text-emerald-50">See what changed</h2>
              <p className="max-w-2xl text-[11px] text-emerald-100/80">
                Compare two saved versions before you roll back or move forward with another edit.
              </p>
            </div>

            {versionNumbers.length < 2 ? (
              <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
                <p className="text-[12px] text-emerald-100/90">
                  You need at least two saved versions before comparison is useful.
                </p>
              </div>
            ) : (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                  <label className="flex flex-col gap-1 text-[11px] text-emerald-100/90">
                    From version
                    <select
                      value={diffFrom}
                      onChange={(event) => setDiffFrom(Number(event.target.value))}
                      className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-[11px] text-emerald-50 outline-none focus:border-emerald-400"
                    >
                      {versionNumbers.map((versionNumber) => (
                        <option key={`from-${versionNumber}`} value={versionNumber}>
                          Version {versionNumber}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1 text-[11px] text-emerald-100/90">
                    To version
                    <select
                      value={diffTo}
                      onChange={(event) => setDiffTo(Number(event.target.value))}
                      className="rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-[11px] text-emerald-50 outline-none focus:border-emerald-400"
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
                    className="self-end rounded-full bg-emerald-500 px-4 py-2 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
                  >
                    {diffLoading ? "Comparing…" : "Compare versions"}
                  </button>
                </div>

                <div className="mt-4 rounded-2xl bg-emerald-950/70 p-4 ring-1 ring-emerald-700/70">
                  {versionDiff?.diff ? (
                    <pre className="max-h-[320px] overflow-auto whitespace-pre-wrap break-words text-[11px] leading-6 text-emerald-50">
                      {prettyJson(versionDiff.diff)}
                    </pre>
                  ) : (
                    <p className="text-[12px] text-emerald-100/90">
                      Choose two versions to inspect the saved diff before you act on it.
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <aside className="flex flex-col gap-4">
          <div className="rounded-3xl bg-emerald-900/40 p-5 ring-1 ring-emerald-700/60">
            <div className="space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300">
                Add a policy
              </p>
              <h2 className="text-xl font-semibold text-emerald-50">
                Start from a policy template
              </h2>
              <p className="text-[11px] text-emerald-100/80">
                Pick a starter, adjust the JSON, and add it to the live evaluation chain.
              </p>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {(Object.keys(POLICY_TEMPLATES) as PolicyTemplateName[]).map((templateName) => (
                <button
                  key={templateName}
                  type="button"
                  onClick={() => chooseTemplate(templateName)}
                  className={`rounded-2xl px-3 py-3 text-left text-[11px] ring-1 transition ${
                    createTemplate === templateName
                      ? "bg-emerald-500/15 text-emerald-50 ring-emerald-400/70"
                      : "bg-emerald-950/70 text-emerald-100 ring-emerald-700/70 hover:bg-emerald-900/60"
                  }`}
                >
                  <span className="block font-semibold capitalize">
                    {templateName.replaceAll("_", " ")}
                  </span>
                  <span className="mt-1 block text-[10px] text-emerald-200/80">
                    {templateName === "allowlist"
                      ? "Allow only named tools"
                      : templateName === "denylist"
                        ? "Block named tools"
                        : templateName === "rbac"
                          ? "Map roles to actions"
                          : templateName === "rate_limit"
                            ? "Control request volume"
                            : "Restrict by time window"}
                  </span>
                </button>
              ))}
            </div>

            <textarea
              value={createConfigText}
              onChange={(event) => setCreateConfigText(event.target.value)}
              className="mt-4 min-h-[280px] w-full rounded-2xl border border-emerald-700/70 bg-emerald-950 px-4 py-3 font-mono text-[11px] leading-6 text-emerald-50 outline-none focus:border-emerald-400"
            />

            <input
              value={createReason}
              onChange={(event) => setCreateReason(event.target.value)}
              placeholder="Why are you adding this rule?"
              className="mt-3 w-full rounded-full border border-emerald-700/70 bg-emerald-950 px-4 py-2 text-[11px] text-emerald-50 outline-none focus:border-emerald-400"
            />

            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={creating}
              className="mt-4 rounded-full bg-emerald-500 px-4 py-2 text-[11px] font-semibold text-emerald-950 transition hover:bg-emerald-400 disabled:opacity-60"
            >
              {creating ? "Adding policy…" : "Add to live chain"}
            </button>
          </div>
        </aside>
      </section>
    </div>
  );
}
