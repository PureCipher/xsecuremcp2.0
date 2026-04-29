"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";

type OpenAPIOperation = {
  operation_key: string;
  method?: string;
  path?: string;
  operation_id?: string;
  summary?: string;
  description?: string;
  tags?: string[];
};

type PreflightFinding = {
  severity?: string;
  message?: string;
  summary?: string;
};

type PublisherPreflightResponse = {
  error?: string;
  ready_for_publish?: boolean;
  summary?: string;
  effective_certification_level?: string;
  minimum_required_level?: string;
  report?: {
    findings?: PreflightFinding[];
  };
};

type PublishRequestBody = {
  display_name: string;
  categories: string[];
  manifest: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

const STEPS = ["OpenAPI source", "Select operations", "Generate toolset", "Preflight", "Publish"] as const;

const DEFAULT_MANIFEST =
  "{\n  \"tool_name\": \"\",\n  \"version\": \"1.0.0\",\n  \"author\": \"\",\n  \"description\": \"\",\n  \"permissions\": [],\n  \"data_flows\": [],\n  \"resource_access\": [],\n  \"tags\": []\n}";

const TOOL_CATEGORIES = [
  "communication",
  "collaboration",
  "social_media",
  "project_management",
  "productivity",
  "crm",
  "marketing",
  "ecommerce",
  "human_resources",
  "payments",
  "finance",
  "blockchain",
  "database",
  "analytics",
  "data_platforms",
  "machine_learning",
  "developer_tools",
  "code_execution",
  "version_control",
  "devops",
  "cloud_platforms",
  "monitoring",
  "security",
  "authentication",
  "content_management",
  "media",
  "design",
  "search",
  "knowledge_management",
  "research",
  "file_system",
  "cloud_storage",
  "healthcare",
  "legal",
  "education",
  "network",
  "home_automation",
  "location_services",
  "travel",
  "data_access",
  "ai_ml",
  "utility",
  "other",
] as const;

function looksLikeUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function uniqStrings(values: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const v of values) {
    const s = v.trim();
    if (!s) continue;
    const key = s.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(s);
  }
  return out;
}

function slugifyToolName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function deriveServersFromOpenapiText(openapiText: string): string[] {
  try {
    const parsed = JSON.parse(openapiText);
    const servers = (parsed as any)?.servers;
    if (!Array.isArray(servers)) return [];
    const urls = servers.map((s: any) => String(s?.url ?? "")).filter((u: string) => looksLikeUrl(u));
    return uniqStrings(urls);
  } catch {
    return [];
  }
}

function tryParseJson(text: string, label: string): { ok: true; value: any } | { ok: false; message: string } {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: {} };
  try {
    return { ok: true, value: JSON.parse(trimmed) };
  } catch {
    return { ok: false, message: `${label} is not valid JSON yet.` };
  }
}

