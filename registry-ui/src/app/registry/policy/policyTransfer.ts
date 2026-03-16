import type {
  PolicyConfig,
  PolicySchemaResponse,
  PolicySnapshot,
} from "@/lib/registryClient";

export type ImportedPolicyPreview = {
  kind: "snapshot" | "provider_list" | "single_provider";
  label: string;
  providerCount: number;
  snapshot: PolicySnapshot;
};

export function parseImportedPolicyJson(
  rawText: string,
): ImportedPolicyPreview | null {
  const trimmed = rawText.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = JSON.parse(trimmed) as unknown;
  if (Array.isArray(parsed)) {
    if (!parsed.every((item) => isPolicyConfig(item))) {
      throw new Error("Provider lists must contain only JSON objects.");
    }
    return {
      kind: "provider_list",
      label: "Provider list",
      providerCount: parsed.length,
      snapshot: {
        format: "securemcp-policy-set/v1",
        providers: parsed,
        metadata: { source: "policy_import" },
      },
    };
  }

  if (!isPolicyConfig(parsed)) {
    throw new Error("Imported policy must be a JSON object or provider list.");
  }

  const policyData = parsed.policy_data;
  if (isPolicyConfig(policyData) && Array.isArray(policyData.providers)) {
    return {
      kind: "snapshot",
      label: "Saved version payload",
      providerCount: countProviders(policyData.providers),
      snapshot: policyData as PolicySnapshot,
    };
  }

  if (Array.isArray(parsed.providers)) {
    return {
      kind: "snapshot",
      label: "Policy snapshot",
      providerCount: countProviders(parsed.providers),
      snapshot: {
        ...parsed,
        format: typeof parsed.format === "string" ? parsed.format : "securemcp-policy-set/v1",
      },
    };
  }

  if ("type" in parsed || "composition" in parsed) {
    return {
      kind: "single_provider",
      label: "Single policy rule",
      providerCount: 1,
      snapshot: {
        format: "securemcp-policy-set/v1",
        providers: [parsed],
        metadata: { source: "policy_import", shape: "single_provider" },
      },
    };
  }

  throw new Error(
    "Imported JSON must be a policy snapshot, a provider list, or a single policy config.",
  );
}

export function downloadJsonFile(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}

export function schemaTypeEntries(schema?: PolicySchemaResponse | null) {
  return Object.entries(schema?.policy_types ?? {});
}

export function schemaCompositionEntries(schema?: PolicySchemaResponse | null) {
  return Object.entries(schema?.compositions ?? {});
}

export function schemaCommonFields(schema?: PolicySchemaResponse | null) {
  return Object.entries(schema?.common_fields ?? {});
}

function countProviders(providers: unknown[]): number {
  return providers.filter((item) => isPolicyConfig(item)).length;
}

function isPolicyConfig(value: unknown): value is PolicyConfig {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
