"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  FormControlLabel,
  IconButton,
  Step,
  StepLabel,
  Stepper,
  Tooltip,
  TextField,
  Typography,
} from "@mui/material";

// ── Wire-format types (mirroring purecipher.curation outputs) ────

interface UpstreamPreview {
  upstream_ref: {
    channel: string;
    identifier: string;
    version: string;
    pinned_hash: string;
    source_url: string;
    metadata: Record<string, unknown>;
  };
  suggested_tool_name: string;
  suggested_display_name: string;
  notes: string[];
}

interface CapabilityTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  tags: string[];
}

interface CapabilityResource {
  uri: string;
  name: string;
  description: string;
  mime_type: string;
}

interface CapabilityPrompt {
  name: string;
  description: string;
}

interface IntrospectionResult {
  upstream_ref: UpstreamPreview["upstream_ref"];
  tool_count: number;
  resource_count: number;
  prompt_count: number;
  duration_ms: number;
  tools: CapabilityTool[];
  resources: CapabilityResource[];
  prompts: CapabilityPrompt[];
}

interface PermissionSuggestion {
  scope: string;
  rationale: string;
  evidence: string[];
  selected: boolean;
}

interface ManifestDraft {
  upstream_ref: UpstreamPreview["upstream_ref"];
  suggested_tool_name: string;
  suggested_display_name: string;
  suggested_description: string;
  permission_suggestions: PermissionSuggestion[];
  observed_tool_names: string[];
}

interface IntrospectResponse {
  introspection: IntrospectionResult;
  draft: ManifestDraft;
}

interface SubmitResponse {
  accepted: boolean;
  listing?: { tool_name: string; listing_id: string };
  manifest_digest?: string;
  introspection?: { tool_count: number };
  status?: number;
  error?: string;
}

const STEPS = [
  "Upstream",
  "Introspect",
  "Confirm permissions",
  "Submit",
] as const;

type WizardStep = 0 | 1 | 2 | 3;

// ── Iter 14.8 — token-on-introspect ──────────────────────────────
//
// Some upstream MCP servers (Stripe, Slack, GitHub, Linear, Notion,
// Atlassian, Sentry, etc.) refuse to start — or return zero tools —
// without a credential in their environment. To unblock the curator,
// Step 2 surfaces an optional credential editor: name/value pairs
// that the registry passes through to the spawn one time, then drops
// from process memory. Nothing is persisted server-side; the curator
// is told this verbatim on the panel.
//
// CredentialEntry models a single row in that editor. ``masked``
// controls whether the field renders as a password input — defaults
// to true (most credentials are tokens) and the curator can flip it
// per row to verify a paste.

interface CredentialEntry {
  /** Stable id so React's keyed renders survive add/remove. */
  id: string;
  /** Env var name. Validated server-side against ``[A-Z_][A-Z0-9_]*``. */
  key: string;
  /** Token value. Never logged; never persisted. */
  value: string;
  /** Whether the value field renders as a password input. */
  masked: boolean;
}

let _credentialIdCounter = 0;
function nextCredentialId(): string {
  _credentialIdCounter += 1;
  return `cred-${_credentialIdCounter}`;
}

function newBlankCredential(key = ""): CredentialEntry {
  return {
    id: nextCredentialId(),
    key,
    value: "",
    masked: true,
  };
}

/**
 * Hint map — when the curator's upstream identifier matches one of
 * these substrings, we pre-seed the credential editor with the
 * ``ENV_VAR`` name(s) the upstream's README documents.
 *
 * The match runs against the lower-cased identifier
 * (``preview.upstream_ref.identifier``). A single upstream can
 * declare multiple env vars (e.g. AWS uses three).
 *
 * This is a *suggestion only* — the curator can edit, remove, or
 * supplement any entry. The intent is to spare them a trip to the
 * upstream's README for the common cases.
 */
const CREDENTIAL_HINTS: ReadonlyArray<{
  match: (id: string) => boolean;
  label: string;
  keys: string[];
}> = [
  {
    match: (id) => id.includes("github"),
    label: "GitHub MCP server",
    keys: ["GITHUB_PERSONAL_ACCESS_TOKEN"],
  },
  {
    match: (id) => id.includes("stripe"),
    label: "Stripe MCP server",
    keys: ["STRIPE_SECRET_KEY"],
  },
  {
    match: (id) => id.includes("slack"),
    label: "Slack MCP server",
    keys: ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
  },
  {
    match: (id) => id.includes("linear"),
    label: "Linear MCP server",
    keys: ["LINEAR_API_KEY"],
  },
  {
    match: (id) => id.includes("notion"),
    label: "Notion MCP server",
    keys: ["NOTION_API_KEY"],
  },
  {
    match: (id) => id.includes("sentry"),
    label: "Sentry MCP server",
    keys: ["SENTRY_AUTH_TOKEN"],
  },
  {
    // ``mcp-atlassian`` (PyPI) and the Docker mirror both read
    // product-specific env vars rather than a single ATLASSIAN_*
    // pair. URL is the workspace base (``https://x.atlassian.net``
    // or ``https://x.atlassian.net/wiki`` for Confluence), USERNAME
    // is the Atlassian account email, API_TOKEN is generated at
    // id.atlassian.com/manage-profile/security/api-tokens.
    match: (id) =>
      id.includes("atlassian") ||
      id.includes("jira") ||
      id.includes("confluence"),
    label: "Atlassian (mcp-atlassian: Jira + Confluence)",
    keys: [
      "JIRA_URL",
      "JIRA_USERNAME",
      "JIRA_API_TOKEN",
      "CONFLUENCE_URL",
      "CONFLUENCE_USERNAME",
      "CONFLUENCE_API_TOKEN",
    ],
  },
  {
    match: (id) => id.includes("postgres"),
    label: "Postgres MCP server",
    keys: ["DATABASE_URL"],
  },
  {
    match: (id) => id.includes("openai"),
    label: "OpenAI-backed MCP server",
    keys: ["OPENAI_API_KEY"],
  },
  {
    match: (id) => id.includes("anthropic"),
    label: "Anthropic-backed MCP server",
    keys: ["ANTHROPIC_API_KEY"],
  },
  {
    match: (id) => id.includes("aws") || id.startsWith("amazon"),
    label: "AWS MCP server",
    keys: [
      "AWS_ACCESS_KEY_ID",
      "AWS_SECRET_ACCESS_KEY",
      "AWS_REGION",
    ],
  },
];