export function OpenApiPublishWizard() {
  const router = useRouter();
  const [activeStep, setActiveStep] = useState(0);

  const [displayName, setDisplayName] = useState("");
  const [categories, setCategories] = useState<string[]>(["network", "utility"]);
  const [hostingVisibility, setHostingVisibility] = useState<"public" | "protected" | "private">("protected");
  const [allowedUsersText, setAllowedUsersText] = useState("");

  const [openapiUrl, setOpenapiUrl] = useState("");
  const [openapiText, setOpenapiText] = useState("");
  const [openapiLoading, setOpenapiLoading] = useState(false);
  const [openapiSourceId, setOpenapiSourceId] = useState<string | null>(null);
  const [openapiOps, setOpenapiOps] = useState<OpenAPIOperation[]>([]);
  const [openapiSelected, setOpenapiSelected] = useState<Record<string, boolean>>({});
  const [openapiToolsetId, setOpenapiToolsetId] = useState<string | null>(null);
  const [hostedMcpEndpoint, setHostedMcpEndpoint] = useState<string | null>(null);

  const [manifestText, setManifestText] = useState(DEFAULT_MANIFEST);
  const [runtimeText, setRuntimeText] = useState("{}");
  const [preflight, setPreflight] = useState<PublisherPreflightResponse | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedKeys = useMemo(
    () => Object.entries(openapiSelected).filter(([, v]) => v).map(([k]) => k),
    [openapiSelected],
  );

  const selectedOps = useMemo(
    () => openapiOps.filter((op) => selectedKeys.includes(op.operation_key)),
    [openapiOps, selectedKeys],
  );

  const resetDownstream = useCallback(() => {
    setPreflight(null);
    setSuccess(null);
    setOpenapiToolsetId(null);
    setHostedMcpEndpoint(null);
  }, []);

  async function fetchAndIngestOpenAPI() {
    setError(null);
    setSuccess(null);
    resetDownstream();
    setOpenapiOps([]);
    setOpenapiSelected({});
    setOpenapiSourceId(null);

    const url = openapiUrl.trim();
    if (!url) {
      setError("Paste an OpenAPI URL first.");
      return;
    }
    if (!looksLikeUrl(url)) {
      setError("OpenAPI URL must be http(s).");
      return;
    }

    setOpenapiLoading(true);
    try {
      const fetchRes = await fetch(`/api/openapi/fetch?url=${encodeURIComponent(url)}`);
      const fetchPayload = (await fetchRes.json()) as { ok?: boolean; text?: string; error?: string };
      if (!fetchRes.ok || fetchPayload.error || !fetchPayload.text) {
        setError(fetchPayload.error ?? "Unable to fetch OpenAPI.");
        return;
      }
      setOpenapiText(fetchPayload.text);

      const ingestRes = await fetch("/api/openapi/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: displayName.trim() || "OpenAPI source",
          source_url: url,
          text: fetchPayload.text,
        }),
      });
      const ingestPayload = (await ingestRes.json()) as {
        error?: string;
        source?: { source_id?: string };
        operations?: OpenAPIOperation[];
      };
      if (!ingestRes.ok || ingestPayload.error) {
        setError(ingestPayload.error ?? "Unable to ingest OpenAPI.");
        return;
      }

      const sourceId = String(ingestPayload.source?.source_id ?? "").trim();
      if (!sourceId) {
        setError("OpenAPI ingest did not return a source id.");
        return;
      }
      setOpenapiSourceId(sourceId);

      const ops = Array.isArray(ingestPayload.operations) ? ingestPayload.operations : [];
      setOpenapiOps(ops);
      setSuccess(`Ingested OpenAPI. Parsed ${ops.length} operations.`);
      if (ops.length) setActiveStep(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "OpenAPI fetch failed.");
    } finally {
      setOpenapiLoading(false);
    }
  }

  async function createToolset() {
    setError(null);
    setSuccess(null);
    setPreflight(null);
    setOpenapiToolsetId(null);
    setHostedMcpEndpoint(null);

    if (!openapiSourceId) {
      setError("Fetch + ingest OpenAPI first.");
      return;
    }
    if (selectedKeys.length === 0) {
      setError("Select at least one operation.");
      return;
    }

    setOpenapiLoading(true);
    try {
      const res = await fetch("/api/openapi/toolset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_id: openapiSourceId,
          selected_operations: selectedKeys,
          title: displayName.trim() || "OpenAPI toolset",
          metadata: {
            upstream_base_url: deriveServersFromOpenapiText(openapiText)[0] ?? "",
            hosting_visibility: hostingVisibility,
            allowed_users:
              hostingVisibility === "private"
                ? allowedUsersText
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean)
                : [],
          },
        }),
      });
      const payload = (await res.json()) as {
        error?: string;
        toolset?: { toolset_id?: string };
      };
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Unable to create toolset.");
        return;
      }

      const toolsetId = String(payload.toolset?.toolset_id ?? "").trim();
      if (!toolsetId) {
        setError("Toolset response missing toolset_id.");
        return;
      }
      setOpenapiToolsetId(toolsetId);
      const endpoint = `/mcp/toolsets/${encodeURIComponent(toolsetId)}`;
      setHostedMcpEndpoint(endpoint);

      // Generate runtime + manifest defaults
      const runtime = {
        server_type: "securemcp",
        transport: "streamable-http",
        endpoint,
        hosted: true,
        toolset_id: toolsetId,
        upstream_base_url: deriveServersFromOpenapiText(openapiText)[0] ?? "",
        hosting_visibility: hostingVisibility,
        allowed_users:
          hostingVisibility === "private"
            ? allowedUsersText
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean)
            : [],
      };
      setRuntimeText(JSON.stringify(runtime, null, 2));

      const manifestObj: any = {
        ...(() => {
          const parsed = tryParseJson(DEFAULT_MANIFEST, "Manifest");
          return parsed.ok && parsed.value && typeof parsed.value === "object" ? parsed.value : {};
        })(),
      };
      manifestObj.tool_name = manifestObj.tool_name || slugifyToolName(displayName) || "openapi-toolset";
      manifestObj.author = manifestObj.author || "publisher";
      manifestObj.description =
        manifestObj.description ||
        (selectedOps.map((op) => String(op.summary ?? "").trim()).filter(Boolean)[0] ?? "OpenAPI-backed toolset");
      const opTags = selectedOps.flatMap((op) => (Array.isArray(op.tags) ? op.tags.map(String) : []));
      manifestObj.tags = uniqStrings([...(Array.isArray(manifestObj.tags) ? manifestObj.tags.map(String) : []), ...opTags]);
      manifestObj.permissions = uniqStrings([
        ...(Array.isArray(manifestObj.permissions) ? manifestObj.permissions.map(String) : []),
        "network_access",
      ]);
      const servers = deriveServersFromOpenapiText(openapiText);
      if (servers.length) {
        manifestObj.resource_access = uniqStrings(servers.slice(0, 3)).map((url) => ({
          resource_pattern: url.replace(/\/+$/g, "") + "/*",
          access_type: "read",
          description: "OpenAPI server base URL",
          classification: "public",
        }));
      }
      setManifestText(JSON.stringify(manifestObj, null, 2));

      setSuccess("Toolset created. Manifest + runtime metadata generated.");
      setActiveStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create toolset.");
    } finally {
      setOpenapiLoading(false);
    }
  }

  const parseCommonBody = useCallback((): PublishRequestBody => {
    const display = displayName.trim();
    if (!display) {
      throw new Error("Display name is required.");
    }
    const cats = categories.filter(Boolean);

    const manifestParsed = tryParseJson(manifestText, "Manifest");
    if (!manifestParsed.ok) throw new Error(manifestParsed.message);
    if (!manifestParsed.value || typeof manifestParsed.value !== "object") throw new Error("Manifest must be a JSON object.");

    const runtimeParsed = tryParseJson(runtimeText, "Runtime metadata");
    if (!runtimeParsed.ok) throw new Error(runtimeParsed.message);
    if (!runtimeParsed.value || typeof runtimeParsed.value !== "object") throw new Error("Runtime metadata must be a JSON object.");

    return {
      display_name: display,
      categories: cats,
      manifest: manifestParsed.value as Record<string, unknown>,
      metadata: runtimeParsed.value as Record<string, unknown>,
    };
  }, [categories, displayName, manifestText, runtimeText]);

  async function runPreflight() {
    setError(null);
    setSuccess(null);
    setPreflight(null);
    setSubmitting(true);
    try {
      const body = parseCommonBody();
      const res = await fetch("/api/publish/preflight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await res.json()) as PublisherPreflightResponse;
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Preflight failed.");
        setPreflight(payload);
        return;
      }
      setPreflight(payload);
      setSuccess(payload.summary ?? "Preflight completed.");
      setActiveStep(4);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preflight failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function submitPublish() {
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const body = parseCommonBody();
      const res = await fetch("/api/publish/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await res.json()) as { error?: string; ok?: boolean; listing_id?: string; tool_name?: string };
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Publish failed.");
        return;
      }
      router.push("/registry/publish/mine");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const readyForToolset = Boolean(openapiSourceId) && selectedKeys.length > 0;
  const readyForPreflight = Boolean(openapiToolsetId);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 2.5 }}>
        <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
          OpenAPI hosted publish flow
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.5, color: "var(--app-muted)", maxWidth: 860 }}>
          This wizard creates a hosted toolset from OpenAPI, then publishes a registry listing that points at the hosted
          SecureMCP endpoint.
        </Typography>

        <Stepper activeStep={activeStep} sx={{ mt: 2.5, mb: 1 }}>
          {STEPS.map((label) => (
            <Step key={label}>
              <StepLabel
                sx={{
                  "& .MuiStepLabel-label": { fontSize: 12, color: "var(--app-muted)" },
                  "& .MuiStepLabel-label.Mui-active": { color: "var(--app-fg)", fontWeight: 700 },
                  "& .MuiStepLabel-label.Mui-completed": { color: "var(--app-muted)" },
                }}
              >
                {label}
              </StepLabel>
            </Step>
          ))}
        </Stepper>

        {error ? (
          <Alert severity="error" sx={{ mt: 1 }}>
            {error}
          </Alert>
        ) : null}
        {success ? (
          <Alert severity="success" sx={{ mt: 1 }}>
            {success}
          </Alert>
        ) : null}

        {activeStep === 0 ? (
          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            <TextField
              label="Listing display name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g., Acme Payments (Hosted)"
              size="small"
              fullWidth
            />
            <Box>
              <Typography sx={{ fontSize: 12, fontWeight: 700, color: "var(--app-muted)", mb: 0.75 }}>
                Categories
              </Typography>
              {categories.length > 0 ? (
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 1 }}>
                  {categories.map((cat) => (
                    <Chip
                      key={cat}
                      label={cat}
                      size="small"
                      onDelete={() => setCategories((prev) => prev.filter((c) => c !== cat))}
                      sx={{
                        bgcolor: "var(--app-control-active-bg)",
                        color: "var(--app-fg)",
                        fontWeight: 600,
                        "& .MuiChip-deleteIcon": { color: "var(--app-muted)", "&:hover": { color: "var(--app-fg)" } },
                      }}
                    />
                  ))}
                </Box>
              ) : null}
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                {TOOL_CATEGORIES.filter((cat) => !categories.includes(cat)).map((cat) => (
                  <Chip
                    key={cat}
                    label={cat}
                    size="small"
                    clickable
                    onClick={() => setCategories((prev) => [...prev, cat])}
                    sx={{
                      bgcolor: "var(--app-surface)",
                      color: "var(--app-muted)",
                      border: "1px solid var(--app-border)",
                      "&:hover": { borderColor: "var(--app-accent)", color: "var(--app-fg)" },
                    }}
                  />
                ))}
              </Box>
            </Box>
            <Box>
              <FormControl size="small" fullWidth>
                <InputLabel id="openapi-hosting-visibility-label">Hosting visibility</InputLabel>
                <Select
                  labelId="openapi-hosting-visibility-label"
                  label="Hosting visibility"
                  value={hostingVisibility}
                  onChange={(e) =>
                    setHostingVisibility(
                      (e.target.value as "public" | "protected" | "private") || "protected",
                    )
                  }
                >
                  <MenuItem value="public">public</MenuItem>
                  <MenuItem value="protected">protected</MenuItem>
                  <MenuItem value="private">private</MenuItem>
                </Select>
              </FormControl>
              <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "var(--app-muted)" }}>
                public: anyone; protected: auth required; private: only allow-listed users
              </Typography>
            </Box>
            {hostingVisibility === "private" ? (
              <TextField
                label="Allowed users (comma-separated usernames)"
                value={allowedUsersText}
                onChange={(e) => setAllowedUsersText(e.target.value)}
                placeholder="alice,bob"
                size="small"
                fullWidth
              />
            ) : null}
            <TextField
              label="OpenAPI URL"
              value={openapiUrl}
              onChange={(e) => setOpenapiUrl(e.target.value)}
              placeholder="https://your-service-domain.tld/openapi.json"
              size="small"
              fullWidth
            />
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Button
                type="button"
                variant="contained"
                disabled={openapiLoading}
                onClick={() => void fetchAndIngestOpenAPI()}
                sx={{ textTransform: "none" }}
              >
                {openapiLoading ? "Loading…" : "Fetch + ingest"}
              </Button>
              <Button
                type="button"
                variant="text"
                component={Link}
                href="/registry/publish/get-started"
                sx={{ textTransform: "none" }}
              >
                Back to onboarding
              </Button>
            </Box>
          </Box>
        ) : null}

        {activeStep === 1 ? (
          <OperationPicker
            ops={openapiOps}
            selected={openapiSelected}
            setSelected={setOpenapiSelected}
            readyForToolset={readyForToolset}
            loading={openapiLoading}
            selectedCount={selectedKeys.length}
            onCreateToolset={() => void createToolset()}
          />
        ) : null}

        {activeStep === 3 ? (
          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Review and optionally edit the generated manifest and runtime metadata before running preflight.
            </Typography>
            {hostedMcpEndpoint ? (
              <Box sx={{ display: "grid", gap: 0.5 }}>
                <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                  Hosted endpoint
                </Typography>
                <Typography variant="body2" sx={{ color: "var(--app-muted)", wordBreak: "break-all" }}>
                  <Box component="code">{hostedMcpEndpoint}</Box>
                </Typography>
              </Box>
            ) : null}
            <TextField
              label="Manifest JSON"
              value={manifestText}
              onChange={(e) => setManifestText(e.target.value)}
              size="small"
              fullWidth
              multiline
              minRows={8}
              sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
            />
            <TextField
              label="Runtime metadata JSON"
              value={runtimeText}
              onChange={(e) => setRuntimeText(e.target.value)}
              size="small"
              fullWidth
              multiline
              minRows={6}
              sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
            />
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Button
                type="button"
                variant="contained"
                disabled={!readyForPreflight || submitting}
                onClick={() => void runPreflight()}
                sx={{ textTransform: "none" }}
              >
                Run preflight
              </Button>
              <Button
                type="button"
                variant="text"
                disabled={submitting}
                onClick={() => setActiveStep(1)}
                sx={{ textTransform: "none" }}
              >
                Back to operations
              </Button>
            </Box>
          </Box>
        ) : null}

        {activeStep === 4 ? (
          <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
            <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
              Preflight results:
              {" "}
              <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                {preflight?.ready_for_publish ? "Ready" : "Not ready"}
              </Box>
            </Typography>
            {preflight?.report?.findings?.length ? (
              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
                    Findings
                  </Typography>
                  <Box sx={{ mt: 1, display: "grid", gap: 1 }}>
                    {preflight.report.findings.slice(0, 12).map((f, idx) => (
                      <Box key={idx} sx={{ display: "grid", gap: 0.25 }}>
                        <Typography variant="caption" sx={{ color: "var(--app-muted)" }}>
                          {(f.severity ?? "info").toUpperCase()}
                        </Typography>
                        <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
                          {f.summary ?? f.message ?? "Finding"}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </CardContent>
              </Card>
            ) : null}
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              <Button
                type="button"
                variant="contained"
                disabled={submitting || !preflight?.ready_for_publish}
                onClick={() => void submitPublish()}
                sx={{ textTransform: "none" }}
              >
                Publish
              </Button>
              <Button
                type="button"
                variant="outlined"
                disabled={submitting}
                onClick={() => setActiveStep(3)}
                sx={{ textTransform: "none" }}
              >
                Edit manifest/runtime
              </Button>
            </Box>
          </Box>
        ) : null}

      </CardContent>
    </Card>
  );
}

const METHOD_COLORS: Record<string, string> = {
  GET: "#22c55e",
  POST: "#3b82f6",
  PUT: "#f59e0b",
  PATCH: "#a855f7",
  DELETE: "#ef4444",
};

const PAGE_SIZE = 100;

function OperationPicker({
  ops,
  selected,
  setSelected,
  readyForToolset,
  loading,
  selectedCount,
  onCreateToolset,
}: {
  ops: OpenAPIOperation[];
  selected: Record<string, boolean>;
  setSelected: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  readyForToolset: boolean;
  loading: boolean;
  selectedCount: number;
  onCreateToolset: () => void;
}) {
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [page, setPage] = useState(0);

  const allTags = useMemo(() => {
    const bag = new Set<string>();
    for (const op of ops) {
      if (Array.isArray(op.tags)) {
        for (const t of op.tags) {
          const trimmed = String(t).trim();
          if (trimmed) bag.add(trimmed);
        }
      }
    }
    return Array.from(bag).sort((a, b) => a.localeCompare(b));
  }, [ops]);

  const allMethods = useMemo(() => {
    const bag = new Set<string>();
    for (const op of ops) {
      if (op.method) bag.add(op.method.toUpperCase());
    }
    return Array.from(bag).sort();
  }, [ops]);

  const needle = search.toLowerCase().trim();

  const filtered = useMemo(() => {
    return ops.filter((op) => {
      if (methodFilter && (op.method ?? "").toUpperCase() !== methodFilter) return false;
      if (tagFilter) {
        const tags = Array.isArray(op.tags) ? op.tags.map((t) => String(t).trim()) : [];
        if (!tags.includes(tagFilter)) return false;
      }
      if (needle) {
        const hay = [
          op.operation_key,
          op.method,
          op.path,
          op.operation_id,
          op.summary,
          op.description,
          ...(op.tags ?? []),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [ops, needle, tagFilter, methodFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageSlice = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  const allFilteredSelected = filtered.length > 0 && filtered.every((op) => selected[op.operation_key]);

  function toggleFiltered() {
    setSelected((prev) => {
      const next = { ...prev };
      if (allFilteredSelected) {
        for (const op of filtered) next[op.operation_key] = false;
      } else {
        for (const op of filtered) next[op.operation_key] = true;
      }
      return next;
    });
  }

  return (
    <Box sx={{ mt: 2, display: "grid", gap: 1.5 }}>
      <Typography variant="body2" sx={{ color: "var(--app-muted)" }}>
        Select the OpenAPI operations to expose as tools ({ops.length} total, {selectedCount} selected).
      </Typography>

      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
        <TextField
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          placeholder="Search endpoints..."
          size="small"
          sx={{ minWidth: 240, flex: 1 }}
        />
        {allMethods.length > 1 ? (
          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel id="op-method-filter">Method</InputLabel>
            <Select
              labelId="op-method-filter"
              label="Method"
              value={methodFilter}
              onChange={(e) => { setMethodFilter(e.target.value); setPage(0); }}
            >
              <MenuItem value="">All methods</MenuItem>
              {allMethods.map((m) => (
                <MenuItem key={m} value={m}>{m}</MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : null}
        {allTags.length > 1 ? (
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel id="op-tag-filter">Tag</InputLabel>
            <Select
              labelId="op-tag-filter"
              label="Tag"
              value={tagFilter}
              onChange={(e) => { setTagFilter(e.target.value); setPage(0); }}
            >
              <MenuItem value="">All tags ({allTags.length})</MenuItem>
              {allTags.map((t) => (
                <MenuItem key={t} value={t}>{t}</MenuItem>
              ))}
            </Select>
          </FormControl>
        ) : null}
      </Box>

      <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
        <CardContent sx={{ p: 2 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 1 }}>
            <Typography variant="overline" sx={{ color: "var(--app-muted)" }}>
              {filtered.length === ops.length
                ? `${ops.length} operations`
                : `${filtered.length} of ${ops.length} operations`}
            </Typography>
            <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={allFilteredSelected}
                    indeterminate={!allFilteredSelected && filtered.some((op) => selected[op.operation_key])}
                    onChange={toggleFiltered}
                  />
                }
                label={
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    {allFilteredSelected ? "Deselect all" : "Select all"} ({filtered.length})
                  </Typography>
                }
              />
            </Box>
          </Box>

          <Box sx={{ mt: 1, display: "grid", gap: 0.5, maxHeight: 420, overflowY: "auto" }}>
            {pageSlice.map((op) => {
              const key = op.operation_key;
              const method = (op.method ?? "").toUpperCase();
              return (
                <label
                  key={key}
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "flex-start",
                    padding: "4px 0",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={Boolean(selected[key])}
                    onChange={(e) => setSelected((prev) => ({ ...prev, [key]: e.target.checked }))}
                    style={{ marginTop: 3, flexShrink: 0 }}
                  />
                  <Box sx={{ minWidth: 0 }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
                      <Box
                        component="span"
                        sx={{
                          fontSize: 10,
                          fontWeight: 800,
                          fontFamily: "monospace",
                          color: METHOD_COLORS[method] ?? "var(--app-muted)",
                          minWidth: 48,
                        }}
                      >
                        {method}
                      </Box>
                      <Box
                        component="span"
                        sx={{
                          fontSize: 12,
                          fontFamily: "monospace",
                          color: "var(--app-fg)",
                          wordBreak: "break-all",
                        }}
                      >
                        {op.path ?? ""}
                      </Box>
                    </Box>
                    {op.summary ? (
                      <Typography sx={{ fontSize: 11, color: "var(--app-muted)", mt: 0.25 }}>
                        {op.summary}
                      </Typography>
                    ) : null}
                  </Box>
                </label>
              );
            })}
            {filtered.length === 0 ? (
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)", py: 2, textAlign: "center" }}>
                No operations match the current filters.
              </Typography>
            ) : null}
          </Box>

          {pageCount > 1 ? (
            <Box sx={{ mt: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
              <Button
                size="small"
                disabled={safePage === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                sx={{ textTransform: "none", minWidth: 0 }}
              >
                Prev
              </Button>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Page {safePage + 1} of {pageCount}
              </Typography>
              <Button
                size="small"
                disabled={safePage >= pageCount - 1}
                onClick={() => setPage((p) => p + 1)}
                sx={{ textTransform: "none", minWidth: 0 }}
              >
                Next
              </Button>
            </Box>
          ) : null}

          <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
            <Button
              type="button"
              variant="contained"
              disabled={!readyForToolset || loading}
              onClick={onCreateToolset}
              sx={{ textTransform: "none" }}
            >
              Create toolset ({selectedCount})
            </Button>
            <Button
              type="button"
              variant="text"
              onClick={() => setSelected({})}
              sx={{ textTransform: "none" }}
            >
              Clear selection
            </Button>
            <Chip size="small" label={`Selected: ${selectedCount}`} />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

