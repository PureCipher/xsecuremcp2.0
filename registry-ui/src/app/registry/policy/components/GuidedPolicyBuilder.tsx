"use client";

import { useState } from "react";
import type { PolicyConfig, PolicySchemaResponse } from "@/lib/registryClient";
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
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

const fieldSx = {
  "& .MuiOutlinedInput-root": {
    borderRadius: 3,
    bgcolor: "var(--app-chrome-bg)",
    "& fieldset": { borderColor: "var(--app-border)" },
    "&:hover fieldset": { borderColor: "var(--app-border)" },
    "&.Mui-focused fieldset": { borderColor: "var(--app-accent)" },
  },
  "& .MuiInputBase-input": { fontSize: 12, color: "var(--app-fg)" },
} as const;

const panelSx = {
  borderRadius: 4,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-surface)",
  p: 2.5,
  boxShadow: "0 0 0 1px var(--app-surface-ring)",
} as const;

const insetPanelSx = {
  mt: 2,
  borderRadius: 3,
  border: "1px solid var(--app-border)",
  bgcolor: "var(--app-control-bg)",
  p: 2,
  boxShadow: "0 0 0 1px var(--app-surface-ring)",
} as const;

export function GuidedPolicyBuilder({ schema, onLoadDraft }: GuidedPolicyBuilderProps) {
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
        message: error instanceof Error ? error.message : `Unable to update ${fieldName}.`,
      });
    }
  }

  function updateGuidedCommonField(fieldName: string, rawValue: string) {
    const spec = schema?.common_field_specs?.[fieldName];
    const parsed = parseFieldInput(spec, rawValue);
    setGuidedDraft((current) => ({ ...current, [fieldName]: parsed }));
  }

  return (
    <Stack spacing={3}>
      <Box sx={panelSx}>
        <Stack spacing={0.5}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Schema guide
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            See the supported JSON shape
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            Use this guide when you hand-edit JSON, prepare imports, or want a quick reminder of the
            fields each policy type supports.
          </Typography>
        </Stack>

        <Box sx={insetPanelSx}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
              fontSize: 10,
            }}
          >
            Common fields
          </Typography>
          <Stack component="ul" spacing={0.5} sx={{ mt: 1, pl: 2, m: 0, color: "var(--app-muted)" }}>
            {commonFieldEntries.map(([fieldName, description]) => (
              <Typography key={fieldName} component="li" variant="caption">
                <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                  {fieldName}
                </Box>
                : {description}
              </Typography>
            ))}
          </Stack>
        </Box>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {policyTypeEntries.map(([typeName, definition]) => (
            <Box key={typeName} sx={insetPanelSx}>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", alignItems: "center" }}>
                <Typography variant="caption" sx={{ fontWeight: 600, textTransform: "capitalize", color: "var(--app-fg)" }}>
                  {typeName.replaceAll("_", " ")}
                </Typography>
                {definition.aliases?.length ? (
                  <Typography variant="caption" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                    Aliases: {definition.aliases.join(", ")}
                  </Typography>
                ) : null}
              </Stack>
              <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                {definition.description}
              </Typography>
              <Stack component="ul" spacing={0.5} sx={{ mt: 1, pl: 2, m: 0 }}>
                {Object.entries(definition.fields ?? {}).map(([fieldName, description]) => (
                  <Typography
                    key={`${typeName}-${fieldName}`}
                    component="li"
                    variant="caption"
                    sx={{ fontSize: 11, color: "var(--app-muted)" }}
                  >
                    <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                      {fieldName}
                    </Box>
                    : {description}
                  </Typography>
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>

        <Box sx={{ ...insetPanelSx, mt: 2 }}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
              fontSize: 10,
            }}
          >
            Composition helpers
          </Typography>
          <Stack component="ul" spacing={1} sx={{ mt: 1, pl: 2, m: 0 }}>
            {compositionEntries.map(([name, definition]) => (
              <Typography key={name} component="li" variant="caption" sx={{ color: "var(--app-muted)" }}>
                <Box component="span" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                  {name.replaceAll("_", " ")}
                </Box>
                : {definition.description}
                {definition.extra_fields
                  ? ` Extra fields: ${Object.entries(definition.extra_fields)
                      .map(([fieldName, description]) => `${fieldName} (${description})`)
                      .join(", ")}`
                  : ""}
              </Typography>
            ))}
          </Stack>
        </Box>
      </Box>

      <Box sx={panelSx}>
        <Stack spacing={0.5}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Guided builder
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
            Author a rule from the schema
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
            Pick a policy type, fill in guided fields, and only drop to raw JSON for nested or advanced
            cases.
          </Typography>
        </Stack>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 2 }}>
          <FormControl fullWidth size="small" sx={fieldSx}>
            <InputLabel id="guided-kind-label" sx={{ color: "var(--app-muted)", fontSize: 12 }}>
              Builder mode
            </InputLabel>
            <Select
              labelId="guided-kind-label"
              label="Builder mode"
              value={guidedKind}
              onChange={(event) =>
                chooseGuidedTemplate(
                  event.target.value as "policy" | "composition",
                  event.target.value === "policy"
                    ? (policyTypeEntries[0]?.[0] ?? "allowlist")
                    : (compositionEntries[0]?.[0] ?? "all_of"),
                )
              }
            >
              <MenuItem value="policy">Single policy</MenuItem>
              <MenuItem value="composition">Composition</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth size="small" sx={fieldSx}>
            <InputLabel id="guided-template-label" sx={{ color: "var(--app-muted)", fontSize: 12 }}>
              Template
            </InputLabel>
            <Select
              labelId="guided-template-label"
              label="Template"
              value={guidedSelection}
              onChange={(event) => chooseGuidedTemplate(guidedKind, event.target.value)}
            >
              {(guidedKind === "policy" ? policyTypeEntries : compositionEntries).map(([key]) => (
                <MenuItem key={key} value={key}>
                  {key.replaceAll("_", " ")}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {commonFieldSpecs.map(([fieldName, spec]) => (
            <Stack key={`guided-common-${fieldName}`} spacing={0.5}>
              <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                {spec.label ?? fieldName}
              </Typography>
              <TextField
                size="small"
                value={formatFieldInput(spec, guidedDraft[fieldName])}
                onChange={(event) => updateGuidedCommonField(fieldName, event.target.value)}
                placeholder={spec.placeholder}
                sx={fieldSx}
              />
              <Typography variant="caption" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                {spec.description}
              </Typography>
            </Stack>
          ))}
        </Stack>

        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {guidedFieldSpecs.map(([fieldName, spec]) => {
            const unsupported =
              spec.type === "policy_config" ||
              spec.type === "policy_config_list" ||
              spec.type === "policy_config_map";
            if (unsupported) {
              return (
                <Box key={`guided-field-${fieldName}`} sx={insetPanelSx}>
                  <Typography variant="caption" sx={{ fontWeight: 600, color: "var(--app-fg)" }}>
                    {spec.label ?? fieldName}
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: "block", color: "var(--app-muted)" }}>
                    {spec.description}
                  </Typography>
                  <Typography variant="caption" sx={{ mt: 1, display: "block", fontSize: 11, color: "var(--app-muted)" }}>
                    Nested rules still use the JSON preview below. Start from the starter config and refine
                    the preview if you need compositions or resource-specific children.
                  </Typography>
                </Box>
              );
            }

            const currentValue = guidedDraft[fieldName];
            const inputValue = formatFieldInput(spec, currentValue);
            return (
              <Stack key={`guided-field-${fieldName}`} spacing={0.5}>
                <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                  {spec.label ?? fieldName}
                </Typography>
                {spec.type === "bool" ? (
                  <FormControl fullWidth size="small" sx={fieldSx}>
                    <Select
                      value={inputValue || String(Boolean(spec.default))}
                      onChange={(event) => updateGuidedField(fieldName, event.target.value)}
                    >
                      <MenuItem value="true">True</MenuItem>
                      <MenuItem value="false">False</MenuItem>
                    </Select>
                  </FormControl>
                ) : spec.type === "enum" ? (
                  <FormControl fullWidth size="small" sx={fieldSx}>
                    <Select
                      value={inputValue || String(spec.default ?? "")}
                      onChange={(event) => updateGuidedField(fieldName, event.target.value)}
                    >
                      {(spec.enum ?? []).map((option) => (
                        <MenuItem key={`${fieldName}-${option}`} value={option}>
                          {option}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : spec.type === "json_map" || spec.type === "string_map_string_list" ? (
                  <JsonEditor
                    value={inputValue}
                    onChange={(newText) => updateGuidedField(fieldName, newText)}
                    minHeight="120px"
                  />
                ) : (
                  <TextField
                    size="small"
                    value={inputValue}
                    onChange={(event) => updateGuidedField(fieldName, event.target.value)}
                    placeholder={spec.placeholder}
                    type={spec.type === "int" ? "number" : "text"}
                    sx={fieldSx}
                  />
                )}
                <Typography variant="caption" sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                  {spec.description}
                </Typography>
              </Stack>
            );
          })}
        </Stack>

        <Box sx={{ ...insetPanelSx, mt: 2 }}>
          <Stack
            direction="row"
            spacing={1}
            sx={{ flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}
          >
            <Typography
              variant="caption"
              sx={{
                fontWeight: 700,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
                fontSize: 10,
              }}
            >
              Guided JSON preview
            </Typography>
            <Button
              type="button"
              variant="outlined"
              size="small"
              onClick={() => {
                onLoadDraft(prettyJson(guidedDraft));
                setBanner({
                  tone: "success",
                  message: "Loaded the guided draft into the proposal editor.",
                });
              }}
              sx={{
                borderRadius: 999,
                textTransform: "none",
                fontSize: 11,
                fontWeight: 700,
                borderColor: "var(--app-border)",
                color: "var(--app-muted)",
                "&:hover": { borderColor: "var(--app-border)", bgcolor: "var(--app-hover-bg)", color: "var(--app-fg)" },
              }}
            >
              Load into proposal editor
            </Button>
          </Stack>
          <Box
            component="pre"
            sx={{
              mt: 1.5,
              maxHeight: 280,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 12,
              lineHeight: 1.8,
              color: "var(--app-fg)",
              m: 0,
            }}
            dangerouslySetInnerHTML={{ __html: highlightJson(prettyJson(guidedDraft)) }}
          />
        </Box>
      </Box>
    </Stack>
  );
}