/**
 * Match the upstream's identifier against the hint table and return
 * the first applicable suggestion's env-var names, or an empty list
 * if no hint fires.
 */
function suggestCredentialKeys(
  preview: UpstreamPreview | null,
): { label: string; keys: string[] } | null {
  if (!preview) return null;
  const id = preview.upstream_ref.identifier.toLowerCase();
  for (const hint of CREDENTIAL_HINTS) {
    if (hint.match(id)) return { label: hint.label, keys: hint.keys };
  }
  return null;
}

/**
 * Strip blank-and-empty rows and translate the editor state into
 * the wire-format ``env`` dict the registry expects. Returns
 * ``undefined`` when no usable credentials were entered, which lets
 * us omit the field entirely so the backend can take the no-env path.
 */
function credentialsToEnv(
  entries: CredentialEntry[],
): Record<string, string> | undefined {
  const out: Record<string, string> = {};
  for (const entry of entries) {
    const key = entry.key.trim();
    if (!key || !entry.value) continue;
    out[key] = entry.value;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

export function OnboardWizard({ mode = "curator" }: { mode?: "author" | "curator" }) {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: upstream URL + resolved preview
  const [upstreamUrl, setUpstreamUrl] = useState("");
  const [preview, setPreview] = useState<UpstreamPreview | null>(null);

  // Step 2: introspection result + draft
  const [intro, setIntro] = useState<IntrospectionResult | null>(null);
  const [draft, setDraft] = useState<ManifestDraft | null>(null);

  // Iter 14.8 — token-on-introspect. One-shot credentials passed at
  // the introspect step. Cleared on successful introspection (the
  // values served their purpose) and on resetWizard. Values are never
  // persisted server-side; see CREDENTIAL_HINTS for the seeded keys.
  const [credentials, setCredentials] = useState<CredentialEntry[]>([]);

  // Iter 14.10 — tool selection. The curator picks which observed
  // tools they're vouching for. Defaults to all observed; the wizard
  // re-seeds this whenever introspection returns a new tool list.
  // Stored as a Set for O(1) membership checks during render.
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());

  // Step 3: curator overrides
  const [toolName, setToolName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [version, setVersion] = useState("0.1.0");
  const [description, setDescription] = useState("");
  const [selections, setSelections] = useState<PermissionSuggestion[]>([]);
  const [hostingMode, setHostingMode] = useState<"catalog" | "proxy">(
    "catalog",
  );
  // Iter 15 — opt-in consent/contract enforcement. Only meaningful
  // when hosting_mode === "proxy"; the submit payload sends them
  // regardless (the backend ignores them in catalog mode) so the
  // curator's intent is preserved if they toggle back and forth.
  const [requireConsent, setRequireConsent] = useState(false);
  const [requireContract, setRequireContract] = useState(false);

  // Step 4: result
  const [submitResult, setSubmitResult] = useState<SubmitResponse | null>(null);

  /**
   * Reset every piece of wizard state back to the initial step.
   *
   * Used by "Onboard another" on the success screen. ``router.refresh()``
   * alone doesn't reset client component state, so we explicitly clear
   * everything before letting the user pick a new upstream.
   */
  const resetWizard = useCallback(() => {
    setStep(0);
    setBusy(false);
    setError(null);
    setUpstreamUrl("");
    setPreview(null);
    setIntro(null);
    setDraft(null);
    setCredentials([]);
    setSelectedTools(new Set());
    setToolName("");
    setDisplayName("");
    setVersion("0.1.0");
    setDescription("");
    setSelections([]);
    setHostingMode("catalog");
    setRequireConsent(false);
    setRequireContract(false);
    setSubmitResult(null);
  }, []);

  /**
   * Step the wizard backward, clearing any error banner from the step
   * we're leaving so a stale message doesn't carry into the prior step.
   */
  const goBackTo = useCallback((target: WizardStep) => {
    setError(null);
    setStep(target);
  }, []);

  // ── Step transitions ─────────────────────────────────────────

  const handleResolve = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const response = await fetch("/api/curate/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upstream: upstreamUrl }),
      });
      const payload = await response.json();
      if (!response.ok) {
        setError(payload?.error ?? "Couldn't resolve that upstream.");
        return;
      }
      const resolved: UpstreamPreview = payload.preview;
      setPreview(resolved);
      setToolName(resolved.suggested_tool_name);
      setDisplayName(resolved.suggested_display_name);
      setStep(1);
    } catch {
      setError("Network error talking to the registry.");
    } finally {
      setBusy(false);
    }
  }, [upstreamUrl]);

  const handleIntrospect = useCallback(async () => {
    setError(null);
    setBusy(true);
    // Iter 14.8 — gather one-shot credentials. ``env`` is included
    // only when the curator filled in at least one key/value row;
    // otherwise we omit it so the backend takes the no-env path.
    const env = credentialsToEnv(credentials);
    try {
      const response = await fetch("/api/curate/introspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upstream: upstreamUrl,
          ...(env ? { env } : {}),
        }),
      });
      const payload = (await response.json()) as IntrospectResponse | {
        error?: string;
      };
      if (!response.ok || !("introspection" in payload)) {
        setError(
          (payload as { error?: string }).error ??
            "Couldn't introspect the upstream.",
        );
        return;
      }
      // Refuse to advance when the upstream surface is empty — the
      // server-side submit handler returns 422 on the same condition,
      // so we'd be setting the curator up for a dead end. Tell them
      // here so they can fix it before filling out step 3.
      const i = payload.introspection;
      if (i.tool_count === 0 && i.resource_count === 0 && i.prompt_count === 0) {
        setError(
          "The upstream exposed zero tools, resources, or prompts. " +
            "It may require authentication the registry doesn't have, " +
            "or it may not be an MCP server. Vouch for an upstream with " +
            "an observable surface.",
        );
        return;
      }
      setIntro(payload.introspection);
      setDraft(payload.draft);
      setSelections(payload.draft.permission_suggestions);
      setDescription(payload.draft.suggested_description);
      // Iter 14.10 — default to vouching for all observed tools.
      // The curator can deselect on Step 3 via the ToolSelector.
      setSelectedTools(
        new Set(payload.introspection.tools.map((t) => t.name)),
      );
      // Iter 14.8.1 — keep credentials in client state through Step
      // 3 so we can re-send them with the submit POST. The submit
      // handler re-introspects (a tamper defence) and that
      // re-introspect needs the same env. We clear right after the
      // submit succeeds — see ``handleSubmit`` below. On submit
      // failure we keep them too, so the curator can fix tool name /
      // permissions and retry without re-typing the token.
      setStep(2);
    } catch {
      setError("Network error during introspection.");
    } finally {
      setBusy(false);
    }
  }, [upstreamUrl, credentials]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setBusy(true);
    // Iter 14.8.1 — re-attach env at submit time. The backend submit
    // handler re-introspects as a tamper defence; for token-required
    // upstreams that re-introspect needs the same env the curator
    // supplied at Step 2. We send only the populated rows.
    const env = credentialsToEnv(credentials);
    try {
      const response = await fetch("/api/curate/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upstream: upstreamUrl,
          tool_name: toolName,
          display_name: displayName,
          version,
          description,
          hosting_mode: hostingMode,
          attestation_kind: mode,
          selected_permissions: selections.map((s) => ({
            scope: s.scope,
            selected: s.selected,
          })),
          // Iter 14.10 — vouched tool subset. Sent as an array of
          // names; the backend filters to observed and rejects empty.
          selected_tools: Array.from(selectedTools),
          // Iter 15 — opt-in enforcement flags. No-op in catalog mode.
          require_consent: hostingMode === "proxy" ? requireConsent : false,
          require_contract: hostingMode === "proxy" ? requireContract : false,
          ...(env ? { env } : {}),
        }),
      });
      const payload = (await response.json()) as SubmitResponse;
      if (!response.ok || payload.error) {
        // Submit failed — keep credentials in state so the curator
        // can fix the underlying issue (typo'd tool name, etc.) and
        // retry without re-typing the token.
        setError(payload.error ?? "Submission failed.");
        return;
      }
      // Submit succeeded — the listing is now persisted with the
      // curator's vouch. The credentials were used for the final
      // re-introspect and are no longer needed; drop them now so
      // they don't linger in client state past the success screen.
      setCredentials([]);
      setSubmitResult(payload);
      setStep(3);
    } catch {
      setError("Network error during submission.");
    } finally {
      setBusy(false);
    }
  }, [
    upstreamUrl,
    toolName,
    displayName,
    version,
    description,
    selections,
    hostingMode,
    requireConsent,
    requireContract,
    credentials,
    selectedTools,
  ]);

  const togglePermission = useCallback((scope: string) => {
    setSelections((prev) =>
      prev.map((s) =>
        s.scope === scope ? { ...s, selected: !s.selected } : s,
      ),
    );
  }, []);

  // ── Render ──────────────────────────────────────────────────

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Stepper activeStep={step} sx={{ mb: 1 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error ? (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      ) : null}

      {step === 0 ? (
        <StepUpstream
          upstreamUrl={upstreamUrl}
          setUpstreamUrl={setUpstreamUrl}
          busy={busy}
          onResolve={handleResolve}
        />
      ) : null}

      {step === 1 && preview ? (
        <StepIntrospect
          preview={preview}
          busy={busy}
          credentials={credentials}
          setCredentials={setCredentials}
          onBack={() => goBackTo(0)}
          onIntrospect={handleIntrospect}
        />
      ) : null}

      {step === 2 && intro && draft && preview ? (
        <StepConfirm
          intro={intro}
          preview={preview}
          selections={selections}
          toolName={toolName}
          setToolName={setToolName}
          displayName={displayName}
          setDisplayName={setDisplayName}
          version={version}
          setVersion={setVersion}
          description={description}
          setDescription={setDescription}
          hostingMode={hostingMode}
          setHostingMode={setHostingMode}
          requireConsent={requireConsent}
          setRequireConsent={setRequireConsent}
          requireContract={requireContract}
          setRequireContract={setRequireContract}
          onTogglePermission={togglePermission}
          selectedTools={selectedTools}
          setSelectedTools={setSelectedTools}
          busy={busy}
          onBack={() => goBackTo(1)}
          onSubmit={handleSubmit}
          mode={mode}
        />
      ) : null}

      {step === 3 && submitResult ? (
        <StepDone result={submitResult} router={router} onReset={resetWizard} mode={mode} />
      ) : null}
    </Box>
  );
}

