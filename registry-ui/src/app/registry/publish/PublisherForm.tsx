"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";

import { useRegistryUserPreferences } from "@/hooks/useRegistryUserPreferences";

type PublishManifest = Record<string, unknown>;
type PublishMetadata = Record<string, unknown>;

type PublishRequestBody = {
  display_name: string;
  categories: string[];
  manifest: PublishManifest;
  metadata: PublishMetadata;
  requested_level?: "basic" | "standard" | "advanced";
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

type Props = {
  initialDisplayName?: string;
  initialCategories?: string;
  initialManifestText?: string;
  initialRuntimeText?: string;
};

const DEFAULT_MANIFEST =
  "{\n  \"tool_name\": \"\",\n  \"version\": \"1.0.0\",\n  \"author\": \"\",\n  \"description\": \"\",\n  \"permissions\": [],\n  \"data_flows\": [],\n  \"resource_access\": [],\n  \"tags\": []\n}";

const STEPS = ["Manifest", "Runtime metadata", "Preflight", "Publish"] as const;

type OpenAPIOperation = {
  operation_key: string;
  method?: string;
  path?: string;
  operation_id?: string;
  summary?: string;
  description?: string;
  tags?: string[];
};

type RegistrySessionResponse = {
  auth_enabled?: boolean;
  session?: { username?: string; role?: string } | null;
};

function tryFormatJson(text: string, label: string): { ok: true; text: string } | { ok: false; message: string } {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, text: "{}" };
  try {
    return { ok: true, text: JSON.stringify(JSON.parse(trimmed), null, 2) };
  } catch {
    return { ok: false, message: `${label} is not valid JSON yet.` };
  }
}

function bumpSemver(
  raw: string,
  part: "patch" | "minor" | "major",
): { ok: true; next: string } | { ok: false; message: string } {
  const trimmed = raw.trim();
  if (!trimmed) return { ok: false, message: "Manifest is empty." };
  let obj: any;
  try {
    obj = JSON.parse(trimmed);
  } catch {
    return { ok: false, message: "Manifest must be valid JSON before bumping version." };
  }
  if (!obj || typeof obj !== "object") {
    return { ok: false, message: "Manifest must be a JSON object." };
  }
  const v = String(obj.version ?? "").trim();
  const m = v.match(/^(\d+)\.(\d+)\.(\d+)(.*)?$/);
  if (!m) {
    return { ok: false, message: "Manifest.version must look like X.Y.Z to bump automatically." };
  }
  let major = Number(m[1]);
  let minor = Number(m[2]);
  let patch = Number(m[3]);
  if (!Number.isFinite(major) || !Number.isFinite(minor) || !Number.isFinite(patch)) {
    return { ok: false, message: "Manifest.version is not a valid semver number." };
  }
  if (part === "major") {
    major += 1;
    minor = 0;
    patch = 0;
  } else if (part === "minor") {
    minor += 1;
    patch = 0;
  } else {
    patch += 1;
  }
  obj.version = `${major}.${minor}.${patch}`;
  return { ok: true, next: JSON.stringify(obj, null, 2) };
}

function slugifyToolName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
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

