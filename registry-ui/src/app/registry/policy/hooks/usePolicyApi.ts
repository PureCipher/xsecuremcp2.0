"use client";

import { useCallback } from "react";
import type {
  PolicyConfig,
  PolicyExportResponse,
  PolicyImportResponse,
  PolicyMigrationPreviewResponse,
  PolicyProposalItem,
  PolicySimulationScenario,
  PolicyVersionDiffResponse,
} from "@/lib/registryClient";
import { downloadJsonFile } from "../policyTransfer";

type ApiDeps = {
  setBanner: (b: { tone: "success" | "error"; message: string } | null) => void;
  setBusyKey: (k: string | null) => void;
  refresh: () => void;
};

async function apiCall<T = Record<string, unknown>>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  const payload = (await response.json().catch(() => ({}))) as T & {
    error?: string;
  };
  if (!response.ok) {
    throw new Error(
      (payload as { error?: string }).error ?? `Request failed (${response.status})`,
    );
  }
  return payload;
}

export function usePolicyApi({ setBanner, setBusyKey, refresh }: ApiDeps) {
  const run = useCallback(
    async (
      key: string,
      fn: () => Promise<string | void>,
    ) => {
      setBanner(null);
      setBusyKey(key);
      try {
        const message = await fn();
        if (message) {
          setBanner({ tone: "success", message });
        }
        refresh();
      } catch (error) {
        setBanner({
          tone: "error",
          message:
            error instanceof Error ? error.message : "An unexpected error occurred.",
        });
      } finally {
        setBusyKey(null);
      }
    },
    [setBanner, setBusyKey, refresh],
  );

  // ── Proposal actions ──────────────────────────────────────────────

  const createProposal = useCallback(
    (payload: {
      action: "add" | "swap" | "remove" | "replace_chain";
      config?: PolicyConfig;
      targetIndex?: number;
      description: string;
    }) =>
      run("create-proposal", async () => {
        await apiCall("/api/policy/proposals", {
          method: "POST",
          body: JSON.stringify({
            action: payload.action,
            config: payload.config,
            target_index: payload.targetIndex,
            description: payload.description,
          }),
        });
        return "Proposal created. Review it before it goes live.";
      }),
    [run],
  );

  const simulateProposal = useCallback(
    (proposalId: string, scenarios: PolicySimulationScenario[]) =>
      run(`simulate-${proposalId}`, async () => {
        await apiCall(`/api/policy/proposals/${proposalId}/simulate`, {
          method: "POST",
          body: JSON.stringify({ scenarios }),
        });
        return "Simulation complete. Review the impact before applying.";
      }),
    [run],
  );

  const approveAndDeploy = useCallback(
    (
      proposal: PolicyProposalItem,
      note: string,
      requireApproval: boolean,
      requireSimulation: boolean,
    ) =>
      run(`approve-${proposal.proposal_id}`, async () => {
        if (proposal.status !== "approved") {
          if (requireSimulation && proposal.status !== "simulated") {
            throw new Error(
              "Run the proposal simulation before approving this change.",
            );
          }
          if (requireApproval) {
            await apiCall(
              `/api/policy/proposals/${proposal.proposal_id}/approve`,
              {
                method: "POST",
                body: JSON.stringify({ note }),
              },
            );
          }
        }
        await apiCall(
          `/api/policy/proposals/${proposal.proposal_id}/deploy`,
          {
            method: "POST",
            body: JSON.stringify({ note }),
          },
        );
        return "Proposal applied to the live policy chain.";
      }),
    [run],
  );

  const rejectProposal = useCallback(
    (proposalId: string, reason: string) =>
      run(`reject-${proposalId}`, async () => {
        await apiCall(`/api/policy/proposals/${proposalId}/reject`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
        return "Proposal rejected.";
      }),
    [run],
  );

  const withdrawProposal = useCallback(
    (proposalId: string, note: string) =>
      run(`withdraw-${proposalId}`, async () => {
        await apiCall(`/api/policy/proposals/${proposalId}/withdraw`, {
          method: "POST",
          body: JSON.stringify({ note }),
        });
        return "Proposal withdrawn.";
      }),
    [run],
  );

  const assignProposal = useCallback(
    (proposalId: string, reviewer: string, note: string) =>
      run(`assign-${proposalId}`, async () => {
        if (!reviewer.trim()) {
          throw new Error("Choose a reviewer username before assigning ownership.");
        }
        await apiCall(`/api/policy/proposals/${proposalId}/assign`, {
          method: "POST",
          body: JSON.stringify({ reviewer, note }),
        });
        return `Proposal assigned to ${reviewer}.`;
      }),
    [run],
  );

  // ── Version actions ───────────────────────────────────────────────

  const rollbackVersion = useCallback(
    (versionNumber: number, reason: string) =>
      run(`rollback-${versionNumber}`, async () => {
        await apiCall("/api/policy/rollback", {
          method: "POST",
          body: JSON.stringify({ version_number: versionNumber, reason }),
        });
        return `Rolled back to version ${versionNumber}.`;
      }),
    [run],
  );

  const loadDiff = useCallback(
    async (v1: number, v2: number): Promise<PolicyVersionDiffResponse | null> => {
      setBanner(null);
      setBusyKey("load-diff");
      try {
        const payload = await apiCall<PolicyVersionDiffResponse>(
          `/api/policy/diff?v1=${v1}&v2=${v2}`,
          { cache: "no-store" },
        );
        return payload;
      } catch (error) {
        setBanner({
          tone: "error",
          message:
            error instanceof Error
              ? error.message
              : "Unable to compare policy versions.",
        });
        return null;
      } finally {
        setBusyKey(null);
      }
    },
    [setBanner, setBusyKey],
  );

  const exportPolicy = useCallback(
    (versionNumber?: number) => {
      const busyId =
        versionNumber === undefined ? "export-live" : `export-${versionNumber}`;
      return run(busyId, async () => {
        const query =
          versionNumber === undefined
            ? ""
            : `?version=${encodeURIComponent(String(versionNumber))}`;
        const payload = await apiCall<PolicyExportResponse>(
          `/api/policy/export${query}`,
          { cache: "no-store" },
        );
        if (!payload.snapshot) {
          throw new Error("Unable to export policy JSON.");
        }
        downloadJsonFile(
          payload.suggested_filename ?? "securemcp-policy.json",
          payload.snapshot,
        );
        return versionNumber === undefined
          ? "Live policy JSON downloaded."
          : `Version ${versionNumber} JSON downloaded.`;
      });
    },
    [run],
  );

  // ── Bundle & pack actions ─────────────────────────────────────────

  const stageBundle = useCallback(
    (bundleId: string, title: string) =>
      run(`bundle-${bundleId}`, async () => {
        const payload = await apiCall<PolicyImportResponse>(
          `/api/policy/bundles/${bundleId}/stage`,
          {
            method: "POST",
            body: JSON.stringify({ description: `Apply bundle: ${title}` }),
          },
        );
        return payload.status === "no_changes"
          ? "That bundle already matches the live chain."
          : `${title} is now staged as a proposal.`;
      }),
    [run],
  );

  const savePack = useCallback(
    (body: Record<string, unknown>) =>
      run("save-pack", async () => {
        await apiCall("/api/policy/packs", {
          method: "POST",
          body: JSON.stringify(body),
        });
        return "Private pack saved. It is now available to your policy team.";
      }),
    [run],
  );

  const deletePack = useCallback(
    (packId: string) =>
      run(`pack-delete-${packId}`, async () => {
        await apiCall(`/api/policy/packs/${packId}`, { method: "DELETE" });
        return "Saved pack deleted.";
      }),
    [run],
  );

  const stagePack = useCallback(
    (packId: string, title: string) =>
      run(`pack-${packId}`, async () => {
        const payload = await apiCall<PolicyImportResponse>(
          `/api/policy/packs/${packId}/stage`,
          {
            method: "POST",
            body: JSON.stringify({ description: `Apply saved pack: ${title}` }),
          },
        );
        return payload.status === "no_changes"
          ? "That saved pack already matches the live chain."
          : `${title} is now staged as a proposal.`;
      }),
    [run],
  );

  // ── Import/export ─────────────────────────────────────────────────

  const importPolicy = useCallback(
    (snapshot: unknown, descriptionPrefix: string) =>
      run("import-policy", async () => {
        const payload = await apiCall<PolicyImportResponse>(
          "/api/policy/import",
          {
            method: "POST",
            body: JSON.stringify({
              snapshot,
              description_prefix: descriptionPrefix,
            }),
          },
        );
        if (payload.status === "no_changes") {
          return "Imported JSON already matches the live policy chain. No proposals were created.";
        }
        const created = payload.summary?.created ?? 0;
        return created === 1
          ? "Imported JSON created 1 batch proposal."
          : `Imported JSON created ${created} proposals.`;
      }),
    [run],
  );

  // ── Migration actions ─────────────────────────────────────────────

  const captureEnvironment = useCallback(
    (environmentId: string, sourceVersionNumber: number | null, note: string) =>
      run(`capture-${environmentId}`, async () => {
        await apiCall(
          `/api/policy/environments/${environmentId}/capture`,
          {
            method: "POST",
            body: JSON.stringify({
              source_version_number: sourceVersionNumber,
              note,
            }),
          },
        );
        return `${environmentId} now has an updated policy baseline.`;
      }),
    [run],
  );

  const stagePromotion = useCallback(
    (source: string, target: string, description: string) =>
      run("stage-promotion", async () => {
        const payload = await apiCall<PolicyImportResponse>(
          "/api/policy/promotions",
          {
            method: "POST",
            body: JSON.stringify({
              source_environment: source,
              target_environment: target,
              description:
                description || `Promote ${source} policy into ${target}.`,
            }),
          },
        );
        return payload.status === "no_changes"
          ? "Those environments already line up. No promotion proposal was created."
          : `${source} is now staged for ${target}.`;
      }),
    [run],
  );

  const previewMigration = useCallback(
    async (
      sourceVersion: number | null,
      targetVersion: number | null,
      targetEnvironment: string,
    ): Promise<PolicyMigrationPreviewResponse | null> => {
      setBanner(null);
      setBusyKey("migration-preview");
      try {
        const payload = await apiCall<PolicyMigrationPreviewResponse>(
          "/api/policy/migrations/preview",
          {
            method: "POST",
            body: JSON.stringify({
              source_version_number: sourceVersion,
              target_version_number: targetVersion,
              target_environment: targetEnvironment,
            }),
          },
        );
        return payload;
      } catch (error) {
        setBanner({
          tone: "error",
          message:
            error instanceof Error
              ? error.message
              : "Unable to preview policy migration.",
        });
        return null;
      } finally {
        setBusyKey(null);
      }
    },
    [setBanner, setBusyKey],
  );

  return {
    // proposals
    createProposal,
    simulateProposal,
    approveAndDeploy,
    rejectProposal,
    withdrawProposal,
    assignProposal,
    // versions
    rollbackVersion,
    loadDiff,
    exportPolicy,
    // bundles & packs
    stageBundle,
    savePack,
    deletePack,
    stagePack,
    // import/export
    importPolicy,
    // migration
    captureEnvironment,
    stagePromotion,
    previewMigration,
  };
}