// ── Step 1 ────────────────────────────────────────────────────

function StepUpstream({
  upstreamUrl,
  setUpstreamUrl,
  busy,
  onResolve,
}: {
  upstreamUrl: string;
  setUpstreamUrl: (v: string) => void;
  busy: boolean;
  onResolve: () => void;
}) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography sx={{ fontWeight: 800, mb: 1, color: "var(--app-fg)" }}>
          Step 1 · Upstream
        </Typography>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 14, mb: 2 }}>
          Paste the upstream MCP server you want to vouch for. Four
          shapes are accepted:
        </Typography>
        <Box
          component="ul"
          sx={{
            mt: 0,
            mb: 2,
            pl: 3,
            color: "var(--app-muted)",
            fontSize: 13,
            "& li": { mb: 0.5 },
            "& code": {
              fontFamily:
                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 12,
              padding: "1px 4px",
              borderRadius: 1,
              bgcolor: "var(--app-control-bg)",
              border: "1px solid var(--app-border)",
            },
          }}
        >
          <li>
            <strong>HTTP/SSE</strong>: <code>https://mcp.example.com/sse</code>
          </li>
          <li>
            <strong>PyPI package</strong>: <code>pypi:markitdown-mcp@1.2.3</code>
          </li>
          <li>
            <strong>npm package</strong>:{" "}
            <code>npm:@modelcontextprotocol/server-everything@0.5.0</code>
          </li>
          <li>
            <strong>Docker / OCI image</strong>:{" "}
            <code>docker:ghcr.io/example/mcp@sha256:…</code>
          </li>
        </Box>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 12, mb: 2 }}>
          PyPI / npm / Docker upstreams need{" "}
          <code>uvx</code> / <code>npx</code> / <code>docker</code> on the
          registry server&apos;s PATH. The version (or digest) is optional
          — omit it to use the package&apos;s latest published version, or
          pin a digest for reproducible Docker curation.
        </Typography>
        <TextField
          fullWidth
          autoFocus
          label="Upstream MCP server"
          placeholder="https://mcp.example.com/sse  ·  pypi:pkg@1.0  ·  npm:pkg@1.0  ·  docker:image@sha256:…"
          value={upstreamUrl}
          onChange={(e) => setUpstreamUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy && upstreamUrl.trim()) onResolve();
          }}
          variant="outlined"
          size="medium"
        />
        <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 2 }}>
          <Button
            onClick={onResolve}
            disabled={busy || !upstreamUrl.trim()}
            variant="contained"
            sx={{
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)" },
              textTransform: "none",
              minWidth: 140,
            }}
          >
            {busy ? <CircularProgress size={18} /> : "Resolve"}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

