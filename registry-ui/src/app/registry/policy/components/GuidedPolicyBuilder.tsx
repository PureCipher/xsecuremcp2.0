"use client";

import { useState } from "react";
import type {
  PolicyConfig,
  PolicySchemaResponse,
} from "@/lib/registryClient";
import {
  formatFieldInput,
  parseFieldInput,
  schemaCommonFieldSpecs,
  schemaCommonFields,
  schemaCompositionEntries,
  schemaTypeEntries,
  starterPolicyConfig,
} from "../policyTransfer";
import { usePolicyContext } from "../contexts/PolicyContext";
import { highlightJson, JsonEditor } from "./JsonEditor";

type GuidedPolicyBuilderProps = {
  schema: PolicySchemaResponse;
  onLoadDraft: (configText: string) => void;
};

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function GuidedPolicyBuilder({
  schema,
  onLoadDraft,
}: GuidedPolicyBuilderProps) {
  const { setBanner } = usePolicyContext();

  const policyTypeEntries = schemaTypeEntries(schema);
  const compositionEntries = schemaCompositionEntries(schema);
  const commonFieldEntries = schemaCommonFields(schema);
  const commonFieldSpecs = schemaCommonFieldSpecs(schema);

  const [guidedKind, setGuidedKind] = useState<"policy" | "composition">("policy");
  const [guidedSelection, setGuidedSelection] = useState<string>(
    policyTypeEntries[0]?.[0] ?? "allowlist",
  );
  const [guidedDraft, setGuidedDraft] = useState<PolicyConfig>(
    starterPolicyConfig(schema, policyTypeEntries[0]?.[0] ?? "allowlist", "policy"),
  );

  const guidedDefinition =
    guidedKind === "policy"
      ? schema?.policy_types?.[guidedSelection]
      : schema?.compositions?.[guidedSelection];
  const guidedFieldSpecs = Object.entries(guidedDefinition?.field_specs ?? {});

  function chooseGuidedTemplate(nextKind: "policy" | "composition", key: string) {
    setGuidedKind(nextKind);
    setGuidedSelection(key);
    setGuidedDraft(starterPolicyConfig(schema, key, nextKind));
  }

  function updateGuidedField(fieldName: string, rawValue: string) {
    const spec = guidedDefinition?.field_specs?.[fieldName];
    try {
      const parsed = parseFieldInput(spec, rawValue);
      setGuidedDraft((current) => ({ ...current, [fieldName]: parsed }));
      setBanner(null);
    } catch (error) {
      setBanner({
        tone: "error",
        message:
          error instanceof Error ? error.message : `Unable to update ${fieldName}.`,
      });
    }
  }

  function updateGuidedCommonField(fieldName: string, rawValue: string) {
    const spec = schema?.common_field_specs?.[fieldName];
    const parsed = parseFieldInput(spec, rawValue);
    setGuidedDraft((current) => ({ ...current, [fieldName]: parsed }));
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Schema guide */}
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Schema guide
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            See the supported JSON shape
          </h2>
          <p className="text-xs text-[--app-muted]">
            Use this guide when you hand-edit JSON, prepare imports, or want a
            quick reminder of the fields each policy type supports.
          </p>
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
            Common fields
          </p>
          <ul className="mt-2 space-y-1 text-xs text-[--app-muted]">
            {commonFieldEntries.map(([fieldName, description]) => (
              <li key={fieldName}>
                <span className="font-semibold text-[--app-fg]">{fieldName}</span>:{" "}
                {description}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-4 grid gap-3">
          {policyTypeEntries.map(([typeName, definition]) => (
            <div
              key={typeName}
              className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-semibold capitalize text-[--app-fg]">
                  {typeName.replaceAll("_", " ")}
                </p>
                {definition.aliases?.length ? (
                  <span className="text-[11px] text-[--app-muted]">
                    Aliases: {definition.aliases.join(", ")}
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-xs text-[--app-muted]">
                {definition.description}
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-[--app-muted]">
                {Object.entries(definition.fields ?? {}).map(
                  ([fieldName, description]) => (
                    <li key={`${typeName}-${fieldName}`}>
                      <span className="font-semibold text-[--app-fg]">
                        {fieldName}
                      </span>
                      : {description}
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
            Composition helpers
          </p>
          <ul className="mt-2 space-y-2 text-xs text-[--app-muted]">
            {compositionEntries.map(([name, definition]) => (
              <li key={name}>
                <span className="font-semibold text-[--app-fg]">
                  {name.replaceAll("_", " ")}
                </span>
                : {definition.description}
                {definition.extra_fields
                  ? ` Extra fields: ${Object.entries(definition.extra_fields)
                      .map(
                        ([fieldName, description]) =>
                          `${fieldName} (${description})`,
                      )
                      .join(", ")}`
                  : ""}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Guided builder */}
      <div className="rounded-3xl border border-[--app-border] bg-[--app-surface] p-5 ring-1 ring-[--app-surface-ring]">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-[--app-muted]">
            Guided builder
          </p>
          <h2 className="text-xl font-semibold text-[--app-fg]">
            Author a rule from the schema
          </h2>
          <p className="text-xs text-[--app-muted]">
            Pick a policy type, fill in guided fields, and only drop to raw
            JSON for nested or advanced cases.
          </p>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-[--app-muted]">
            Builder mode
            <select
              value={guidedKind}
              onChange={(event) =>
                chooseGuidedTemplate(
                  event.target.value as "policy" | "composition",
                  event.target.value === "policy"
                    ? (policyTypeEntries[0]?.[0] ?? "allowlist")
                    : (compositionEntries[0]?.[0] ?? "all_of"),
                )
              }
              className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
            >
              <option value="policy">Single policy</option>
              <option value="composition">Composition</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-[--app-muted]">
            Template
            <select
              value={guidedSelection}
              onChange={(event) =>
                chooseGuidedTemplate(guidedKind, event.target.value)
              }
              className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
            >
              {(guidedKind === "policy"
                ? policyTypeEntries
                : compositionEntries
              ).map(([key]) => (
                <option key={key} value={key}>
                  {key.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 grid gap-3">
          {commonFieldSpecs.map(([fieldName, spec]) => (
            <label
              key={`guided-common-${fieldName}`}
              className="flex flex-col gap-1 text-xs text-[--app-muted]"
            >
              {spec.label ?? fieldName}
              <input
                value={formatFieldInput(spec, guidedDraft[fieldName])}
                onChange={(event) =>
                  updateGuidedCommonField(fieldName, event.target.value)
                }
                placeholder={spec.placeholder}
                className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
              />
              <span className="text-[11px] text-[--app-muted]">
                {spec.description}
              </span>
            </label>
          ))}
        </div>

        <div className="mt-4 grid gap-3">
          {guidedFieldSpecs.map(([fieldName, spec]) => {
            const unsupported =
              spec.type === "policy_config" ||
              spec.type === "policy_config_list" ||
              spec.type === "policy_config_map";
            if (unsupported) {
              return (
                <div
                  key={`guided-field-${fieldName}`}
                  className="rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]"
                >
                  <p className="text-xs font-semibold text-[--app-fg]">
                    {spec.label ?? fieldName}
                  </p>
                  <p className="mt-2 text-xs text-[--app-muted]">
                    {spec.description}
                  </p>
                  <p className="mt-2 text-[11px] text-[--app-muted]">
                    Nested rules still use the JSON preview below. Start from
                    the starter config and refine the preview if you need
                    compositions or resource-specific children.
                  </p>
                </div>
              );
            }

            const currentValue = guidedDraft[fieldName];
            const inputValue = formatFieldInput(spec, currentValue);
            return (
              <label
                key={`guided-field-${fieldName}`}
                className="flex flex-col gap-1 text-xs text-[--app-muted]"
              >
                {spec.label ?? fieldName}
                {spec.type === "bool" ? (
                  <select
                    value={inputValue || String(Boolean(spec.default))}
                    onChange={(event) =>
                      updateGuidedField(fieldName, event.target.value)
                    }
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : spec.type === "enum" ? (
                  <select
                    value={inputValue || String(spec.default ?? "")}
                    onChange={(event) =>
                      updateGuidedField(fieldName, event.target.value)
                    }
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
                  >
                    {(spec.enum ?? []).map((option) => (
                      <option key={`${fieldName}-${option}`} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : spec.type === "json_map" ||
                  spec.type === "string_map_string_list" ? (
                  <JsonEditor
                    value={inputValue}
                    onChange={(newText) =>
                      updateGuidedField(fieldName, newText)
                    }
                    minHeight="120px"
                  />
                ) : (
                  <input
                    value={inputValue}
                    onChange={(event) =>
                      updateGuidedField(fieldName, event.target.value)
                    }
                    placeholder={spec.placeholder}
                    type={spec.type === "int" ? "number" : "text"}
                    className="rounded-2xl border border-[--app-border] bg-[--app-chrome-bg] px-4 py-2 text-xs text-[--app-fg] outline-none focus:border-[--app-accent]"
                  />
                )}
                <span className="text-[11px] text-[--app-muted]">
                  {spec.description}
                </span>
              </label>
            );
          })}
        </div>

        <div className="mt-4 rounded-2xl border border-[--app-border] bg-[--app-control-bg] p-4 ring-1 ring-[--app-surface-ring]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[--app-muted]">
              Guided JSON preview
            </p>
            <button
              type="button"
              onClick={() => {
                onLoadDraft(prettyJson(guidedDraft));
                setBanner({
                  tone: "success",
                  message: "Loaded the guided draft into the proposal editor.",
                });
              }}
              className="rounded-full border border-[--app-border] px-3 py-1 text-[11px] font-semibold text-[--app-muted] transition hover:bg-[--app-hover-bg] hover:text-[--app-fg]"
            >
              Load into proposal editor
            </button>
          </div>
          <pre
            className="mt-3 max-h-[280px] overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-6 text-[--app-fg]"
            dangerouslySetInnerHTML={{
              __html: highlightJson(prettyJson(guidedDraft)),
            }}
          />
        </div>
      </div>
    </div>
  );
}
