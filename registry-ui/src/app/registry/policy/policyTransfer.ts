import type {
  PolicyConfig,
  PolicySchemaFieldSpec,
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

export function schemaCommonFieldSpecs(schema?: PolicySchemaResponse | null) {
  return Object.entries(schema?.common_field_specs ?? {});
}

export function starterPolicyConfig(
  schema: PolicySchemaResponse | null | undefined,
  key: string,
  kind: "policy" | "composition",
): PolicyConfig {
  const definition =
    kind === "policy"
      ? schema?.policy_types?.[key]
      : schema?.compositions?.[key];
  const starter = definition?.starter_config;
  if (starter && isPolicyConfig(starter)) {
    return structuredClone(starter);
  }

  if (kind === "policy") {
    return { type: key, version: "1.0.0" };
  }
  return { composition: key, version: "1.0.0", policies: [] };
}

export function parseFieldInput(
  spec: PolicySchemaFieldSpec | undefined,
  rawValue: string,
): unknown {
  const type = spec?.type ?? "string";
  if (type === "int") {
    const parsed = Number.parseInt(rawValue, 10);
    return Number.isFinite(parsed) ? parsed : spec?.default ?? 0;
  }
  if (type === "bool") {
    return rawValue === "true";
  }
  if (type === "string_list") {
    return rawValue
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (type === "int_list") {
    return rawValue
      .split(/[\n,]/)
      .map((item) => Number.parseInt(item.trim(), 10))
      .filter((item) => Number.isFinite(item));
  }
  if (type === "string_map_string_list") {
    return rawValue
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .reduce<Record<string, string[]>>((result, line) => {
        const [key, rest] = line.split(":");
        if (!key || !rest) {
          return result;
        }
        result[key.trim()] = rest
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean);
        return result;
      }, {});
  }
  if (type === "json_map") {
    return JSON.parse(rawValue || "{}") as Record<string, unknown>;
  }
  return rawValue;
}

export function formatFieldInput(
  spec: PolicySchemaFieldSpec | undefined,
  value: unknown,
): string {
  const type = spec?.type ?? "string";
  if (type === "string_list" && Array.isArray(value)) {
    return value.join(", ");
  }
  if (type === "int_list" && Array.isArray(value)) {
    return value.join(", ");
  }
  if (type === "string_map_string_list" && isPolicyConfig(value)) {
    return Object.entries(value)
      .map(([key, actions]) =>
        `${key}: ${Array.isArray(actions) ? actions.join(", ") : ""}`,
      )
      .join("\n");
  }
  if (type === "json_map" && isPolicyConfig(value)) {
    return JSON.stringify(value, null, 2);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  return "";
}

function countProviders(providers: unknown[]): number {
  return providers.filter((item) => isPolicyConfig(item)).length;
}

function isPolicyConfig(value: unknown): value is PolicyConfig {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