// ── Step 2 ────────────────────────────────────────────────────

function StepIntrospect({
  preview,
  busy,
  credentials,
  setCredentials,
  onBack,
  onIntrospect,
}: {
  preview: UpstreamPreview;
  busy: boolean;
  credentials: CredentialEntry[];
  setCredentials: React.Dispatch<React.SetStateAction<CredentialEntry[]>>;
  onBack: () => void;
  onIntrospect: () => void;
}) {
  // Iter 14.8 — credential editor lives only on stdio channels.
  // For HTTP, the registry doesn't have a robust generic header
  // injection path (the wizard would have to know whether to send
  // ``Authorization: Bearer …``, ``X-Api-Key: …``, etc.), so we hide
  // the editor and tell the curator to bake auth into the URL.
  const channel = preview.upstream_ref.channel;
  const channelSupportsCredentials =
    channel === "pypi" || channel === "npm" || channel === "docker";

  // Match the upstream against the hint table once on mount and
  // pre-seed empty rows for each suggested env var. The curator can
  // edit / add / remove freely; this just saves them a trip to the
  // README for the common cases (Stripe, Slack, GitHub, etc.).
  const hint = useMemo(() => suggestCredentialKeys(preview), [preview]);
  useEffect(() => {
    if (!channelSupportsCredentials) return;
    if (credentials.length > 0) return;
    if (!hint || hint.keys.length === 0) return;
    setCredentials(hint.keys.map((k) => newBlankCredential(k)));
    // We deliberately seed only when the editor is empty so that if a
    // curator removes all rows we don't repopulate them on re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hint, channelSupportsCredentials]);

  const updateCredential = (id: string, patch: Partial<CredentialEntry>) => {
    setCredentials((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    );
  };
  const removeCredential = (id: string) => {
    setCredentials((prev) => prev.filter((c) => c.id !== id));
  };
  const addCredential = () => {
    setCredentials((prev) => [...prev, newBlankCredential()]);
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography sx={{ fontWeight: 800, mb: 1, color: "var(--app-fg)" }}>
          Step 2 · Introspect the upstream
        </Typography>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 14, mb: 2 }}>
          The registry connects to the upstream and lists its tools,
          resources, and prompts. This call may take up to 15 seconds
          while the server warms up.
        </Typography>
        <Box
          sx={{
            display: "grid",
            gap: 1.25,
            p: 2,
            bgcolor: "var(--app-control-bg)",
            border: "1px solid var(--app-border)",
            borderRadius: 2,
            mb: 2,
          }}
        >
          <Field label="Channel" value={preview.upstream_ref.channel} />
          <Field
            label={
              preview.upstream_ref.channel === "http"
                ? "URL"
                : preview.upstream_ref.channel === "docker"
                  ? "Image"
                  : "Package"
            }
            value={preview.upstream_ref.identifier}
          />
          {preview.upstream_ref.version ? (
            <Field
              label="Pinned version"
              value={preview.upstream_ref.version}
            />
          ) : null}
          {preview.upstream_ref.pinned_hash ? (
            <Field
              label="Integrity hash"
              value={preview.upstream_ref.pinned_hash}
            />
          ) : null}
          {preview.upstream_ref.source_url ? (
            <Field
              label="Source"
              value={preview.upstream_ref.source_url}
            />
          ) : null}
          <Field
            label="Suggested tool name"
            value={preview.suggested_tool_name}
          />
        </Box>
        {preview.notes.length > 0 ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            {preview.notes.map((n) => (
              <div key={n}>{n}</div>
            ))}
          </Alert>
        ) : null}

        {channelSupportsCredentials ? (
          <CredentialEditor
            credentials={credentials}
            hintLabel={hint?.label ?? null}
            onUpdate={updateCredential}
            onRemove={removeCredential}
            onAdd={addCredential}
          />
        ) : null}

        <Box sx={{ display: "flex", justifyContent: "space-between", mt: 1 }}>
          <Button onClick={onBack} variant="text">
            Back
          </Button>
          <Button
            onClick={onIntrospect}
            disabled={busy}
            variant="contained"
            sx={{
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)" },
              textTransform: "none",
              minWidth: 200,
            }}
          >
            {busy ? <CircularProgress size={18} /> : "Introspect upstream"}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

/**
 * Iter 14.8 — credential editor.
 *
 * Renders a compact key/value table for the optional ``env`` dict the
 * registry passes to the spawn at introspect time. Each row has:
 *
 * - A KEY field (text, env-var name).
 * - A VALUE field that renders as a password input by default, with a
 *   show/hide eye toggle so the curator can verify a paste before
 *   submitting.
 * - A remove button.
 *
 * Below the table is an "Add credential" button and a copy block
 * making the trust contract explicit: credentials are passed once,
 * never written to disk, never logged.
 */
function CredentialEditor({
  credentials,
  hintLabel,
  onUpdate,
  onRemove,
  onAdd,
}: {
  credentials: CredentialEntry[];
  hintLabel: string | null;
  onUpdate: (id: string, patch: Partial<CredentialEntry>) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
}) {
  return (
    <Box
      sx={{
        mb: 2,
        p: 2,
        border: "1px solid var(--app-border)",
        borderRadius: 2,
        bgcolor: "var(--app-surface)",
      }}
    >
      <Typography
        sx={{
          fontWeight: 700,
          fontSize: 12,
          color: "var(--app-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          mb: 0.5,
        }}
      >
        Credentials (optional)
      </Typography>
      <Typography sx={{ color: "var(--app-muted)", fontSize: 13, mb: 1.5 }}>
        Some upstream MCP servers (Stripe, Slack, GitHub, Linear, Notion,
        and similar) refuse to start, or return zero tools, until a token
        is in their environment. Add one row per env var the upstream
        documents.
      </Typography>
      {hintLabel ? (
        <Alert severity="info" sx={{ mb: 1.5, fontSize: 13 }}>
          Looks like a <strong>{hintLabel}</strong> — pre-seeded the
          common env var name(s). Edit, remove, or add rows as needed.
        </Alert>
      ) : null}

      {credentials.length > 0 ? (
        <Box sx={{ display: "grid", gap: 1, mb: 1 }}>
          {credentials.map((entry) => (
            <Box
              key={entry.id}
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr auto auto" },
                gap: 1,
                alignItems: "center",
              }}
            >
              <TextField
                size="small"
                placeholder="GITHUB_PERSONAL_ACCESS_TOKEN"
                value={entry.key}
                onChange={(e) =>
                  onUpdate(entry.id, { key: e.target.value })
                }
                slotProps={{
                  htmlInput: {
                    style: {
                      fontFamily:
                        "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 12,
                    },
                  },
                }}
              />
              <TextField
                size="small"
                type={entry.masked ? "password" : "text"}
                placeholder="value"
                value={entry.value}
                onChange={(e) =>
                  onUpdate(entry.id, { value: e.target.value })
                }
                autoComplete="off"
                slotProps={{
                  htmlInput: {
                    style: {
                      fontFamily:
                        "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 12,
                    },
                    // Help password managers stay out of token fields
                    // — they tend to autofill the curator's own
                    // credentials, which is a real footgun here.
                    "data-1p-ignore": "true",
                    "data-lpignore": "true",
                  },
                }}
              />
              <Tooltip title={entry.masked ? "Show value" : "Hide value"}>
                <IconButton
                  size="small"
                  onClick={() =>
                    onUpdate(entry.id, { masked: !entry.masked })
                  }
                  aria-label={entry.masked ? "Show value" : "Hide value"}
                >
                  {entry.masked ? (
                    /* Eye icon — minimal inline SVG to avoid a new
                       icon library import for a single use. */
                    <Box
                      component="svg"
                      width={16}
                      height={16}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx={12} cy={12} r={3} />
                    </Box>
                  ) : (
                    /* Eye-off icon */
                    <Box
                      component="svg"
                      width={16}
                      height={16}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                      <line x1={1} y1={1} x2={23} y2={23} />
                    </Box>
                  )}
                </IconButton>
              </Tooltip>
              <Tooltip title="Remove">
                <IconButton
                  size="small"
                  onClick={() => onRemove(entry.id)}
                  aria-label="Remove credential"
                >
                  <Box
                    component="svg"
                    width={16}
                    height={16}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1={18} y1={6} x2={6} y2={18} />
                    <line x1={6} y1={6} x2={18} y2={18} />
                  </Box>
                </IconButton>
              </Tooltip>
            </Box>
          ))}
        </Box>
      ) : null}

      <Button
        onClick={onAdd}
        size="small"
        variant="text"
        sx={{ textTransform: "none", mb: 1 }}
      >
        + Add credential
      </Button>

      <Typography
        sx={{
          fontSize: 11,
          color: "var(--app-muted)",
          fontStyle: "italic",
          lineHeight: 1.5,
        }}
      >
        Credentials are passed to the upstream once, only to introspect
        its tools. The registry never writes them to disk, never includes
        them in the published manifest, and never logs the values.
      </Typography>
    </Box>
  );
}

