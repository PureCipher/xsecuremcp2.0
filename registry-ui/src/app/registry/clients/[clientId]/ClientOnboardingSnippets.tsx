"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import type {
  RegistryClientSummary,
  RegistryClientTokenSummary,
} from "@/lib/registryClient";

/**
 * Iter 14.33 — Client onboarding snippets.
 *
 * Symmetric to Iter 14.29 on the listing side. Where that component
 * answers "how do I install this MCP server in my client?", this
 * one answers "how do I authenticate THIS client against the
 * registry from my code?". Four targets, the highest-leverage
 * onboarding workflows in priority order:
 *
 *   - Python SDK   (fastmcp.Client)
 *   - TypeScript SDK (@modelcontextprotocol/sdk, streamable-http)
 *   - Inspector / mcp-cli (npx @modelcontextprotocol/inspector)
 *   - curl (JSON-RPC tools/list and tools/call)
 *
 * Each snippet pre-fills the client's slug and points at the
 * registry's MCP endpoint, defaulting to `${origin}/mcp` derived
 * from the browser. Operators can override the URL inline; some
 * deployments mount the registry behind a different path or proxy.
 *
 * The bearer token is always rendered as an env-var placeholder
 * (`PURECIPHER_TOKEN`). The registry only returns plaintext secrets
 * once, at token-issue time — we never embed a real secret in the
 * snippet, even when one is hypothetically available in the page's
 * memory (it is not, by design — issued secrets render on the
 * issuance card and are not held in any state our snippet builder
 * could observe).
 *
 * If the client has no active tokens, render a soft alert pointing
 * the operator at the "Issue token" button on the parent page. The
 * snippets still render — they're useful as documentation even
 * before the operator commits to issuing a token — but we don't
 * mislead them about what's required to actually connect.
 */

// ── Configuration ─────────────────────────────────────────────

const TOKEN_ENV_VAR = "PURECIPHER_TOKEN";

type TabId = "python-sdk" | "typescript-sdk" | "inspector" | "curl";

type Snippet = {
  text: string;
  language: "python" | "typescript" | "bash";
  description: string;
  installCommand?: string;
};

type TabDefinition = {
  id: TabId;
  label: string;
  build: (params: BuildParams) => Snippet;
};

type BuildParams = {
  registryUrl: string;
  clientSlug: string;
  clientDisplayName: string;
};

// ── Helpers ───────────────────────────────────────────────────