function looksLikeUrl(value: string): boolean {
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
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

function applyOpenapiSelectionToManifest(opts: {
  manifestText: string;
  displayName: string;
  publisherAuthor: string;
  selectedOps: OpenAPIOperation[];
  openapiText: string;
}): { ok: true; nextText: string } | { ok: false; message: string } {
  const formatted = tryFormatJson(opts.manifestText, "Manifest");
  if (!formatted.ok) return { ok: false, message: formatted.message };

  let obj: any;
  try {
    obj = JSON.parse(formatted.text);
  } catch {
    return { ok: false, message: "Manifest must be valid JSON." };
  }
  if (!obj || typeof obj !== "object") {
    return { ok: false, message: "Manifest must be a JSON object." };
  }

  const toolName = String(obj.tool_name ?? "").trim();
  if (!toolName) {
    const inferred = slugifyToolName(opts.displayName);
    if (inferred) obj.tool_name = inferred;
  }

  obj.author = opts.publisherAuthor;

  const permissions = Array.isArray(obj.permissions) ? obj.permissions.map(String) : [];
  obj.permissions = uniqStrings([...permissions, "network_access"]);

  const tags = Array.isArray(obj.tags) ? obj.tags.map(String) : [];
  const opTags = opts.selectedOps.flatMap((op) => (Array.isArray(op.tags) ? op.tags.map(String) : []));
  obj.tags = uniqStrings([...tags, ...opTags]);

  const servers = deriveServersFromOpenapiText(opts.openapiText);
  const resourceAccess = Array.isArray(obj.resource_access) ? obj.resource_access : [];
  if (servers.length) {
    const existingPatterns = new Set(
      resourceAccess
        .map((ra: any) => String(ra?.resource_pattern ?? ""))
        .filter(Boolean),
    );
    for (const url of servers.slice(0, 3)) {
      const pattern = url.replace(/\/+$/g, "") + "/*";
      if (existingPatterns.has(pattern)) continue;
      resourceAccess.push({
        resource_pattern: pattern,
        access_type: "read",
        description: "OpenAPI server base URL",
        classification: "public",
      });
    }
  }
  obj.resource_access = resourceAccess;

  if (!String(obj.description ?? "").trim()) {
    const summaries = opts.selectedOps
      .map((op) => String(op.summary ?? "").trim())
      .filter(Boolean);
    if (summaries.length) obj.description = summaries[0];
  }

  return { ok: true, nextText: JSON.stringify(obj, null, 2) };
}

export function PublisherForm({
  initialDisplayName,
  initialCategories,
  initialManifestText,
  initialRuntimeText,
}: Props) {
  const { prefs } = useRegistryUserPreferences();
  const [activeStep, setActiveStep] = useState(0);

  const [displayName, setDisplayName] = useState(initialDisplayName ?? "");
  const [categories, setCategories] = useState(initialCategories ?? "network,utility");
  const [manifestText, setManifestText] = useState(initialManifestText ?? DEFAULT_MANIFEST);
  const [runtimeText, setRuntimeText] = useState(initialRuntimeText ?? "{}");
  const [preflight, setPreflight] = useState<PublisherPreflightResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [publisherUsername, setPublisherUsername] = useState<string>("");

  // ── OpenAPI helper (MVP) ───────────────────────────────────────────────
  const [openapiUrl, setOpenapiUrl] = useState("");
  const [openapiText, setOpenapiText] = useState("");
  const [openapiLoading, setOpenapiLoading] = useState(false);
  const [openapiSourceId, setOpenapiSourceId] = useState<string | null>(null);
  const [openapiOps, setOpenapiOps] = useState<OpenAPIOperation[]>([]);
  const [openapiSelected, setOpenapiSelected] = useState<Record<string, boolean>>({});
  const [openapiToolsetId, setOpenapiToolsetId] = useState<string | null>(null);
  const [hostedMcpEndpoint, setHostedMcpEndpoint] = useState<string | null>(null);
  const selectedKeys = useMemo(
    () => Object.entries(openapiSelected).filter(([, v]) => v).map(([k]) => k),
    [openapiSelected],
  );

  // ── Manifest Builder (MVP) ─────────────────────────────────────────────
  const [builderToolName, setBuilderToolName] = useState("");
  const [builderVersion, setBuilderVersion] = useState("1.0.0");
  const [builderAuthor, setBuilderAuthor] = useState("");
  const [builderDescription, setBuilderDescription] = useState("");
  const [builderTags, setBuilderTags] = useState("");
  const [builderPermissions, setBuilderPermissions] = useState("network_access");
  const [builderResourcePatterns, setBuilderResourcePatterns] = useState("");
  const [mcpWizardDisplayName, setMcpWizardDisplayName] = useState("");
  const [mcpWizardToolName, setMcpWizardToolName] = useState("");
  const [mcpWizardAuthor, setMcpWizardAuthor] = useState("");
  const [mcpWizardDescription, setMcpWizardDescription] = useState("");
  const [mcpWizardCategories, setMcpWizardCategories] = useState("");
  const [mcpWizardTags, setMcpWizardTags] = useState("");
  const [mcpWizardPackage, setMcpWizardPackage] = useState("");
  const [mcpWizardInstall, setMcpWizardInstall] = useState("");
  const [mcpWizardCommand, setMcpWizardCommand] = useState("");
  const [mcpWizardArgs, setMcpWizardArgs] = useState("");
  const [mcpWizardTransport, setMcpWizardTransport] = useState("stdio");
  const [mcpWizardTools, setMcpWizardTools] = useState("");
  const [mcpWizardPermissions, setMcpWizardPermissions] = useState("read_resource,network_access");
  const [mcpWizardResourcePatterns, setMcpWizardResourcePatterns] = useState("");

  function loadBuilderFromManifest(nextManifestText: string) {
    const formatted = tryFormatJson(nextManifestText, "Manifest");
    if (!formatted.ok) {
      setError(formatted.message);
      return;
    }
    try {
      const obj: any = JSON.parse(formatted.text);
      setBuilderToolName(String(obj?.tool_name ?? ""));
      setBuilderVersion(String(obj?.version ?? "1.0.0"));
      setBuilderAuthor(String(obj?.author ?? ""));
      setBuilderDescription(String(obj?.description ?? ""));
      setBuilderTags(Array.isArray(obj?.tags) ? obj.tags.join(",") : String(obj?.tags ?? ""));
      setBuilderPermissions(
        Array.isArray(obj?.permissions) ? obj.permissions.join(",") : String(obj?.permissions ?? "network_access"),
      );
      const patterns = Array.isArray(obj?.resource_access)
        ? obj.resource_access.map((ra: any) => String(ra?.resource_pattern ?? "")).filter(Boolean)
        : [];
      setBuilderResourcePatterns(patterns.join("\n"));
      setManifestText(formatted.text);
    } catch {
      setError("Manifest is not valid JSON.");
    }
  }

  function applyBuilderToManifest() {
    setError(null);
    const formatted = tryFormatJson(manifestText, "Manifest");
    if (!formatted.ok) {
      setError(formatted.message);
      return;
    }
    let obj: any;
    try {
      obj = JSON.parse(formatted.text);
    } catch {
      setError("Manifest must be valid JSON.");
      return;
    }
    if (!obj || typeof obj !== "object") {
      setError("Manifest must be a JSON object.");
      return;
    }

    const toolName = builderToolName.trim() || slugifyToolName(displayName);
    if (!toolName) {
      setError("Tool name is required (or provide a Display name).");
      return;
    }

    obj.tool_name = toolName;
    obj.version = builderVersion.trim() || "1.0.0";
    obj.author = builderAuthor.trim() || publisherUsername || "publisher";
    obj.description = builderDescription.trim();

    const tags = uniqStrings(
      builderTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    );
    obj.tags = tags;

    const permissions = uniqStrings(
      builderPermissions
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean),
    );
    obj.permissions = permissions;

    const patterns = builderResourcePatterns
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean);
    obj.resource_access = patterns.map((pattern: string) => ({
      resource_pattern: pattern,
      access_type: "read",
      description: "Upstream API access",
      classification: "public",
    }));

    // Keep existing arrays if present
    if (!Array.isArray(obj.data_flows)) obj.data_flows = [];

    setManifestText(JSON.stringify(obj, null, 2));
    setSuccess("Manifest updated from Manifest Builder.");
  }

  function generateFromMcpWizard() {
    setError(null);
    setSuccess(null);
    const nextDisplayName = mcpWizardDisplayName.trim();
    const nextToolName = mcpWizardToolName.trim() || slugifyToolName(nextDisplayName);
    const nextAuthor = mcpWizardAuthor.trim() || publisherUsername || "publisher";
    const nextDescription = mcpWizardDescription.trim();
    const nextCommand = mcpWizardCommand.trim();

    if (!nextDisplayName) {
      setError("MCP wizard needs a display name.");
      return;
    }
    if (!nextToolName) {
      setError("MCP wizard needs a tool name or a display name that can become a tool name.");
      return;
    }
    if (!nextDescription) {
      setError("MCP wizard needs a short description.");
      return;
    }
    if (!nextCommand) {
      setError("MCP wizard needs a run command.");
      return;
    }

    const nextCategories = uniqStrings(
      mcpWizardCategories
        .split(",")
        .map((category) => category.trim())
        .filter(Boolean),
    );
    const nextTags = uniqStrings(
      mcpWizardTags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    );
    const nextPermissions = uniqStrings(
      mcpWizardPermissions
        .split(",")
        .map((permission) => permission.trim())
        .filter(Boolean),
    );
    const nextResourcePatterns = mcpWizardResourcePatterns
      .split("\n")
      .map((pattern) => pattern.trim())
      .filter(Boolean);
    const runtimeArgs = mcpWizardArgs
      .split(/\s+/)
      .map((arg) => arg.trim())
      .filter(Boolean);
    const runtimeTools = mcpWizardTools
      .split(",")
      .map((tool) => tool.trim())
      .filter(Boolean);

    const manifest = {
      tool_name: nextToolName,
      version: "1.0.0",
      author: nextAuthor,
      description: nextDescription,
      permissions: nextPermissions.length ? nextPermissions : ["read_resource"],
      data_flows: [
        {
          source: "input.request",
          destination: "output.response",
          classification: nextResourcePatterns.some((pattern) => pattern.startsWith("file:")) ? "internal" : "public",
          description: "The MCP server receives a tool request and returns the generated response.",
        },
      ],
      resource_access: nextResourcePatterns.map((pattern) => ({
        resource_pattern: pattern,
        access_type: "read",
        description: pattern.startsWith("file:") ? "Reads local resources provided to the MCP server." : "Reads remote resources over the network.",
        classification: pattern.startsWith("file:") ? "internal" : "public",
      })),
      tags: nextTags,
    };
    const runtime = {
      server_type: "mcp",
      transport: mcpWizardTransport.trim() || "stdio",
      package: mcpWizardPackage.trim(),
      install: mcpWizardInstall.trim(),
      command: nextCommand,
      args: runtimeArgs,
      tools: runtimeTools,
    };

    const manifestTextNext = JSON.stringify(manifest, null, 2);
    setDisplayName(nextDisplayName);
    setCategories(nextCategories.length ? nextCategories.join(",") : "utility");
    setManifestText(manifestTextNext);
    setRuntimeText(JSON.stringify(runtime, null, 2));
    setPreflight(null);
    setBuilderToolName(nextToolName);
    setBuilderVersion("1.0.0");
    setBuilderAuthor(nextAuthor);
    setBuilderDescription(nextDescription);
    setBuilderTags(nextTags.join(","));
    setBuilderPermissions((nextPermissions.length ? nextPermissions : ["read_resource"]).join(","));
    setBuilderResourcePatterns(nextResourcePatterns.join("\n"));
    setSuccess("MCP wizard generated the manifest and runtime metadata. Review them, then continue.");
    loadBuilderFromManifest(manifestTextNext);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch("/api/session");
        const payload = (await resp.json().catch(() => null)) as RegistrySessionResponse | null;
        const username = payload?.session?.username ?? "";
        if (cancelled) return;
        setPublisherUsername(username);
        if (!builderAuthor.trim() && username.trim()) {
          setBuilderAuthor(username.trim());
        }
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const parseCommonBody = useCallback((): PublishRequestBody => {
    const body: PublishRequestBody = {
      display_name: "",
      categories: [],
      manifest: {},
      metadata: {},
    };
    body.display_name = displayName.trim();
    body.categories = categories
      .split(",")
      .map((category) => category.trim())
      .filter(Boolean);
    body.manifest = JSON.parse(manifestText) as PublishManifest;
    body.metadata = runtimeText.trim() ? (JSON.parse(runtimeText) as PublishMetadata) : {};
    body.requested_level = prefs.publisher.defaultCertification;
    return body;
  }, [displayName, categories, manifestText, runtimeText, prefs.publisher.defaultCertification]);

  async function fetchAndIngestOpenAPI() {
    setError(null);
    setSuccess(null);
    setOpenapiOps([]);
    setOpenapiSelected({});
    setOpenapiSourceId(null);
    setOpenapiToolsetId(null);
    setHostedMcpEndpoint(null);

    const url = openapiUrl.trim();
    if (!url) {
      setError("Paste an OpenAPI URL first.");
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
        body: JSON.stringify({ title: displayName.trim() || "OpenAPI source", source_url: url, text: fetchPayload.text }),
      });
      const ingestPayload = (await ingestRes.json()) as {
        error?: string;
        source?: { source_id?: string };
        operations?: OpenAPIOperation[];
      };
      if (!ingestRes.ok || ingestPayload.error) {
        setError(ingestPayload.error ?? "OpenAPI ingest failed.");
        return;
      }
      const sid = ingestPayload.source?.source_id ?? null;
      setOpenapiSourceId(sid);
      const ops = Array.isArray(ingestPayload.operations) ? ingestPayload.operations : [];
      setOpenapiOps(ops);
      const nextSelected: Record<string, boolean> = {};
      for (const op of ops.slice(0, 50)) {
        if (op.operation_key) nextSelected[op.operation_key] = false;
      }
      setOpenapiSelected(nextSelected);
      setSuccess(`Loaded ${ops.length} operations from OpenAPI.`);
    } catch (err) {
      console.error("OpenAPI helper error", err);
      setError("Unable to load the OpenAPI document.");
    } finally {
      setOpenapiLoading(false);
    }
  }

  async function createOpenAPIToolset() {
    setError(null);
    setSuccess(null);
    if (!openapiSourceId) {
      setError("Ingest an OpenAPI document first.");
      return;
    }
    if (selectedKeys.length === 0) {
      setError("Select at least one operation to create a toolset.");
      return;
    }

    setOpenapiLoading(true);
    try {
      const sessionRes = await fetch("/api/session");
      const sessionPayload = (await sessionRes.json().catch(() => null)) as RegistrySessionResponse | null;
      const username = sessionPayload?.session?.username ?? "";
      const publisherAuthor = username.trim() || "publisher";

      const res = await fetch("/api/openapi/toolset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_id: openapiSourceId,
          title: `${displayName.trim() || "API"} toolset`,
          selected_operations: selectedKeys,
          tool_name_prefix: (displayName.trim() || "").toLowerCase().replace(/\s+/g, "-").slice(0, 24),
          metadata: {
            upstream_base_url: deriveServersFromOpenapiText(openapiText)[0] ?? "",
          },
        }),
      });
      const payload = (await res.json()) as { error?: string; toolset?: { toolset_id?: string } };
      if (!res.ok || payload.error) {
        setError(payload.error ?? "Toolset creation failed.");
        return;
      }

      const toolsetId = payload.toolset?.toolset_id ?? "";
      if (toolsetId) {
        setOpenapiToolsetId(toolsetId);
        const origin = typeof window !== "undefined" ? window.location.origin : "";
        const endpoint = origin ? `${origin}/mcp/toolsets/${encodeURIComponent(toolsetId)}` : `/mcp/toolsets/${encodeURIComponent(toolsetId)}`;
        setHostedMcpEndpoint(endpoint);

        // Auto-fill runtime metadata (merge if already set).
        const runtimeFormatted = tryFormatJson(runtimeText, "Runtime metadata");
        if (runtimeFormatted.ok) {
          try {
            const rt: any = JSON.parse(runtimeFormatted.text);
            const nextRt = rt && typeof rt === "object" ? rt : {};
            nextRt.server_type = nextRt.server_type ?? "securemcp";
            nextRt.transport = nextRt.transport ?? "streamable-http";
            nextRt.endpoint = endpoint;
            setRuntimeText(JSON.stringify(nextRt, null, 2));
          } catch {
            // ignore
          }
        }
      }

      const selectedOps = openapiOps.filter((op) => selectedKeys.includes(op.operation_key));
      const applied = applyOpenapiSelectionToManifest({
        manifestText,
        displayName,
        publisherAuthor,
        selectedOps,
        openapiText,
      });
      if (!applied.ok) {
        setError(applied.message);
        return;
      }
      setManifestText(applied.nextText);
      loadBuilderFromManifest(applied.nextText);

      setSuccess(
        `Toolset created: ${toolsetId || "ok"}. Hosted MCP endpoint is live immediately (no restart). Manifest + runtime endpoint updated.`,
      );
    } catch (err) {
      console.error("Toolset create error", err);
      setError("Unable to create toolset.");
    } finally {
      setOpenapiLoading(false);
    }
  }

  async function copyHostedEndpoint() {
    if (!hostedMcpEndpoint) return;
    try {
      await navigator.clipboard.writeText(hostedMcpEndpoint);
      setSuccess("Hosted MCP endpoint copied to clipboard.");
    } catch {
      setError("Unable to copy to clipboard (browser permission).");
    }
  }

  function validateManifestForNext(): boolean {
    setError(null);
    const m = tryFormatJson(manifestText, "Manifest");
    if (!m.ok) {
      setError(m.message);
      return false;
    }
    setManifestText(m.text);
    try {
      JSON.parse(m.text);
    } catch {
      setError("Manifest is not valid JSON.");
      return false;
    }
    if (!displayName.trim()) {
      setError("Add a display name before continuing.");
      return false;
    }
    return true;
  }

  function validateRuntimeForNext(): boolean {
    setError(null);
    const r = tryFormatJson(runtimeText, "Runtime metadata");
    if (!r.ok) {
      setError(r.message);
      return false;
    }
    setRuntimeText(r.text);
    return true;
  }

  function handleNext() {
    if (activeStep === 0) {
      if (!validateManifestForNext()) return;
      setActiveStep(1);
      return;
    }
    if (activeStep === 1) {
      if (!validateRuntimeForNext()) return;
      setActiveStep(2);
      return;
    }
    if (activeStep === 2) {
      if (!preflight) {
        setError("Run preflight once before publishing.");
        return;
      }
      setActiveStep(3);
    }
  }

  function handleBack() {
    setError(null);
    setActiveStep((s) => Math.max(0, s - 1));
  }

  async function runPreflight() {
    setError(null);
    setSuccess(null);
    setPreflight(null);
    try {
      const body = parseCommonBody();
      const response = await fetch("/api/publish/preflight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = (await response.json()) as PublisherPreflightResponse;
      if (!response.ok || payload.error) {
        setError(payload.error ?? "Preflight failed.");
      } else {
        setPreflight(payload);
      }
    } catch (err) {
      console.error("Preflight error", err);
      setError("Manifest and runtime metadata must be valid JSON.");
    }
  }

  async function runSubmit() {
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const body = parseCommonBody();
      const response = await fetch("/api/publish/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        setError(payload.error ?? "Publish failed.");
      } else {
        setSuccess("Listing created.");
      }
    } catch (err) {
      console.error("Publish error", err);
      setError("Manifest and runtime metadata must be valid JSON.");
    } finally {
      setSubmitting(false);
    }
  }

  function formatManifestField() {
    const m = tryFormatJson(manifestText, "Manifest");
    if (!m.ok) {
      setError(m.message);
      return;
    }
    setError(null);
    setManifestText(m.text);
  }

  function bumpManifestVersion(part: "patch" | "minor" | "major") {
    setError(null);
    const formatted = tryFormatJson(manifestText, "Manifest");
    if (!formatted.ok) {
      setError(formatted.message);
      return;
    }
    const bumped = bumpSemver(formatted.text, part);
    if (!bumped.ok) {
      setError(bumped.message);
      return;
    }
    setManifestText(bumped.next);
  }

  function formatRuntimeField() {
    const r = tryFormatJson(runtimeText, "Runtime metadata");
    if (!r.ok) {
      setError(r.message);
      return;
    }
    setError(null);
    setRuntimeText(r.text);
  }

  return (
    <Stack component="section" spacing={3}>
      <Card variant="outlined">
        <CardContent sx={{ p: 2.5 }}>
          <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
            Publish flow
          </Typography>
          <Typography sx={{ mt: 0.5, fontSize: 13, color: "var(--app-muted)" }}>
            Same four beats as the publisher tutorial: manifest → runtime → preflight → publish.
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
            <Stack spacing={2} sx={{ mt: 2 }}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Step 1 — Listing identity plus the SecureMCP manifest others will verify against.
              </Typography>

              <Card
                variant="outlined"
                sx={{
                  bgcolor: "var(--app-surface)",
                  borderColor: "var(--app-accent)",
                  boxShadow: "0 20px 60px rgba(37, 99, 235, 0.08)",
                }}
              >
                <CardContent sx={{ p: 2.25 }}>
                  <Box sx={{ display: "grid", gap: 0.75 }}>
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                      <Typography sx={{ fontWeight: 850, color: "var(--app-fg)" }}>
                        Guided MCP Server Wizard
                      </Typography>
                      <Chip size="small" label="No JSON required" sx={{ bgcolor: "var(--app-control-active-bg)", color: "var(--app-muted)", fontWeight: 800 }} />
                    </Box>
                    <Typography sx={{ fontSize: 13, color: "var(--app-muted)", lineHeight: 1.6 }}>
                      Enter the MCP server package/command details and the wizard will generate the manifest and runtime metadata.
                      For MarkItDown, category should be <strong>utility</strong>, with <strong>file_system</strong> and
                      <strong> data_access</strong> as secondary categories.
                    </Typography>
                  </Box>

                  <Stack spacing={1.5} sx={{ mt: 2 }}>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Display name"
                        value={mcpWizardDisplayName}
                        onChange={(e) => setMcpWizardDisplayName(e.target.value)}
                        placeholder="MarkItDown MCP"
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Tool name"
                        value={mcpWizardToolName}
                        onChange={(e) => setMcpWizardToolName(e.target.value)}
                        placeholder="markitdown"
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <TextField
                      label="Description"
                      value={mcpWizardDescription}
                      onChange={(e) => setMcpWizardDescription(e.target.value)}
                      placeholder="Convert documents, files, and URLs into Markdown."
                      size="small"
                      fullWidth
                    />
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Author / publisher"
                        value={mcpWizardAuthor}
                        onChange={(e) => setMcpWizardAuthor(e.target.value)}
                        placeholder="microsoft"
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Categories"
                        value={mcpWizardCategories}
                        onChange={(e) => setMcpWizardCategories(e.target.value)}
                        placeholder="utility,file_system,data_access"
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Package"
                        value={mcpWizardPackage}
                        onChange={(e) => setMcpWizardPackage(e.target.value)}
                        placeholder="markitdown-mcp"
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Install command"
                        value={mcpWizardInstall}
                        onChange={(e) => setMcpWizardInstall(e.target.value)}
                        placeholder="pip install markitdown-mcp"
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Run command"
                        value={mcpWizardCommand}
                        onChange={(e) => setMcpWizardCommand(e.target.value)}
                        placeholder="markitdown-mcp"
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Args"
                        value={mcpWizardArgs}
                        onChange={(e) => setMcpWizardArgs(e.target.value)}
                        placeholder="--http --host 127.0.0.1 --port 3001"
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Transport"
                        value={mcpWizardTransport}
                        onChange={(e) => setMcpWizardTransport(e.target.value)}
                        placeholder="stdio"
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Tools"
                        value={mcpWizardTools}
                        onChange={(e) => setMcpWizardTools(e.target.value)}
                        placeholder="convert_to_markdown"
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <TextField
                      label="Permissions"
                      value={mcpWizardPermissions}
                      onChange={(e) => setMcpWizardPermissions(e.target.value)}
                      placeholder="read_resource,network_access"
                      size="small"
                      fullWidth
                    />
                    <TextField
                      label="Resource access patterns"
                      value={mcpWizardResourcePatterns}
                      onChange={(e) => setMcpWizardResourcePatterns(e.target.value)}
                      placeholder={"file:///*\nhttps://*"}
                      size="small"
                      fullWidth
                      multiline
                      minRows={3}
                      sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
                    />
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                      <Button
                        type="button"
                        variant="contained"
                        onClick={generateFromMcpWizard}
                        sx={{
                          bgcolor: "var(--app-accent)",
                          color: "var(--app-accent-contrast)",
                          textTransform: "none",
                          "&:hover": { bgcolor: "var(--app-accent)" },
                        }}
                      >
                        Generate manifest + runtime
                      </Button>
                      <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
                        MarkItDown category: utility, file_system, data_access
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>

              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Manifest Builder</Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                    Use friendly fields, then apply into the JSON manifest. This is the recommended path for publishers.
                  </Typography>

                  <Stack spacing={1.5} sx={{ mt: 1.5 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                      <TextField
                        label="Tool name"
                        value={builderToolName}
                        onChange={(e) => setBuilderToolName(e.target.value)}
                        placeholder={slugifyToolName(displayName) || "my-tool"}
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Version"
                        value={builderVersion}
                        onChange={(e) => setBuilderVersion(e.target.value)}
                        placeholder="1.0.0"
                        size="small"
                        sx={{ width: { xs: "100%", sm: 180 } }}
                      />
                    </Stack>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                      <TextField
                        label="Author"
                        value={builderAuthor}
                        onChange={(e) => setBuilderAuthor(e.target.value)}
                        placeholder={publisherUsername || "publisher"}
                        size="small"
                        fullWidth
                      />
                      <Button
                        type="button"
                        variant="text"
                        onClick={() => setBuilderAuthor(publisherUsername || "publisher")}
                        sx={{ textTransform: "none", alignSelf: { xs: "flex-start", sm: "center" } }}
                      >
                        Use Publisher
                      </Button>
                    </Stack>

                    <TextField
                      label="Description"
                      value={builderDescription}
                      onChange={(e) => setBuilderDescription(e.target.value)}
                      placeholder="What does your tool do?"
                      size="small"
                      fullWidth
                    />
                    <TextField
                      label="Tags (comma-separated)"
                      value={builderTags}
                      onChange={(e) => setBuilderTags(e.target.value)}
                      placeholder="security,encryption,api"
                      size="small"
                      fullWidth
                    />
                    <TextField
                      label="Permissions (comma-separated)"
                      value={builderPermissions}
                      onChange={(e) => setBuilderPermissions(e.target.value)}
                      placeholder="network_access"
                      size="small"
                      fullWidth
                    />
                    <TextField
                      label="Resource access patterns (one per line)"
                      value={builderResourcePatterns}
                      onChange={(e) => setBuilderResourcePatterns(e.target.value)}
                      placeholder="https://your-service-domain.tld/*"
                      size="small"
                      fullWidth
                      multiline
                      minRows={3}
                      sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
                    />

                    <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                      <Button
                        type="button"
                        variant="contained"
                        onClick={applyBuilderToManifest}
                        sx={{ textTransform: "none" }}
                      >
                        Apply to manifest JSON
                      </Button>
                      <Button
                        type="button"
                        variant="outlined"
                        onClick={() => loadBuilderFromManifest(manifestText)}
                        sx={{ textTransform: "none" }}
                      >
                        Load from current JSON
                      </Button>
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>

              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>REST/OpenAPI helper (MVP)</Typography>
                  <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)" }}>
                    Fetch an <Box component="code">openapi.json</Box>, inspect operations, and create a server-side toolset record.
                    This does not yet publish a listing or host the gateway automatically.
                  </Typography>

                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.5 }}>
                    <TextField
                      label="OpenAPI URL"
                      value={openapiUrl}
                      onChange={(e) => setOpenapiUrl(e.target.value)}
                      placeholder="https://your-service-domain.tld/openapi.json"
                      size="small"
                      fullWidth
                    />
                    <Button
                      type="button"
                      variant="outlined"
                      disabled={openapiLoading}
                      onClick={() => void fetchAndIngestOpenAPI()}
                      sx={{ textTransform: "none", whiteSpace: "nowrap" }}
                    >
                      {openapiLoading ? "Loading…" : "Fetch + ingest"}
                    </Button>
                  </Stack>

                  {openapiOps.length ? (
                    <Box sx={{ mt: 1.5 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                        Operations
                      </Typography>
                      <Box sx={{ mt: 1, display: "grid", gap: 0.75 }}>
                        {openapiOps.slice(0, 30).map((op) => {
                          const key = op.operation_key;
                          const label = `${(op.method ?? "").toUpperCase()} ${op.path ?? ""} — ${op.summary ?? key}`;
                          return (
                            <label key={key} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                              <input
                                type="checkbox"
                                checked={Boolean(openapiSelected[key])}
                                onChange={(e) =>
                                  setOpenapiSelected((prev) => ({ ...prev, [key]: e.target.checked }))
                                }
                                style={{ marginTop: 3 }}
                              />
                              <span style={{ fontSize: 12, color: "var(--app-muted)" }}>{label}</span>
                            </label>
                          );
                        })}
                        {openapiOps.length > 30 ? (
                          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                            Showing first 30 operations (MVP). Parsed: {openapiOps.length}.
                          </Typography>
                        ) : null}
                      </Box>
                      <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: "wrap" }}>
                        <Button
                          type="button"
                          variant="contained"
                          disabled={openapiLoading || selectedKeys.length === 0}
                          onClick={() => void createOpenAPIToolset()}
                          sx={{ textTransform: "none" }}
                        >
                          Create toolset ({selectedKeys.length})
                        </Button>
                        <Button
                          type="button"
                          variant="text"
                          onClick={() => setOpenapiSelected({})}
                          sx={{ textTransform: "none" }}
                        >
                          Clear selection
                        </Button>
                      </Stack>
                      {hostedMcpEndpoint ? (
                        <Box sx={{ mt: 1.5 }}>
                          <Typography sx={{ fontSize: 12, fontWeight: 700, color: "var(--app-fg)" }}>
                            Hosted MCP endpoint
                          </Typography>
                          <Typography sx={{ mt: 0.5, fontSize: 12, color: "var(--app-muted)", wordBreak: "break-all" }}>
                            <Box component="code">{hostedMcpEndpoint}</Box>
                          </Typography>
                          <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: "wrap" }}>
                            <Button
                              type="button"
                              size="small"
                              variant="outlined"
                              onClick={() => void copyHostedEndpoint()}
                              sx={{ textTransform: "none" }}
                            >
                              Copy endpoint
                            </Button>
                          </Stack>
                        </Box>
                      ) : null}
                      {openapiSourceId ? (
                        <Typography sx={{ mt: 1, fontSize: 11, color: "var(--app-muted)" }}>
                          Source id: <Box component="code">{openapiSourceId}</Box>
                        </Typography>
                      ) : null}
                      {openapiToolsetId ? (
                        <Typography sx={{ mt: 0.5, fontSize: 11, color: "var(--app-muted)" }}>
                          Toolset id: <Box component="code">{openapiToolsetId}</Box>
                        </Typography>
                      ) : null}
                    </Box>
                  ) : null}
                </CardContent>
              </Card>

              <TextField
                label="Display name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your MCP tool"
                size="small"
                fullWidth
              />
              <TextField
                label="Categories (comma-separated)"
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
                placeholder="network,utility"
                size="small"
                fullWidth
              />
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                  Manifest JSON
                </Typography>
                <Button type="button" size="small" variant="outlined" onClick={formatManifestField} sx={{ textTransform: "none" }}>
                  Format manifest
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant="text"
                  onClick={() => bumpManifestVersion("patch")}
                  sx={{ textTransform: "none" }}
                >
                  Bump patch
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant="text"
                  onClick={() => bumpManifestVersion("minor")}
                  sx={{ textTransform: "none" }}
                >
                  Bump minor
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant="text"
                  onClick={() => bumpManifestVersion("major")}
                  sx={{ textTransform: "none" }}
                >
                  Bump major
                </Button>
              </Box>
              <TextField
                value={manifestText}
                onChange={(e) => setManifestText(e.target.value)}
                multiline
                minRows={12}
                fullWidth
                sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
              />
            </Stack>
          ) : null}

          {activeStep === 1 ? (
            <Stack spacing={2} sx={{ mt: 2 }}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Step 2 — How to run or connect (endpoint, transport, Docker, CLI, env). Leave as <Box component="code">{"{}"}</Box> if you only want the listing without install hints.
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
                <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--app-muted)" }}>
                  Runtime metadata JSON
                </Typography>
                <Button type="button" size="small" variant="outlined" onClick={formatRuntimeField} sx={{ textTransform: "none" }}>
                  Format JSON
                </Button>
              </Box>
              <TextField
                value={runtimeText}
                onChange={(e) => setRuntimeText(e.target.value)}
                multiline
                minRows={10}
                fullWidth
                sx={{ "& textarea": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 } }}
              />
            </Stack>
          ) : null}

          {activeStep === 2 ? (
            <Stack spacing={2} sx={{ mt: 2 }}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Step 3 — Run preflight so the registry can evaluate guardrails and certification posture before you submit.
              </Typography>
              <Alert severity="info" sx={{ borderRadius: 3 }}>
                Publisher preference applied: preflight will request <strong>{prefs.publisher.defaultCertification}</strong> certification.
              </Alert>
              <Button
                type="button"
                onClick={() => void runPreflight()}
                variant="contained"
                sx={{
                  alignSelf: "flex-start",
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  "&:hover": { bgcolor: "var(--app-accent)" },
                }}
              >
                Run preflight
              </Button>

              {preflight ? (
                <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                  <CardContent sx={{ p: 2 }}>
                    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
                      <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Preflight result</Typography>
                      <Chip
                        size="small"
                        label={preflight.ready_for_publish ? "Ready to publish" : "Needs changes"}
                        sx={{
                          bgcolor: preflight.ready_for_publish ? "var(--app-control-active-bg)" : "rgba(245, 158, 11, 0.18)",
                          color: preflight.ready_for_publish ? "var(--app-fg)" : "#92400e",
                          fontSize: 11,
                          fontWeight: 700,
                          letterSpacing: "0.01em",
                        }}
                      />
                    </Box>
                    <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>{preflight.summary}</Typography>

                    <Box sx={{ mt: 1.5, display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                          Effective level:
                        </Box>{" "}
                        {preflight.effective_certification_level}
                      </Typography>
                      <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                        <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                          Registry minimum:
                        </Box>{" "}
                        {preflight.minimum_required_level}
                      </Typography>
                    </Box>

                    {Array.isArray(preflight.report?.findings) && preflight.report.findings.length > 0 ? (
                      <Box sx={{ mt: 1.5 }}>
                        <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Guardrail findings</Typography>
                        <Box component="ul" sx={{ mt: 1, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                          {preflight.report.findings.slice(0, 6).map((finding, index) => (
                            <li key={index}>
                              <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                                {finding.severity?.toUpperCase?.() ?? "INFO"}:
                              </Box>{" "}
                              {finding.message ?? finding.summary ?? "See certification report."}
                            </li>
                          ))}
                          {preflight.report.findings.length > 6 ? (
                            <li>
                              +{preflight.report.findings.length - 6} more finding
                              {preflight.report.findings.length - 6 === 1 ? "" : "s"} in the full report.
                            </li>
                          ) : null}
                        </Box>
                      </Box>
                    ) : null}
                  </CardContent>
                </Card>
              ) : (
                <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>Preflight has not been run in this session yet.</Typography>
              )}
            </Stack>
          ) : null}

          {activeStep === 3 ? (
            <Stack spacing={2} sx={{ mt: 2 }}>
              <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                Step 4 — Submit the listing. If moderation is enabled, it may stay pending until a reviewer approves.
              </Typography>
              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Summary</Typography>
                  <Box component="ul" sx={{ mt: 1, pl: 2, color: "var(--app-muted)", fontSize: 12 }}>
                    <li>
                      <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Display name:</Box> {displayName.trim() || "—"}
                    </li>
                    <li>
                      <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Categories:</Box> {categories.trim() || "—"}
                    </li>
                    <li>
                      <Box component="span" sx={{ fontWeight: 700, color: "var(--app-fg)" }}>Preflight:</Box>{" "}
                      {preflight?.ready_for_publish ? "Ready to publish" : preflight ? "Needs changes (you may still submit)" : "—"}
                    </li>
                  </Box>
                </CardContent>
              </Card>
              <Button
                type="button"
                disabled={submitting}
                onClick={() => void runSubmit()}
                variant="contained"
                sx={{
                  alignSelf: "flex-start",
                  bgcolor: "var(--app-accent)",
                  color: "var(--app-accent-contrast)",
                  "&:hover": { bgcolor: "var(--app-accent)" },
                }}
              >
                {submitting ? "Publishing…" : "Publish listing"}
              </Button>
            </Stack>
          ) : null}

          <Stack direction="row" spacing={1} sx={{ mt: 3, flexWrap: "wrap", justifyContent: "space-between" }}>
            <Button type="button" variant="text" disabled={activeStep === 0} onClick={handleBack} sx={{ textTransform: "none" }}>
              Back
            </Button>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
              {activeStep < 2 ? (
                <Button type="button" variant="contained" onClick={handleNext} sx={{ textTransform: "none" }}>
                  Next
                </Button>
              ) : null}
              {activeStep === 2 ? (
                <Button
                  type="button"
                  variant="contained"
                  disabled={!preflight}
                  onClick={handleNext}
                  sx={{ textTransform: "none" }}
                >
                  Continue to publish
                </Button>
              ) : null}
              {activeStep === 3 ? (
                <Button type="button" variant="outlined" onClick={() => setActiveStep(2)} sx={{ textTransform: "none" }}>
                  Edit preflight
                </Button>
              ) : null}
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Stack>
  );
}