// ── Step 3 ────────────────────────────────────────────────────

function StepConfirm({
  intro,
  preview,
  selections,
  toolName,
  setToolName,
  displayName,
  setDisplayName,
  version,
  setVersion,
  description,
  setDescription,
  hostingMode,
  setHostingMode,
  requireConsent,
  setRequireConsent,
  requireContract,
  setRequireContract,
  onTogglePermission,
  selectedTools,
  setSelectedTools,
  busy,
  onBack,
  onSubmit,
  mode = "curator",
}: {
  intro: IntrospectionResult;
  preview: UpstreamPreview;
  selections: PermissionSuggestion[];
  toolName: string;
  setToolName: (v: string) => void;
  displayName: string;
  setDisplayName: (v: string) => void;
  version: string;
  setVersion: (v: string) => void;
  description: string;
  setDescription: (v: string) => void;
  hostingMode: "catalog" | "proxy";
  setHostingMode: (v: "catalog" | "proxy") => void;
  requireConsent: boolean;
  setRequireConsent: (v: boolean) => void;
  requireContract: boolean;
  setRequireContract: (v: boolean) => void;
  onTogglePermission: (scope: string) => void;
  selectedTools: Set<string>;
  setSelectedTools: React.Dispatch<React.SetStateAction<Set<string>>>;
  busy: boolean;
  onBack: () => void;
  onSubmit: () => void;
  mode?: "author" | "curator";
}) {
  // Proxy mode is supported for HTTP, PyPI, npm, and Docker upstreams.
  // The stdio channels run a fresh subprocess per session via
  // uvx/npx/docker run; surface that operational characteristic on
  // the card so the curator knows what they're signing up for.
  const channel = preview.upstream_ref.channel;
  const proxyNoteByChannel: Record<string, string> = {
    pypi: "For PyPI upstreams, the registry spawns one uvx subprocess per session. First launch may take 10–30s while the package is downloaded; later sessions reuse the cache.",
    npm: "For npm upstreams, the registry spawns one npx subprocess per session. First launch may take 10–30s while the package is downloaded; later sessions reuse the cache.",
    docker: "For Docker upstreams, the registry runs a fresh container per session via docker run --rm -i (with --memory=512m and --pids-limit=128). First launch may take 30s–2min while the image is pulled; later sessions reuse the cached image.",
  };
  const proxyNote = proxyNoteByChannel[channel];
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography sx={{ fontWeight: 800, mb: 1, color: "var(--app-fg)" }}>
          Step 3 · Confirm what you&apos;re vouching for
        </Typography>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 14, mb: 2 }}>
          The registry observed{" "}
          <strong>{intro.tool_count}</strong> tool(s),{" "}
          <strong>{intro.resource_count}</strong> resource(s), and{" "}
          <strong>{intro.prompt_count}</strong> prompt(s). Confirm or
          remove permissions below — you cannot add scopes the registry
          didn&apos;t observe.
        </Typography>

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
            mb: 3,
          }}
        >
          <TextField
            label="Tool name"
            value={toolName}
            onChange={(e) => setToolName(e.target.value)}
            size="small"
          />
          <TextField
            label="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            size="small"
          />
          <TextField
            label="Version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            size="small"
          />
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            size="small"
            multiline
            minRows={2}
          />
        </Box>

        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 12,
            color: "var(--app-muted)",
            mb: 1,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Permissions vouched for ({selections.filter((s) => s.selected).length} of {selections.length})
        </Typography>
        {selections.length === 0 ? (
          <Alert severity="warning" sx={{ mb: 2 }}>
            The registry didn&apos;t suggest any permissions. The
            resulting listing will declare only the implicit
            call_tool scope.
          </Alert>
        ) : (
          <Box sx={{ display: "grid", gap: 1, mb: 3 }}>
            {selections.map((s) => (
              <Box
                key={s.scope}
                sx={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: 1.25,
                  alignItems: "flex-start",
                  p: 1.5,
                  border: "1px solid var(--app-border)",
                  borderRadius: 2,
                  bgcolor: s.selected
                    ? "var(--app-control-bg)"
                    : "transparent",
                }}
              >
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={s.selected}
                      onChange={() => onTogglePermission(s.scope)}
                    />
                  }
                  label=""
                />
                <Box>
                  <Typography
                    sx={{
                      fontWeight: 700,
                      fontFamily:
                        "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 13,
                      color: "var(--app-fg)",
                    }}
                  >
                    {s.scope}
                  </Typography>
                  <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                    {s.rationale}
                  </Typography>
                  {s.evidence.length > 0 ? (
                    <Box sx={{ mt: 0.75, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                      {s.evidence.slice(0, 4).map((ev) => (
                        <Chip
                          key={ev}
                          size="small"
                          label={ev}
                          sx={{ fontSize: 10 }}
                        />
                      ))}
                    </Box>
                  ) : null}
                </Box>
              </Box>
            ))}
          </Box>
        )}

        {intro.tools.length > 0 ? (
          <ToolSelector
            tools={intro.tools}
            selectedTools={selectedTools}
            setSelectedTools={setSelectedTools}
          />
        ) : null}

        {/* Hosting-mode chooser. Curator picks whether the registry
            simply lists the upstream (catalog) or hosts a SecureMCP-
            enforced gateway in front of it (proxy). */}
        <Box sx={{ mb: 3 }}>
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: 12,
              color: "var(--app-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              mb: 1,
            }}
          >
            Hosting mode
          </Typography>
          <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
            <HostingModeOption
              selected={hostingMode === "catalog"}
              title="Catalog-only"
              body={
                <>
                  Listing publishes a signed third-party attestation.
                  Install recipes point at the upstream{" "}
                  <strong>directly</strong>.
                </>
              }
              onClick={() => setHostingMode("catalog")}
              disabled={false}
            />
            <HostingModeOption
              selected={hostingMode === "proxy"}
              title="Host as SecureMCP"
              body={
                <>
                  Registry mounts a SecureMCP gateway in front of the
                  upstream. Calls are bound by an{" "}
                  <strong>allowlist policy</strong> built from the
                  curator-vouched tools and recorded in the provenance
                  ledger.
                </>
              }
              onClick={() => setHostingMode("proxy")}
              disabled={false}
              note={proxyNote}
            />
          </Box>
        </Box>

        {hostingMode === "proxy" ? (
          <Box sx={{ mb: 3 }}>
            <Typography
              sx={{
                fontWeight: 700,
                fontSize: 12,
                color: "var(--app-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                mb: 1,
              }}
            >
              Runtime gating (optional)
            </Typography>
            <Box
              sx={{
                display: "grid",
                gap: 0.5,
                p: 1.75,
                border: "1px solid var(--app-border)",
                borderRadius: 2,
                bgcolor: "var(--app-surface)",
              }}
            >
              <FormControlLabel
                control={
                  <Checkbox
                    checked={requireConsent}
                    onChange={(e) => setRequireConsent(e.target.checked)}
                  />
                }
                label={
                  <Box>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: "var(--app-fg)" }}>
                      Require consent grant before every tool call
                    </Typography>
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      Callers must have a matching edge in the consent
                      graph (issue via <code>/security/consent/grant</code>)
                      or the proxy denies the call.
                    </Typography>
                  </Box>
                }
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={requireContract}
                    onChange={(e) => setRequireContract(e.target.checked)}
                  />
                }
                label={
                  <Box>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: "var(--app-fg)" }}>
                      Require an active contract with the registry
                    </Typography>
                    <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
                      Callers must have negotiated a contract via{" "}
                      <code>/security/contracts/negotiate</code> before
                      the proxy forwards calls.
                    </Typography>
                  </Box>
                }
              />
            </Box>
          </Box>
        ) : null}

        <Box sx={{ display: "flex", justifyContent: "space-between" }}>
          <Button onClick={onBack} variant="text">
            Back
          </Button>
          <Button
            onClick={onSubmit}
            disabled={busy || !toolName.trim() || selectedTools.size === 0}
            variant="contained"
            sx={{
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)" },
              textTransform: "none",
              minWidth: 200,
            }}
          >
            {busy ? <CircularProgress size={18} /> : mode === "author" ? "Submit author listing" : "Submit curated listing"}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