function shellQuote(value: string): string {
  if (/^[A-Za-z0-9_./@:=+-]+$/.test(value)) return value;
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function defaultRegistryUrl(): string {
  // Server-render fallback. The component is "use client" so this
  // path runs only when navigator/window aren't yet available
  // (vanishingly rare in practice but defended for SSR safety).
  if (typeof window === "undefined") return "http://127.0.0.1:8000/mcp";
  // Trim any trailing slash on origin to keep the joined URL clean.
  return `${window.location.origin.replace(/\/$/, "")}/mcp`;
}

function trimUrl(url: string): string {
  // Strip whitespace + trailing slash so curl/JSON-RPC posts go to
  // the canonical endpoint without producing `…/mcp//` URLs.
  return url.trim().replace(/\/+$/, "");
}

// ── Snippet builders ─────────────────────────────────────────

const PYTHON_SDK: TabDefinition = {
  id: "python-sdk",
  label: "Python SDK",
  build: ({ registryUrl, clientSlug, clientDisplayName }) => ({
    language: "python",
    text:
      `import asyncio\n` +
      `import os\n\n` +
      `from fastmcp import Client\n\n` +
      `# Bearer token issued in the registry UI for client "${clientDisplayName}"\n` +
      `# (slug: ${clientSlug}). The registry shows the secret exactly once\n` +
      `# at issue time — store it in your secrets manager and export it\n` +
      `# as the env var below before running.\n` +
      `TOKEN = os.environ["${TOKEN_ENV_VAR}"]\n\n` +
      `async def main():\n` +
      `    async with Client(\n` +
      `        ${JSON.stringify(registryUrl)},\n` +
      `        auth=TOKEN,\n` +
      `    ) as client:\n` +
      `        tools = await client.list_tools()\n` +
      `        for t in tools:\n` +
      `            print(t.name, "—", t.description or "")\n\n` +
      `if __name__ == "__main__":\n` +
      `    asyncio.run(main())\n`,
    description: `Connect from any Python service or notebook. The fastmcp Client uses the streamable-HTTP transport against the registry endpoint and attaches the bearer token via the \`auth=\` shortcut. All telemetry the registry attributes back will use the slug "${clientSlug}".`,
    installCommand: "pip install fastmcp",
  }),
};

const TYPESCRIPT_SDK: TabDefinition = {
  id: "typescript-sdk",
  label: "TypeScript SDK",
  build: ({ registryUrl, clientSlug, clientDisplayName }) => ({
    language: "typescript",
    text:
      `import { Client } from "@modelcontextprotocol/sdk/client/index.js";\n` +
      `import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";\n\n` +
      `// Bearer token issued in the registry UI for client "${clientDisplayName}"\n` +
      `// (slug: ${clientSlug}). The registry shows the secret exactly once\n` +
      `// at issue time — store it in your secrets manager and export it as\n` +
      `// the env var below.\n` +
      `const TOKEN = process.env.${TOKEN_ENV_VAR};\n` +
      `if (!TOKEN) throw new Error("${TOKEN_ENV_VAR} env var is required");\n\n` +
      `const transport = new StreamableHTTPClientTransport(\n` +
      `  new URL(${JSON.stringify(registryUrl)}),\n` +
      `  {\n` +
      `    requestInit: {\n` +
      `      headers: { Authorization: \`Bearer \${TOKEN}\` },\n` +
      `    },\n` +
      `  },\n` +
      `);\n\n` +
      `const client = new Client(\n` +
      `  { name: ${JSON.stringify(clientSlug)}, version: "1.0.0" },\n` +
      `  { capabilities: {} },\n` +
      `);\n\n` +
      `await client.connect(transport);\n` +
      `const { tools } = await client.listTools();\n` +
      `console.log(tools);\n`,
    description: `Connect from a Node.js service. Uses StreamableHTTPClientTransport (the canonical MCP HTTP transport) and threads the bearer token via the underlying fetch's request init. The registry's audit log will see the slug "${clientSlug}" as the actor on every call.`,
    installCommand: "npm install @modelcontextprotocol/sdk",
  }),
};

const INSPECTOR_TAB: TabDefinition = {
  id: "inspector",
  label: "Inspector / mcp-cli",
  build: ({ registryUrl, clientSlug }) => ({
    language: "bash",
    text:
      `# Smoke-test the connection from the terminal. The Inspector is\n` +
      `# the canonical MCP CLI: it opens a local browser UI for browsing\n` +
      `# tools, resources, prompts, and exercising calls — useful before\n` +
      `# committing the SDK code path on either side.\n\n` +
      `# 1) Set your token in the shell:\n` +
      `export ${TOKEN_ENV_VAR}=<paste-issued-token-here>\n\n` +
      `# 2) Launch the Inspector pointing at the registry endpoint:\n` +
      `npx @modelcontextprotocol/inspector ${shellQuote(registryUrl)}\n\n` +
      `# 3) A browser tab opens with the Inspector's web UI. Before\n` +
      `# clicking Connect:\n` +
      `#    - Open the request-configuration panel (gear / settings icon).\n` +
      `#    - Choose transport: Streamable HTTP.\n` +
      `#    - Add a custom header:\n` +
      `#         Authorization: Bearer $${TOKEN_ENV_VAR}\n` +
      `#      (or paste the literal token value).\n` +
      `#    - Click Connect.\n\n` +
      `# The registry's actor resolver maps the bearer to slug\n` +
      `# "${clientSlug}", so every call in this session is attributed to\n` +
      `# that client in the audit log.\n`,
    description: `Run an interactive smoke test before wiring SDK code. The Inspector launches with the registry URL pre-loaded; you add the Authorization header in its web UI's request panel before connecting. The registry resolves the bearer to slug "${clientSlug}" and attributes calls accordingly.`,
    installCommand: "npx -y @modelcontextprotocol/inspector --help",
  }),
};

const CURL_TAB: TabDefinition = {
  id: "curl",
  label: "curl (JSON-RPC)",
  build: ({ registryUrl, clientSlug }) => ({
    language: "bash",
    text:
      `# Direct JSON-RPC against the registry's streamable-HTTP endpoint.\n` +
      `# Useful for shell scripts, smoke tests, or runtimes without an\n` +
      `# MCP SDK. Calls are attributed to slug "${clientSlug}" by the\n` +
      `# registry's actor resolver.\n\n` +
      `# Required: the bearer token issued in the UI.\n` +
      `export ${TOKEN_ENV_VAR}=<paste-issued-token-here>\n\n` +
      `# 1) List available tools.\n` +
      `curl -X POST ${shellQuote(registryUrl)} \\\n` +
      `  -H "Authorization: Bearer $${TOKEN_ENV_VAR}" \\\n` +
      `  -H 'Content-Type: application/json' \\\n` +
      `  -H 'Accept: application/json, text/event-stream' \\\n` +
      `  -d '{\n` +
      `    "jsonrpc": "2.0",\n` +
      `    "id": 1,\n` +
      `    "method": "tools/list"\n` +
      `  }'\n\n` +
      `# 2) Call a tool. Replace TOOL_NAME and arguments with the\n` +
      `# specifics of the tool you want to invoke.\n` +
      `curl -X POST ${shellQuote(registryUrl)} \\\n` +
      `  -H "Authorization: Bearer $${TOKEN_ENV_VAR}" \\\n` +
      `  -H 'Content-Type: application/json' \\\n` +
      `  -H 'Accept: application/json, text/event-stream' \\\n` +
      `  -d '{\n` +
      `    "jsonrpc": "2.0",\n` +
      `    "id": 2,\n` +
      `    "method": "tools/call",\n` +
      `    "params": {\n` +
      `      "name": "TOOL_NAME",\n` +
      `      "arguments": {}\n` +
      `    }\n` +
      `  }'\n`,
    description: `Two JSON-RPC calls against the registry endpoint: list available tools, then invoke one. Drop into shell scripts, smoke tests, or runtimes without an MCP SDK. The Authorization header is what binds calls to slug "${clientSlug}" in audit.`,
  }),
};

const TABS: TabDefinition[] = [
  PYTHON_SDK,
  TYPESCRIPT_SDK,
  INSPECTOR_TAB,
  CURL_TAB,
];

// ── Component ────────────────────────────────────────────────

export function ClientOnboardingSnippets({
  client,
  tokens,
}: {
  client: RegistryClientSummary;
  tokens: RegistryClientTokenSummary[];
}) {
  // Lazy-initialize from window.location to avoid SSR mismatch and
  // to handle the "registry mounted under a non-/mcp path" case
  // — the operator can edit the URL inline.
  const [registryUrl, setRegistryUrl] = useState<string>(() =>
    defaultRegistryUrl(),
  );
  // Re-derive default after hydration in case the SSR pass produced
  // the fallback (vanishingly rare; defensive).
  useEffect(() => {
    if (typeof window !== "undefined") {
      setRegistryUrl((prev) => {
        const fresh = defaultRegistryUrl();
        return prev === "http://127.0.0.1:8000/mcp" ? fresh : prev;
      });
    }
  }, []);

  const [activeTab, setActiveTab] = useState<TabId>("python-sdk");
  const [copied, setCopied] = useState<TabId | null>(null);

  const activeTokens = useMemo(
    () => tokens.filter((t) => t.active),
    [tokens],
  );
  const isSuspended = client.status === "suspended";

  const params: BuildParams = useMemo(
    () => ({
      registryUrl: trimUrl(registryUrl),
      clientSlug: client.slug,
      clientDisplayName: client.display_name || client.slug,
    }),
    [registryUrl, client.slug, client.display_name],
  );

  const activeDef = TABS.find((t) => t.id === activeTab) ?? PYTHON_SDK;
  const snippet = activeDef.build(params);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet.text);
      setCopied(activeTab);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = snippet.text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand("copy");
        setCopied(activeTab);
        window.setTimeout(() => setCopied(null), 1500);
      } finally {
        document.body.removeChild(textarea);
      }
    }
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Box
          sx={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 1,
            flexWrap: "wrap",
            mb: 1,
          }}
        >
          <Box>
            <Typography
              sx={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Connect from your code
            </Typography>
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Pick a target — Python, TypeScript, Inspector, or curl — and copy
              the snippet. Each is pre-filled with this client&apos;s slug and
              authenticates via bearer token.
            </Typography>
          </Box>
          <Chip
            size="small"
            label={`slug · ${client.slug}`}
            sx={{
              fontFamily:
                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 11,
              bgcolor: "var(--app-control-bg)",
              color: "var(--app-muted)",
              border: "1px solid var(--app-border)",
            }}
          />
        </Box>

        {isSuspended ? (
          <Alert severity="warning" sx={{ mb: 1.5, fontSize: 12 }}>
            This client is currently <strong>suspended</strong>. The registry
            will reject calls bearing its tokens with HTTP 403 until it is
            reinstated. The snippets below are still accurate; they just
            won&apos;t succeed in this state.
          </Alert>
        ) : null}

        {activeTokens.length === 0 && !isSuspended ? (
          <Alert severity="info" sx={{ mb: 1.5, fontSize: 12 }}>
            No active bearer tokens for this client yet. Use the{" "}
            <strong>Issue token</strong> button above first — the registry
            shows the secret exactly once, on issue, and only stores its hash
            after that.
          </Alert>
        ) : null}

        <Box sx={{ mb: 1.5 }}>
          <TextField
            label="Registry MCP endpoint"
            size="small"
            value={registryUrl}
            onChange={(e) => setRegistryUrl(e.target.value)}
            fullWidth
            helperText={
              "Default: ${origin}/mcp (the streamable-HTTP path the registry mounts). Override if your deployment uses a different path or reverse proxy."
            }
            slotProps={{
              input: {
                sx: {
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 12,
                },
              },
            }}
          />
        </Box>

        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v as TabId)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 36,
            "& .MuiTab-root": {
              minHeight: 36,
              textTransform: "none",
              fontSize: 12.5,
              fontWeight: 600,
              color: "var(--app-muted)",
              "&.Mui-selected": { color: "var(--app-fg)" },
            },
            "& .MuiTabs-indicator": { bgcolor: "var(--app-accent)" },
          }}
        >
          {TABS.map((t) => (
            <Tab key={t.id} value={t.id} label={t.label} />
          ))}
        </Tabs>

        <Box sx={{ mt: 1.5, position: "relative" }}>
          <Box
            component="pre"
            sx={{
              m: 0,
              p: 2,
              pr: 9,
              bgcolor: "var(--app-control-bg)",
              border: "1px solid var(--app-border)",
              borderRadius: 2,
              fontFamily:
                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 12,
              lineHeight: 1.55,
              color: "var(--app-fg)",
              overflow: "auto",
              maxHeight: 360,
              whiteSpace: "pre",
            }}
          >
            {snippet.text}
          </Box>
          <Box
            sx={{
              position: "absolute",
              top: 8,
              right: 8,
              display: "flex",
              gap: 0.5,
              alignItems: "center",
            }}
          >
            <Chip
              size="small"
              label={snippet.language}
              sx={{
                fontSize: 10,
                height: 20,
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                bgcolor: "var(--app-surface)",
                color: "var(--app-muted)",
                border: "1px solid var(--app-border)",
              }}
            />
            <Tooltip
              title={copied === activeTab ? "Copied!" : "Copy to clipboard"}
            >
              <Button
                onClick={handleCopy}
                size="small"
                variant="outlined"
                sx={{
                  textTransform: "none",
                  minWidth: 0,
                  px: 1.25,
                  py: 0.25,
                  fontSize: 11,
                  fontWeight: 700,
                  bgcolor: "var(--app-surface)",
                  borderColor: "var(--app-border)",
                  color:
                    copied === activeTab
                      ? "var(--app-accent)"
                      : "var(--app-fg)",
                }}
              >
                {copied === activeTab ? "✓ Copied" : "Copy"}
              </Button>
            </Tooltip>
          </Box>
        </Box>

        <Box sx={{ mt: 1.5, display: "grid", gap: 0.75 }}>
          <Typography sx={{ fontSize: 12, color: "var(--app-muted)" }}>
            {snippet.description}
          </Typography>

          {snippet.installCommand ? (
            <Box
              sx={{
                display: "flex",
                alignItems: "baseline",
                gap: 1,
                flexWrap: "wrap",
                fontSize: 11,
                color: "var(--app-muted)",
              }}
            >
              <Box
                component="span"
                sx={{
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                }}
              >
                Install once
              </Box>
              <Box
                component="code"
                sx={{
                  fontFamily:
                    "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 11,
                  color: "var(--app-fg)",
                  bgcolor: "var(--app-control-bg)",
                  border: "1px solid var(--app-border)",
                  borderRadius: 1,
                  px: 0.75,
                  py: 0.25,
                }}
              >
                {snippet.installCommand}
              </Box>
            </Box>
          ) : null}

          <Typography sx={{ fontSize: 11, color: "var(--app-muted)" }}>
            The {TOKEN_ENV_VAR} placeholder represents the bearer secret
            returned by the registry when the token was issued. Treat it like
            any other production secret: keep it out of source control, rotate
            via the &ldquo;Issue token&rdquo; / &ldquo;Revoke&rdquo; flow, and
            never paste it into a snippet you&apos;ll commit.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}
