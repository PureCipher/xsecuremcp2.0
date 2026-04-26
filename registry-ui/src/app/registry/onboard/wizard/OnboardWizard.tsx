"use client";

import { useCallback, useState } from "react";
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
  Step,
  StepLabel,
  Stepper,
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

export function OnboardWizard() {
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

  // Step 3: curator overrides
  const [toolName, setToolName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [version, setVersion] = useState("0.1.0");
  const [description, setDescription] = useState("");
  const [selections, setSelections] = useState<PermissionSuggestion[]>([]);
  const [hostingMode, setHostingMode] = useState<"catalog" | "proxy">(
    "catalog",
  );

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
    setToolName("");
    setDisplayName("");
    setVersion("0.1.0");
    setDescription("");
    setSelections([]);
    setHostingMode("catalog");
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
    try {
      const response = await fetch("/api/curate/introspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ upstream: upstreamUrl }),
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
      setStep(2);
    } catch {
      setError("Network error during introspection.");
    } finally {
      setBusy(false);
    }
  }, [upstreamUrl]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setBusy(true);
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
          selected_permissions: selections.map((s) => ({
            scope: s.scope,
            selected: s.selected,
          })),
        }),
      });
      const payload = (await response.json()) as SubmitResponse;
      if (!response.ok || payload.error) {
        setError(payload.error ?? "Submission failed.");
        return;
      }
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
          onBack={() => goBackTo(0)}
          onIntrospect={handleIntrospect}
        />
      ) : null}

      {step === 2 && intro && draft && preview ? (
        <StepConfirm
          intro={intro}
          draft={draft}
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
          onTogglePermission={togglePermission}
          busy={busy}
          onBack={() => goBackTo(1)}
          onSubmit={handleSubmit}
        />
      ) : null}

      {step === 3 && submitResult ? (
        <StepDone result={submitResult} router={router} onReset={resetWizard} />
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
  onBack,
  onIntrospect,
}: {
  preview: UpstreamPreview;
  busy: boolean;
  onBack: () => void;
  onIntrospect: () => void;
}) {
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

// ── Step 3 ────────────────────────────────────────────────────

function StepConfirm({
  intro,
  draft,
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
  onTogglePermission,
  busy,
  onBack,
  onSubmit,
}: {
  intro: IntrospectionResult;
  draft: ManifestDraft;
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
  onTogglePermission: (scope: string) => void;
  busy: boolean;
  onBack: () => void;
  onSubmit: () => void;
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

        {draft.observed_tool_names.length > 0 ? (
          <Box sx={{ mb: 2 }}>
            <Typography
              sx={{
                fontWeight: 700,
                fontSize: 12,
                color: "var(--app-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                mb: 0.75,
              }}
            >
              Observed tools
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
              {draft.observed_tool_names.slice(0, 16).map((n) => (
                <Chip key={n} size="small" label={n} />
              ))}
              {draft.observed_tool_names.length > 16 ? (
                <Chip
                  size="small"
                  variant="outlined"
                  label={`+${draft.observed_tool_names.length - 16} more`}
                />
              ) : null}
            </Box>
          </Box>
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

        <Box sx={{ display: "flex", justifyContent: "space-between" }}>
          <Button onClick={onBack} variant="text">
            Back
          </Button>
          <Button
            onClick={onSubmit}
            disabled={busy || !toolName.trim()}
            variant="contained"
            sx={{
              bgcolor: "var(--app-accent)",
              color: "var(--app-accent-contrast)",
              "&:hover": { bgcolor: "var(--app-accent)" },
              textTransform: "none",
              minWidth: 200,
            }}
          >
            {busy ? <CircularProgress size={18} /> : "Submit curated listing"}
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
}: {
  result: SubmitResponse;
  router: ReturnType<typeof useRouter>;
  onReset: () => void;
}) {
  const listingName = result.listing?.tool_name ?? "your listing";
  return (
    <Card variant="outlined">
      <CardContent>
        <Alert severity="success" sx={{ mb: 2 }}>
          Curated listing submitted for review.
        </Alert>
        <Typography sx={{ color: "var(--app-muted)", fontSize: 14, mb: 2 }}>
          <strong>{listingName}</strong> was published as a
          curator-attested listing. A reviewer will approve or reject
          it before it appears in the public catalog.
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