// ── Step 4 ────────────────────────────────────────────────────

function StepDone({
  result,
  router,
  onReset,
  mode = "curator",
}: {
  result: SubmitResponse;
  router: ReturnType<typeof useRouter>;
  onReset: () => void;
  mode?: "author" | "curator";
}) {
  const listingName = result.listing?.tool_name ?? "your listing";
  return (
    <Card variant="outlined">
      <CardContent>
        <Alert severity="success" sx={{ mb: 2 }}>
          {mode === "author" ? "Author listing submitted for review." : "Curated listing submitted for review."}
        </Alert>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 14, mb: 2 }}>
          <strong>{listingName}</strong> was published as
          {mode === "author"
            ? " an author-attested listing."
            : " a curator-attested listing."}{" "}
          A reviewer will approve or reject it before it appears in
          the public catalog.
        </Typography>
        <Box sx={{ display: "flex", gap: 1.25 }}>
          <Link
            href={`/registry/listings/${encodeURIComponent(listingName)}`}
            style={{ textDecoration: "none" }}
          >
            <Button variant="contained" sx={{ textTransform: "none" }}>
              View listing
            </Button>
          </Link>
          <Button
            onClick={() => {
              onReset();
              router.refresh();
            }}
            variant="text"
          >
            Onboard another
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}

