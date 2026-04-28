"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  MenuItem,
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

// Iter 14.3: enum members exactly as defined on the backend
// (fastmcp.server.security.gateway.tool_marketplace.ToolCategory and
// fastmcp.server.security.certification.manifest.PermissionScope).
// Free-text inputs let typos slip through to submit-time failures;
// constrained pickers backed by these arrays keep the wizard honest.
const TOOL_CATEGORIES = [
  "data_access",
  "file_system",
  "network",
  "code_execution",
  "ai_ml",
  "communication",
  "search",
  "database",
  "authentication",
  "monitoring",
  "utility",
  "other",
] as const;

const PERMISSION_SCOPES = [
  "read_resource",
  "write_resource",
  "call_tool",
  "network_access",
  "file_system_read",
  "file_system_write",
  "environment_read",
  "subprocess_exec",
  "sensitive_data",
  "cross_origin",
] as const;

const MCP_TRANSPORTS = [
  "stdio",
  "streamable-http",
  "sse",
  "http",
] as const;


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
  // Iter 14.3: was comma-string; now array-backed multi-select to
  // prevent submit-time failures from typo'd category names.
  const [mcpWizardCategories, setMcpWizardCategories] = useState<string[]>([]);
  const [mcpWizardTags, setMcpWizardTags] = useState("");
  const [mcpWizardPackage, setMcpWizardPackage] = useState("");
  const [mcpWizardInstall, setMcpWizardInstall] = useState("");
  const [mcpWizardCommand, setMcpWizardCommand] = useState("");
  const [mcpWizardArgs, setMcpWizardArgs] = useState("");
  const [mcpWizardTransport, setMcpWizardTransport] = useState("stdio");
  const [mcpWizardTools, setMcpWizardTools] = useState("");
  // Iter 14.3: was comma-string; now array-backed multi-select.
  const [mcpWizardPermissions, setMcpWizardPermissions] = useState<string[]>([
    "read_resource",
    "network_access",
  ]);
  const [mcpWizardResourcePatterns, setMcpWizardResourcePatterns] = useState("");
  // Iter 14.3: surfaced in the wizard so publishers don't have to
  // expand the Advanced JSON disclosure to set them.
  const [mcpWizardVersion, setMcpWizardVersion] = useState("0.1.0");
  const [mcpWizardLicense, setMcpWizardLicense] = useState("");
  const [mcpWizardSourceUrl, setMcpWizardSourceUrl] = useState("");
  // Iter 14.3: pre-slugify the tool name when the user blurs the
  // field so they see exactly what will be saved instead of finding
  // out at submit time.
  const [mcpWizardToolNameSlug, setMcpWizardToolNameSlug] = useState("");
  // Iter 14.1: distribution channel — http / pypi (default) / npm /
  // docker / github. Picking one pre-fills Install/Run command
  // templates if those fields are still empty, and the chosen value
  // rides through into runtime metadata as ``upstream_channel`` so
  // the curator/proxy runtime can dispatch on it.
  // Iter 14.3 default ``"pypi"`` matches the page-level
  // ``startingPoint`` default below so both chip groups agree on
  // first render.
  const [mcpWizardChannel, setMcpWizardChannel] = useState<
    "http" | "pypi" | "npm" | "docker" | "github"
  >("pypi");

  // Iter 14.4: per-field auto-fill state. The "don't clobber user
  // input" guard from Iter 14.1 used `if (!field.trim())` which
  // can't tell *"the user typed this"* apart from *"I auto-filled
  // this last time."* — so once any template lands in a field, every
  // subsequent chip click is silently skipped. Track whether the
  // current value came from a template; user typing flips it false.
  const [installAutoFilled, setInstallAutoFilled] = useState(true);
  const [commandAutoFilled, setCommandAutoFilled] = useState(true);
  const [permissionsAutoFilled, setPermissionsAutoFilled] = useState(true);

  // Iter 14.2: page-level "what are you shipping?" picker. Six
  // options drive which form section is visible — five package
  // channels (HTTP/PyPI/npm/Docker/GitHub) feed the Guided Wizard;
  // ``openapi`` swaps the wizard out for the OpenAPI helper as the
  // primary form. Manifest Builder demotes to an Advanced disclosure
  // regardless. Default ``pypi`` is the most common publishing path.
  type StartingPoint =
    | "http"
    | "pypi"
    | "npm"
    | "docker"
    | "github"
    | "openapi";
  const [startingPoint, setStartingPoint] = useState<StartingPoint>("pypi");
  const [advancedJsonOpen, setAdvancedJsonOpen] = useState(false);
  const isOpenAPIStartingPoint = startingPoint === "openapi";

  function pickStartingPoint(next: StartingPoint) {
    setStartingPoint(next);
    if (next !== "openapi") {
      // Sync the wizard's internal channel state so its templates +
      // placeholders match the page-level choice.
      applyChannelTemplate(next);
    }
  }

  function applyChannelTemplate(
    channel: "http" | "pypi" | "npm" | "docker" | "github",
  ) {
    setMcpWizardChannel(channel);
    // Default transport: HTTP-channel servers run as streamable-http;
    // language-package servers default to stdio.
    if (channel === "http") {
      if (!mcpWizardTransport.trim() || mcpWizardTransport === "stdio") {
        setMcpWizardTransport("streamable-http");
      }
    } else if (mcpWizardTransport === "streamable-http") {
      setMcpWizardTransport("stdio");
    }
    // Iter 14.4: re-template the install/run/permissions fields
    // whenever the user picks a channel chip — but only if those
    // fields are still in their auto-filled state. As soon as the
    // user types into a field, its flag flips false and that
    // particular field stops being re-templated. Net result:
    // chip clicks always update untouched fields; explicit edits
    // are preserved.
    const pkg = mcpWizardPackage.trim();
    let nextInstall = "";
    let nextCommand = "";
    if (channel === "pypi") {
      nextInstall = pkg ? `pip install ${pkg}` : "pip install <package>";
      nextCommand = pkg ? `python -m ${pkg}` : "python -m <package>";
    } else if (channel === "npm") {
      nextInstall = pkg ? `npm install -g ${pkg}` : "npm install -g <package>";
      nextCommand = pkg ? `npx ${pkg}` : "npx <package>";
    } else if (channel === "docker") {
      nextInstall = pkg ? `docker pull ${pkg}` : "docker pull <image>";
      nextCommand = pkg
        ? `docker run --rm -i ${pkg}`
        : "docker run --rm -i <image>";
    } else if (channel === "github") {
      nextInstall = pkg
        ? `git clone ${pkg}`
        : "git clone https://github.com/<owner>/<repo>";
      // GitHub has no canonical run command — clear so the publisher
      // fills it in (rather than carrying the previous channel's
      // template forward).
      nextCommand = "";
    } else if (channel === "http") {
      // HTTP endpoints don't have an install step; the run command
      // is the endpoint URL itself.
      nextInstall = "";
      nextCommand = "https://server.example.com/mcp";
    }
    if (installAutoFilled) {
      setMcpWizardInstall(nextInstall);
    }
    if (commandAutoFilled) {
      setMcpWizardCommand(nextCommand);
    }
    // Channel-aware permission defaults. Only when the publisher
    // hasn't typed/edited the permission set themselves.
    if (permissionsAutoFilled) {
      if (channel === "docker") {
        setMcpWizardPermissions([
          "network_access",
          "subprocess_exec",
          "read_resource",
        ]);
      } else {
        // pypi / npm / http / github all default to the standard
        // read + network combo.
        setMcpWizardPermissions(["read_resource", "network_access"]);
      }
    }
  }

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

    // Iter 14.3: categories + permissions are now array-backed
    // (constrained pickers), so just dedupe + sanity-trim.
    const nextCategories = uniqStrings(
      mcpWizardCategories.map((c) => c.trim()).filter(Boolean),
    );
    const nextTags = uniqStrings(
      mcpWizardTags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    );
    const nextPermissions = uniqStrings(
      mcpWizardPermissions.map((p) => p.trim()).filter(Boolean),
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
      version: mcpWizardVersion.trim() || "0.1.0",
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
      // Iter 14.1: distribution channel. Drives downstream dispatch
      // (curator pinning, proxy runtime client factory, install
      // recipe rendering).
      upstream_channel: mcpWizardChannel,
      // Iter 14.3: surfaced license + source URL travel in runtime
      // metadata so the public detail page can link them.
      ...(mcpWizardLicense.trim()
        ? { tool_license: mcpWizardLicense.trim() }
        : {}),
      ...(mcpWizardSourceUrl.trim()
        ? { source_url: mcpWizardSourceUrl.trim() }
        : {}),
    };

    const manifestTextNext = JSON.stringify(manifest, null, 2);
    setDisplayName(nextDisplayName);
    setCategories(nextCategories.length ? nextCategories.join(",") : "utility");
    setManifestText(manifestTextNext);
    setRuntimeText(JSON.stringify(runtime, null, 2));
    setPreflight(null);
    setBuilderToolName(nextToolName);
    setBuilderVersion(mcpWizardVersion.trim() || "0.1.0");
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

              {/* Iter 14.2: page-level "what are you shipping?" picker
                  that drives which form section is primary below.
                  Replaces the previous wall of three coequal panels
                  with a linear flow that adapts to the publisher's
                  starting point. */}
              <Card
                variant="outlined"
                sx={{
                  bgcolor: "var(--app-control-bg)",
                  borderColor: "var(--app-control-border)",
                }}
              >
                <CardContent sx={{ p: 2.25 }}>
                  <Typography
                    sx={{
                      fontSize: 11,
                      fontWeight: 800,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "var(--app-muted)",
                    }}
                  >
                    What are you shipping?
                  </Typography>
                  <Typography
                    sx={{
                      mt: 0.5,
                      fontSize: 13,
                      color: "var(--app-muted)",
                      lineHeight: 1.6,
                    }}
                  >
                    Pick the starting point that matches what you have. The form
                    below adapts: package channels feed the Guided Wizard;
                    OpenAPI swaps in the REST helper as the primary form.
                  </Typography>
                  <Box
                    sx={{
                      mt: 1.25,
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 0.75,
                    }}
                  >
                    {(
                      [
                        { value: "http", label: "HTTP / SSE", hint: "https endpoint" },
                        { value: "pypi", label: "PyPI", hint: "pip package" },
                        { value: "npm", label: "npm", hint: "node package" },
                        { value: "docker", label: "Docker", hint: "container image" },
                        { value: "github", label: "GitHub", hint: "git source" },
                        { value: "openapi", label: "OpenAPI / REST", hint: "openapi.json" },
                      ] as const
                    ).map((opt) => {
                      const selected = startingPoint === opt.value;
                      return (
                        <Chip
                          key={opt.value}
                          size="medium"
                          label={`${opt.label} · ${opt.hint}`}
                          clickable
                          onClick={() => pickStartingPoint(opt.value)}
                          variant={selected ? "filled" : "outlined"}
                          sx={{
                            fontWeight: 800,
                            bgcolor: selected
                              ? "var(--app-accent)"
                              : "var(--app-surface)",
                            color: selected
                              ? "var(--app-accent-contrast)"
                              : "var(--app-fg)",
                            borderColor: "var(--app-control-border)",
                            "&:hover": {
                              bgcolor: selected
                                ? "var(--app-accent)"
                                : "var(--app-hover-bg)",
                            },
                          }}
                        />
                      );
                    })}
                  </Box>
                </CardContent>
              </Card>

              {!isOpenAPIStartingPoint ? (
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
                        onBlur={() => {
                          // Iter 14.3: pre-slugify on blur so the
                          // user sees the validated form before
                          // hitting Generate.
                          const raw = mcpWizardToolName.trim();
                          if (!raw) {
                            setMcpWizardToolNameSlug("");
                            return;
                          }
                          const slug = slugifyToolName(raw);
                          setMcpWizardToolNameSlug(slug);
                          if (slug && slug !== raw) {
                            setMcpWizardToolName(slug);
                          }
                        }}
                        placeholder="markitdown"
                        size="small"
                        fullWidth
                        helperText={
                          mcpWizardToolNameSlug &&
                          mcpWizardToolNameSlug !== mcpWizardToolName
                            ? `Will save as: ${mcpWizardToolNameSlug}`
                            : "Lowercase letters, digits, hyphens."
                        }
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
                        placeholder={publisherUsername || "your-username"}
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Categories"
                        select
                        value={mcpWizardCategories}
                        onChange={(e) => {
                          const v = e.target.value;
                          setMcpWizardCategories(
                            typeof v === "string" ? v.split(",") : (v as string[]),
                          );
                        }}
                        slotProps={{
                          select: {
                            multiple: true,
                            renderValue: (selected: unknown) =>
                              (selected as string[]).join(", "),
                          },
                        }}
                        helperText={
                          mcpWizardCategories.length === 0
                            ? "Pick one or more (defaults to utility on submit)."
                            : `${mcpWizardCategories.length} selected`
                        }
                        size="small"
                        fullWidth
                      >
                        {TOOL_CATEGORIES.map((cat) => (
                          <MenuItem key={cat} value={cat}>
                            {cat}
                          </MenuItem>
                        ))}
                      </TextField>
                    </Stack>
                    {/* Iter 14.3: surfaced version + license + source
                        URL — used to be hidden in the Manifest
                        Builder Advanced disclosure. */}
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Version"
                        value={mcpWizardVersion}
                        onChange={(e) => setMcpWizardVersion(e.target.value)}
                        placeholder="0.1.0"
                        helperText="SemVer. 0.x.y is fine for early publishes."
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="License (SPDX)"
                        value={mcpWizardLicense}
                        onChange={(e) => setMcpWizardLicense(e.target.value)}
                        placeholder="Apache-2.0"
                        helperText="Optional. e.g. MIT, Apache-2.0, BSD-3-Clause."
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Source URL"
                        value={mcpWizardSourceUrl}
                        onChange={(e) => setMcpWizardSourceUrl(e.target.value)}
                        placeholder="https://github.com/owner/repo"
                        helperText="Optional. Linked from the public detail page."
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <Box>
                      <Typography
                        sx={{
                          fontSize: 11,
                          fontWeight: 800,
                          letterSpacing: "0.16em",
                          textTransform: "uppercase",
                          color: "var(--app-muted)",
                          mb: 0.75,
                        }}
                      >
                        Distribution channel
                      </Typography>
                      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                        {(
                          [
                            { value: "http", label: "HTTP / SSE", hint: "https endpoint" },
                            { value: "pypi", label: "PyPI", hint: "pip package" },
                            { value: "npm", label: "npm", hint: "node package" },
                            { value: "docker", label: "Docker", hint: "container image" },
                            { value: "github", label: "GitHub", hint: "git source" },
                          ] as const
                        ).map((opt) => {
                          const selected = mcpWizardChannel === opt.value;
                          return (
                            <Chip
                              key={opt.value}
                              size="small"
                              label={opt.label}
                              clickable
                              onClick={() => applyChannelTemplate(opt.value)}
                              variant={selected ? "filled" : "outlined"}
                              sx={{
                                fontWeight: 800,
                                bgcolor: selected
                                  ? "var(--app-accent)"
                                  : "var(--app-control-bg)",
                                color: selected
                                  ? "var(--app-accent-contrast)"
                                  : "var(--app-fg)",
                                borderColor: "var(--app-control-border)",
                                "&:hover": {
                                  bgcolor: selected
                                    ? "var(--app-accent)"
                                    : "var(--app-hover-bg)",
                                },
                              }}
                            />
                          );
                        })}
                      </Box>
                      <Typography
                        sx={{ fontSize: 11, color: "var(--app-muted)", mt: 0.5 }}
                      >
                        Picking a channel pre-fills the install / run command
                        templates below. Edit them freely afterwards.
                      </Typography>
                    </Box>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Package"
                        value={mcpWizardPackage}
                        onChange={(e) => setMcpWizardPackage(e.target.value)}
                        placeholder={
                          mcpWizardChannel === "docker"
                            ? "ghcr.io/example/mcp:1.2.3"
                            : mcpWizardChannel === "npm"
                              ? "@modelcontextprotocol/server-everything"
                              : mcpWizardChannel === "github"
                                ? "https://github.com/owner/repo"
                                : mcpWizardChannel === "http"
                                  ? "(no package — HTTP endpoint)"
                                  : "markitdown-mcp"
                        }
                        size="small"
                        fullWidth
                      />
                      <TextField
                        label="Install command"
                        value={mcpWizardInstall}
                        onChange={(e) => {
                          setMcpWizardInstall(e.target.value);
                          // Iter 14.4: the user is now editing —
                          // future chip clicks won't overwrite this.
                          setInstallAutoFilled(false);
                        }}
                        placeholder={
                          mcpWizardChannel === "docker"
                            ? "docker pull ghcr.io/example/mcp:1.2.3"
                            : mcpWizardChannel === "npm"
                              ? "npm install -g <package>"
                              : mcpWizardChannel === "github"
                                ? "git clone https://github.com/owner/repo"
                                : mcpWizardChannel === "http"
                                  ? "(none — connect directly)"
                                  : "pip install markitdown-mcp"
                        }
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        label="Run command"
                        value={mcpWizardCommand}
                        onChange={(e) => {
                          setMcpWizardCommand(e.target.value);
                          // Iter 14.4: explicit edit — stop
                          // re-templating this field on chip clicks.
                          setCommandAutoFilled(false);
                        }}
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
                        select
                        value={mcpWizardTransport}
                        onChange={(e) => setMcpWizardTransport(e.target.value)}
                        helperText="MCP transport the server speaks."
                        size="small"
                        fullWidth
                      >
                        {MCP_TRANSPORTS.map((t) => (
                          <MenuItem key={t} value={t}>
                            {t}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        label="Tools"
                        value={mcpWizardTools}
                        onChange={(e) => setMcpWizardTools(e.target.value)}
                        placeholder="convert_to_markdown"
                        helperText="Comma-separated MCP tool names the server exposes."
                        size="small"
                        fullWidth
                      />
                    </Stack>
                    <TextField
                      label="Permissions"
                      select
                      value={mcpWizardPermissions}
                      onChange={(e) => {
                        const v = e.target.value;
                        setMcpWizardPermissions(
                          typeof v === "string" ? v.split(",") : (v as string[]),
                        );
                        // Iter 14.4: explicit edit — chip clicks
                        // won't re-template permissions after this.
                        setPermissionsAutoFilled(false);
                      }}
                      slotProps={{
                        select: {
                          multiple: true,
                          renderValue: (selected: unknown) =>
                            (selected as string[]).join(", "),
                        },
                      }}
                      helperText={
                        mcpWizardPermissions.length === 0
                          ? "Pick the permission scopes the server needs."
                          : `${mcpWizardPermissions.length} selected`
                      }
                      size="small"
                      fullWidth
                    >
                      {PERMISSION_SCOPES.map((scope) => (
                        <MenuItem key={scope} value={scope}>
                          {scope}
                        </MenuItem>
                      ))}
                    </TextField>
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
                        Produces the manifest + runtime metadata for Steps 2–4.
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
              ) : null}

              {/* Iter 14.2: Manifest Builder demoted to an Advanced
                  disclosure — most publishers don't need to hand-edit
                  JSON, the Wizard above produces it for them. */}
              <Card variant="outlined" sx={{ bgcolor: "var(--app-control-bg)" }}>
                <CardContent sx={{ p: 2 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 1,
                    }}
                  >
                    <Box>
                      <Typography sx={{ fontWeight: 700, color: "var(--app-fg)" }}>
                        Advanced: edit manifest JSON directly
                      </Typography>
                      <Typography
                        sx={{ mt: 0.25, fontSize: 12, color: "var(--app-muted)" }}
                      >
                        Most publishers don't need this — the form above produces
                        the manifest. Open if you want fine-grained control.
                      </Typography>
                    </Box>
                    <Button
                      type="button"
                      variant="outlined"
                      size="small"
                      onClick={() => setAdvancedJsonOpen((v) => !v)}
                      sx={{ textTransform: "none", whiteSpace: "nowrap" }}
                    >
                      {advancedJsonOpen ? "Collapse" : "Expand"}
                    </Button>
                  </Box>
                  {advancedJsonOpen ? (
                  <Typography sx={{ mt: 1, fontSize: 12, color: "var(--app-muted)" }}>
                    Use friendly fields, then apply into the JSON manifest.
                  </Typography>
                  ) : null}

                  {advancedJsonOpen ? (
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
                  ) : null}
                </CardContent>
              </Card>

              {isOpenAPIStartingPoint ? (
              <Card
                variant="outlined"
                sx={{
                  bgcolor: "var(--app-surface)",
                  borderColor: "var(--app-accent)",
                  boxShadow: "0 20px 60px rgba(37, 99, 235, 0.08)",
                }}
              >
                <CardContent sx={{ p: 2.25 }}>
                  <Box
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 1,
                      alignItems: "center",
                    }}
                  >
                    <Typography sx={{ fontWeight: 850, color: "var(--app-fg)" }}>
                      REST / OpenAPI helper
                    </Typography>
                    <Chip
                      size="small"
                      label="Primary form for OpenAPI"
                      sx={{
                        bgcolor: "var(--app-control-active-bg)",
                        color: "var(--app-muted)",
                        fontWeight: 800,
                      }}
                    />
                  </Box>
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
              ) : null}

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