// ── Tool selector (Iter 14.10) ────────────────────────────────

/**
 * Single component that scales gracefully from 1 to ~200 tools.
 *
 * Behavior tiers, all in one layout (no mode switching that the
 * curator has to learn):
 *
 * - Always visible: count badge ("X of Y selected"), Select All /
 *   None / Invert buttons.
 * - When >15 tools: a search input that live-filters by name and
 *   description.
 * - The list is a fixed-height scroll container so 49 Atlassian
 *   tools and 4 filesystem tools both render predictably; rows are
 *   single-line (name in mono + description as secondary text) so
 *   roughly 8 fit at once.
 *
 * The "vouching for X of Y" framing makes the security model
 * legible: this is the surface the curator is putting their
 * signature on, not a passive display of what was observed.
 */
function ToolSelector({
  tools,
  selectedTools,
  setSelectedTools,
}: {
  tools: CapabilityTool[];
  selectedTools: Set<string>;
  setSelectedTools: React.Dispatch<React.SetStateAction<Set<string>>>;
}) {
  const [filter, setFilter] = useState("");

  const total = tools.length;
  const selectedCount = selectedTools.size;
  const showSearch = total > 15;

  // Filter is case-insensitive, matches name OR description.
  const visibleTools = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return tools;
    return tools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description ?? "").toLowerCase().includes(q),
    );
  }, [tools, filter]);

  const toggle = (name: string) => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedTools(new Set(tools.map((t) => t.name)));
  };
  const selectNone = () => {
    setSelectedTools(new Set());
  };
  const invert = () => {
    setSelectedTools((prev) => {
      const next = new Set<string>();
      for (const t of tools) if (!prev.has(t.name)) next.add(t.name);
      return next;
    });
  };

  // Apply select-all/none/invert *to the filtered subset* when a
  // search term is active. This is the action curators actually want
  // when they've narrowed to "delete*" tools and want to remove all
  // of them at once.
  const filterIsActive = filter.trim().length > 0;
  const selectAllVisible = () => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      for (const t of visibleTools) next.add(t.name);
      return next;
    });
  };
  const selectNoneVisible = () => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      for (const t of visibleTools) next.delete(t.name);
      return next;
    });
  };

  return (
    <Box sx={{ mb: 3 }}>
      <Box
        sx={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          mb: 1,
          gap: 2,
          flexWrap: "wrap",
        }}
      >
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 12,
            color: "var(--app-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Tools to vouch for ({selectedCount} of {total} selected)
        </Typography>
        <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
          <Button
            size="small"
            variant="text"
            onClick={filterIsActive ? selectAllVisible : selectAll}
            sx={{ textTransform: "none", fontSize: 12, minWidth: 0 }}
          >
            {filterIsActive ? "Select visible" : "Select all"}
          </Button>
          <Button
            size="small"
            variant="text"
            onClick={filterIsActive ? selectNoneVisible : selectNone}
            sx={{ textTransform: "none", fontSize: 12, minWidth: 0 }}
          >
            {filterIsActive ? "Deselect visible" : "Select none"}
          </Button>
          {!filterIsActive ? (
            <Button
              size="small"
              variant="text"
              onClick={invert}
              sx={{ textTransform: "none", fontSize: 12, minWidth: 0 }}
            >
              Invert
            </Button>
          ) : null}
        </Box>
      </Box>

      {showSearch ? (
        <TextField
          fullWidth
          size="small"
          placeholder={`Filter ${total} tools by name or description…`}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          sx={{ mb: 1 }}
        />
      ) : null}

      {selectedCount === 0 ? (
        <Alert severity="warning" sx={{ mb: 1, fontSize: 13 }}>
          No tools selected. A listing must include
          for at least one tool — submit will be blocked until you
          select one.
        </Alert>
      ) : null}

      <Box
        sx={{
          border: "1px solid var(--app-border)",
          borderRadius: 2,
          maxHeight: 360,
          overflowY: "auto",
          bgcolor: "var(--app-surface)",
        }}
      >
        {visibleTools.length === 0 ? (
          <Box sx={{ p: 2 }}>
            <Typography sx={{ color: "var(--app-muted)", fontSize: 13 }}>
              No tools match {`"${filter}"`}.
            </Typography>
          </Box>
        ) : (
          visibleTools.map((tool, idx) => {
            const isSelected = selectedTools.has(tool.name);
            return (
              <Box
                key={tool.name}
                onClick={() => toggle(tool.name)}
                sx={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr",
                  gap: 1.25,
                  alignItems: "flex-start",
                  px: 1.5,
                  py: 0.875,
                  borderBottom:
                    idx < visibleTools.length - 1
                      ? "1px solid var(--app-border)"
                      : "none",
                  bgcolor: isSelected
                    ? "var(--app-control-bg)"
                    : "transparent",
                  cursor: "pointer",
                  transition: "background-color 80ms ease",
                  "&:hover": {
                    bgcolor: isSelected
                      ? "var(--app-control-active-bg)"
                      : "var(--app-control-bg)",
                  },
                }}
              >
                <Checkbox
                  checked={isSelected}
                  onChange={() => toggle(tool.name)}
                  onClick={(e) => e.stopPropagation()}
                  size="small"
                  sx={{ p: 0.25 }}
                />
                <Box sx={{ minWidth: 0 }}>
                  <Typography
                    sx={{
                      fontFamily:
                        "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 12.5,
                      fontWeight: 600,
                      color: "var(--app-fg)",
                      wordBreak: "break-word",
                    }}
                  >
                    {tool.name}
                  </Typography>
                  {tool.description ? (
                    <Typography
                      sx={{
                        fontSize: 12,
                        color: "var(--app-muted)",
                        lineHeight: 1.4,
                        // Truncate to 2 lines so dense rows stay
                        // scannable even when descriptions are long.
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {tool.description}
                    </Typography>
                  ) : null}
                </Box>
              </Box>
            );
          })
        )}
      </Box>

      <Typography
        sx={{
          mt: 0.75,
          fontSize: 11,
          color: "var(--app-muted)",
          fontStyle: "italic",
          lineHeight: 1.5,
        }}
      >
        In proxy hosting mode, deselected tools are blocked at the
        gateway — calls are rejected before reaching the upstream.
        In catalog mode, the listing&apos;s attestation describes
        only the vouched subset.
      </Typography>
    </Box>
  );
}

// ── Helpers ───────────────────────────────────────────────────

function HostingModeOption({
  selected,
  title,
  body,
  onClick,
  disabled,
  note,
}: {
  selected: boolean;
  title: string;
  body: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
  note?: string;
}) {
  return (
    <Box
      onClick={disabled ? undefined : onClick}
      sx={{
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.55 : 1,
        p: 1.75,
        borderRadius: 2,
        border: "1px solid",
        borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
        bgcolor: selected ? "var(--app-control-active-bg)" : "var(--app-surface)",
        transition: "border-color 120ms ease, background-color 120ms ease",
        "&:hover": {
          borderColor: disabled
            ? "var(--app-border)"
            : "var(--app-accent)",
        },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
        <Box
          sx={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            border: "2px solid",
            borderColor: selected ? "var(--app-accent)" : "var(--app-border)",
            position: "relative",
            "&::after": selected
              ? {
                  content: '""',
                  position: "absolute",
                  inset: 2,
                  borderRadius: "50%",
                  bgcolor: "var(--app-accent)",
                }
              : undefined,
          }}
        />
        <Typography sx={{ fontSize: 13, fontWeight: 700, color: "var(--app-fg)" }}>
          {title}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: 12, color: "var(--app-muted)", lineHeight: 1.55 }}>
        {body}
      </Typography>
      {note ? (
        <Typography
          sx={{
            mt: 1,
            fontSize: 11,
            color: "var(--app-muted)",
            fontStyle: "italic",
          }}
        >
          {note}
        </Typography>
      ) : null}
    </Box>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 1.5 }}>
      <Typography
        sx={{
          fontSize: 12,
          fontWeight: 700,
          color: "var(--app-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{
          fontSize: 13,
          fontFamily:
            "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          color: "var(--app-fg)",
          wordBreak: "break-all",
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
