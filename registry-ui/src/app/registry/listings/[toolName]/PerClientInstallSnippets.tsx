"use client";

import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import type {
  RegistryToolListing,
  RegistryUpstreamRef,
} from "@/lib/registryClient";

/**
 * Iter 14.29.1 — Per-client install snippets, ceiling pass.
 *
 * Generates ready-to-paste / ready-to-run snippets for the workflows
 * a curator actually performs after landing on a listing detail page:
 *
 *   GUI clients (paste JSON into a config file)
 *     · Claude Desktop
 *     · Cursor
 *     · Continue
 *     · Cline
 *
 *   CLI / probing (terminal-first workflows)
 *     · Inspector / mcp-cli (modelcontextprotocol/inspector)
 *     · curl (HTTP MCP servers, JSON-RPC)
 *
 *   SDK call (programmatic embedding)
 *     · Python (fastmcp Client)
 *     · TypeScript (@modelcontextprotocol/sdk)
 *
 * The original `RecipeTabs` component (rendered separately on the
 * listing page) covers transport-level concerns: verify the
 * attestation, run via Docker compose, talk MCP over stdio. This
 * component covers the other half: "how do I actually call this?"
 *
 * Three things make these snippets useful rather than misleading:
 *
 *   1. Channel→spawn translation. Each upstream channel (pypi, npm,
 *      docker, http) maps to a different command/args/url shape. We
 *      generate one canonical spawn entry from upstream_ref and
 *      project it into each client's expected wrapper.
 *
 *   2. Required-env passthrough. The manifest's `metadata.env` (or
 *      `metadata.env_vars`) lists the env vars the server needs at
 *      startup. We surface them as placeholders inside every snippet
 *      so the curator knows their tool will fail without them. Skip
 *      this and you ship a snippet that pastes cleanly but panics on
 *      first run — the most common first-run failure mode.
 *
 *   3. Streamable-HTTP transport. The MCP spec moved off SSE to
 *      `streamable-http` as the canonical HTTP transport. We honor
 *      `metadata.transport` if the publisher overrides, otherwise
 *      default to streamable-http (matching the backend default).
 *
 * If the listing has no upstream_ref (a curator-attested catalog
 * listing without a transport ref), this component renders an
 * explanatory empty state rather than misleading config.
 */

// ── Channel → spawn entry ─────────────────────────────────────

type SpawnEntry = {
  command?: string;
  args?: string[];
  url?: string;
  transport?: string;
};

function spawnEntryForUpstream(
  upstream: RegistryUpstreamRef,
  metadataTransport: string | null,
): SpawnEntry | null {
  const channel = (upstream.channel ?? "").toLowerCase();
  const identifier = upstream.identifier ?? "";
  const version = upstream.version ?? "";
  if (!identifier) return null;

  if (channel === "http") {
    // Iter 14.29.1 — switch to streamable-http (the canonical MCP
    // HTTP transport) instead of legacy SSE. Allow the publisher to
    // override via metadata.transport for back-compat with servers
    // that haven't migrated yet.
    return {
      url: identifier,
      transport: metadataTransport || "streamable-http",
    };
  }
  if (channel === "pypi") {
    const spec = version ? `${identifier}@${version}` : identifier;
    return { command: "uvx", args: [spec] };
  }
  if (channel === "npm") {
    const spec = version ? `${identifier}@${version}` : identifier;
    return { command: "npx", args: ["-y", spec] };
  }
  if (channel === "docker") {
    const imageRef = version
      ? identifier.includes("@") || identifier.includes(":")
        ? identifier
        : `${identifier}:${version}`
      : identifier;
    return {
      command: "docker",
      args: ["run", "--rm", "-i", imageRef],
    };
  }
  return null;
}

// ── Env-var extraction ────────────────────────────────────────

type EnvMap = Record<string, string>;

function extractEnv(metadata: unknown): EnvMap {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return {};
  }
  const meta = metadata as Record<string, unknown>;
  const raw = meta.env ?? meta.env_vars;
  if (!raw) return {};
  // Dict form: { "OPENAI_API_KEY": "<value>" }
  if (typeof raw === "object" && !Array.isArray(raw)) {
    const out: EnvMap = {};
    for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
      const k = String(key).trim();
      if (!k) continue;
      out[k] = typeof val === "string" && val.trim() ? val : `\${${k}}`;
    }
    return out;
  }
  // List form: ["OPENAI_API_KEY"] → infer ${VAR_NAME} placeholder.
  if (Array.isArray(raw)) {
    const out: EnvMap = {};
    for (const item of raw) {
      const k = String(item).trim();
      if (!k) continue;
      out[k] = `\${${k}}`;
    }
    return out;
  }
  return {};
}

// ── OS detection ──────────────────────────────────────────────

type OsKey = "mac" | "windows" | "linux";

function detectOS(): OsKey {
  if (typeof navigator === "undefined") return "mac";
  const platform = (navigator.platform ?? "").toLowerCase();
  const ua = (navigator.userAgent ?? "").toLowerCase();
  if (platform.includes("mac") || ua.includes("mac os")) return "mac";
  if (platform.includes("win") || ua.includes("windows")) return "windows";
  return "linux";
}

// ── Snippet shape ────────────────────────────────────────────

type Language = "json" | "bash" | "python" | "typescript";

type Snippet = {
  /** The raw text users will copy. */
  text: string;
  language: Language;
  /** Short note rendered below the snippet. */
  description: string;
  /** OS-aware config-file hint. Only for GUI clients. */
  configPath?: { mac: string; windows: string; linux: string };
  /** Optional install command (shown for SDK / CLI tabs). */
  installCommand?: string;
  /** When `false`, render the disabled-state message instead of the snippet. */
  applicable: boolean;
  disabledReason?: string;
};

type SnippetTabId =
  | "claude-desktop"
  | "cursor"
  | "continue"
  | "cline"
  | "inspector"
  | "curl"
  | "python-sdk"
  | "typescript-sdk";

type TabDefinition = {
  id: SnippetTabId;
  label: string;
  group: "GUI" | "CLI" | "SDK";
  build: (
    toolName: string,
    spawn: SpawnEntry,
    env: EnvMap,
    channel: string,
  ) => Snippet;
};

// ── GUI client builders ───────────────────────────────────────

function spawnWithEnv(spawn: SpawnEntry, env: EnvMap): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (spawn.command) out.command = spawn.command;
  if (spawn.args && spawn.args.length > 0) out.args = spawn.args;
  if (spawn.url) out.url = spawn.url;
  if (spawn.transport) out.transport = spawn.transport;
  if (Object.keys(env).length > 0) out.env = env;
  return out;
}

const CLAUDE_DESKTOP: TabDefinition = {
  id: "claude-desktop",
  label: "Claude Desktop",
  group: "GUI",
  build: (toolName, spawn, env) => ({
    applicable: true,
    language: "json",
    text: JSON.stringify(
      { mcpServers: { [toolName]: spawnWithEnv(spawn, env) } },
      null,
      2,
    ),
    description:
      "Add this entry under mcpServers in Claude Desktop's config file. Restart Claude Desktop after editing to load the server.",
    configPath: {
      mac: "~/Library/Application Support/Claude/claude_desktop_config.json",
      windows: "%APPDATA%\\Claude\\claude_desktop_config.json",
      linux: "~/.config/Claude/claude_desktop_config.json",
    },
  }),
};

const CURSOR: TabDefinition = {
  id: "cursor",
  label: "Cursor",
  group: "GUI",
  build: (toolName, spawn, env) => ({
    applicable: true,
    language: "json",
    text: JSON.stringify(
      { mcpServers: { [toolName]: spawnWithEnv(spawn, env) } },
      null,
      2,
    ),
    description:
      "Cursor reads MCP servers from .cursor/mcp.json. The project-local file takes precedence over the global one.",
    configPath: {
      mac: "~/.cursor/mcp.json (global) or ./.cursor/mcp.json (per project)",
      windows: "%USERPROFILE%\\.cursor\\mcp.json",
      linux: "~/.cursor/mcp.json",
    },
  }),
};

const CONTINUE_CLIENT: TabDefinition = {
  id: "continue",
  label: "Continue",
  group: "GUI",
  build: (toolName, spawn, env) => {
    let entry: Record<string, unknown>;
    if (spawn.url) {
      entry = {
        name: toolName,
        transport: {
          type: spawn.transport ?? "streamable-http",
          url: spawn.url,
        },
      };
    } else {
      const stdio: Record<string, unknown> = {
        type: "stdio",
        command: spawn.command,
        args: spawn.args ?? [],
      };
      if (Object.keys(env).length > 0) stdio.env = env;
      entry = { name: toolName, transport: stdio };
    }
    return {
      applicable: true,
      language: "json",
      text: JSON.stringify(
        {
          experimental: { modelContextProtocolServers: [entry] },
        },
        null,
        2,
      ),
      description:
        "Continue uses an experimental MCP integration. Add the entry to the experimental.modelContextProtocolServers array.",
      configPath: {
        mac: "~/.continue/config.json",
        windows: "%USERPROFILE%\\.continue\\config.json",
        linux: "~/.continue/config.json",
      },
    };
  },
};

const CLINE: TabDefinition = {
  id: "cline",
  label: "Cline",
  group: "GUI",
  build: (toolName, spawn, env) => ({
    applicable: true,
    language: "json",
    text: JSON.stringify(
      { mcpServers: { [toolName]: spawnWithEnv(spawn, env) } },
      null,
      2,
    ),
    description:
      "Cline (the VS Code extension) stores MCP servers under the extension's globalStorage. Edit the JSON file directly or use Cline's MCP server panel.",
    configPath: {
      mac: "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
      windows:
        "%APPDATA%\\Code\\User\\globalStorage\\saoudrizwan.claude-dev\\settings\\cline_mcp_settings.json",
      linux:
        "~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    },
  }),
};

// ── CLI builders ──────────────────────────────────────────────

function shellQuote(value: string): string {
  // Minimal POSIX-shell quoting: single-quote and escape embedded
  // single quotes. Good enough for tool specs / URLs / env values.
  if (/^[A-Za-z0-9_./@:=+-]+$/.test(value)) return value;
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function envPrefix(env: EnvMap): string {
  if (Object.keys(env).length === 0) return "";
  return (
    Object.entries(env)
      .map(([k, v]) => `${k}=${shellQuote(v)}`)
      .join(" ") + " \\\n  "
  );
}

const INSPECTOR_TAB: TabDefinition = {
  id: "inspector",
  label: "Inspector / mcp-cli",
  group: "CLI",
  build: (toolName, spawn, env, channel) => {
    const prefix = envPrefix(env);
    let body: string;
    if (channel === "http" && spawn.url) {
      body = `npx @modelcontextprotocol/inspector ${shellQuote(spawn.url)}`;
    } else if (spawn.command) {
      const parts = [spawn.command, ...(spawn.args ?? [])].map(shellQuote);
      body = `npx @modelcontextprotocol/inspector ${parts.join(" ")}`;
    } else {
      return {
        applicable: false,
        language: "bash",
        text: "",
        description: "",
        disabledReason:
          "This listing's upstream_ref doesn't carry a runnable transport (no command, no URL).",
      };
    }
    return {
      applicable: true,
      language: "bash",
      text:
        `# Launches the MCP Inspector against ${toolName}.\n` +
        `# It opens a local web UI for browsing tools, resources,\n` +
        `# prompts, and exercising calls interactively.\n` +
        `${prefix}${body}`,
      description:
        "The Inspector is the canonical MCP CLI. It connects to your server and exposes its surface area through a local browser UI — ideal for smoke-testing before pasting JSON into a client config.",
      installCommand: "npx -y @modelcontextprotocol/inspector --help",
    };
  },
};

const CURL_TAB: TabDefinition = {
  id: "curl",
  label: "curl (JSON-RPC)",
  group: "CLI",
  build: (toolName, spawn, env, channel) => {
    if (channel !== "http" || !spawn.url) {
      return {
        applicable: false,
        language: "bash",
        text: "",
        description: "",
        disabledReason:
          "curl only works for HTTP-channel MCP servers. This listing uses a stdio transport — use the Inspector or SDK tabs instead.",
      };
    }
    const url = shellQuote(spawn.url);
    // For HTTP servers env vars belong on the *server*, not on the
    // curl client; surface a hint rather than prepending them.
    const envHint =
      Object.keys(env).length > 0
        ? `# Note: this server expects env vars at startup:\n#   ${Object.keys(env).join(", ")}\n# These are the server's own env, not curl's. The publisher\n# is responsible for provisioning them on the deployed instance.\n\n`
        : "";
    return {
      applicable: true,
      language: "bash",
      text:
        envHint +
        `# 1) Discover the tool surface (MCP tools/list).\n` +
        `curl -X POST ${url} \\\n` +
        `  -H 'Content-Type: application/json' \\\n` +
        `  -H 'Accept: application/json, text/event-stream' \\\n` +
        `  -d '{\n` +
        `    "jsonrpc": "2.0",\n` +
        `    "id": 1,\n` +
        `    "method": "tools/list"\n` +
        `  }'\n\n` +
        `# 2) Call a tool (replace TOOL_METHOD and arguments).\n` +
        `curl -X POST ${url} \\\n` +
        `  -H 'Content-Type: application/json' \\\n` +
        `  -H 'Accept: application/json, text/event-stream' \\\n` +
        `  -d '{\n` +
        `    "jsonrpc": "2.0",\n` +
        `    "id": 2,\n` +
        `    "method": "tools/call",\n` +
        `    "params": {\n` +
        `      "name": "TOOL_METHOD",\n` +
        `      "arguments": {}\n` +
        `    }\n` +
        `  }'`,
      description: `Direct JSON-RPC calls to ${toolName}. Useful for scripting, smoke tests, or integrating from a non-Node/non-Python runtime. If the server requires bearer auth, add an \`-H 'Authorization: Bearer …'\` header.`,
    };
  },
};

// ── SDK builders ──────────────────────────────────────────────

function pyRepr(value: string): string {
  // Python repr is fine for ASCII-dominant strings; fall back to
  // JSON.stringify which produces a compatible literal for the
  // narrow subset of values we emit.
  return JSON.stringify(value);
}

const PYTHON_SDK: TabDefinition = {
  id: "python-sdk",
  label: "Python SDK",
  group: "SDK",
  build: (toolName, spawn, env, channel) => {
    const envBlock =
      Object.keys(env).length > 0
        ? "\n    # Required env vars for this server:\n" +
          Object.keys(env)
            .map((k) => `    os.environ.setdefault(${pyRepr(k)}, ${pyRepr(`<your ${k} value>`)})`)
            .join("\n") +
          "\n"
        : "";

    let body: string;
    if (channel === "http" && spawn.url) {
      body =
        `    # Streamable-HTTP MCP server.\n` +
        `    async with Client(${pyRepr(spawn.url)}) as client:\n` +
        `        tools = await client.list_tools()\n` +
        `        for t in tools:\n` +
        `            print(t.name, "—", t.description or "")`;
    } else if (spawn.command) {
      const argsRepr = JSON.stringify(spawn.args ?? []);
      // Hand-format the env dict so it lines up with the surrounding
      // 16-space-indented "command" / "args" keys. JSON.stringify
      // with an indent argument doesn't honor existing indentation
      // depth, so we'd end up with the env body floating at column
      // 26 rather than 20.
      const envForConfig =
        Object.keys(env).length > 0
          ? `,\n                "env": {\n` +
            Object.entries(env)
              .map(
                ([k, v]) =>
                  `                    ${JSON.stringify(k)}: ${JSON.stringify(v)}`,
              )
              .join(",\n") +
            `\n                }`
          : "";
      body =
        `    # stdio MCP server — fastmcp.Client accepts the same\n` +
        `    # mcpServers config block your GUI client uses.\n` +
        `    config = {\n` +
        `        "mcpServers": {\n` +
        `            ${pyRepr(toolName)}: {\n` +
        `                "command": ${pyRepr(spawn.command)},\n` +
        `                "args": ${argsRepr}` +
        envForConfig +
        `\n            }\n` +
        `        }\n` +
        `    }\n` +
        `    async with Client(config) as client:\n` +
        `        tools = await client.list_tools()\n` +
        `        for t in tools:\n` +
        `            print(t.name, "—", t.description or "")`;
    } else {
      return {
        applicable: false,
        language: "python",
        text: "",
        description: "",
        disabledReason:
          "This listing's upstream_ref doesn't carry a runnable transport.",
      };
    }

    return {
      applicable: true,
      language: "python",
      text:
        `import asyncio\n` +
        (Object.keys(env).length > 0 ? `import os\n` : ``) +
        `\n` +
        `from fastmcp import Client\n\n` +
        `async def main():` +
        envBlock +
        `\n` +
        body +
        `\n\n` +
        `if __name__ == "__main__":\n` +
        `    asyncio.run(main())\n`,
      description: `Embed ${toolName} in a Python service or notebook. The fastmcp Client handles transport selection from the config block — same shape your GUI client expects.`,
      installCommand: "pip install fastmcp",
    };
  },
};

const TYPESCRIPT_SDK: TabDefinition = {
  id: "typescript-sdk",
  label: "TypeScript SDK",
  group: "SDK",
  build: (toolName, spawn, env, channel) => {
    const importHttp =
      `import { Client } from "@modelcontextprotocol/sdk/client/index.js";\n` +
      `import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";\n`;
    const importStdio =
      `import { Client } from "@modelcontextprotocol/sdk/client/index.js";\n` +
      `import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";\n`;

    let body: string;
    if (channel === "http" && spawn.url) {
      body =
        importHttp +
        `\n` +
        `const transport = new StreamableHTTPClientTransport(\n` +
        `  new URL(${JSON.stringify(spawn.url)}),\n` +
        `);\n\n` +
        `const client = new Client(\n` +
        `  { name: "registry-test", version: "1.0.0" },\n` +
        `  { capabilities: {} },\n` +
        `);\n\n` +
        `await client.connect(transport);\n` +
        `const { tools } = await client.listTools();\n` +
        `console.log(tools);\n`;
    } else if (spawn.command) {
      const envBlock =
        Object.keys(env).length > 0
          ? `,\n  env: {\n` +
            Object.keys(env)
              .map(
                (k) =>
                  `    ${JSON.stringify(k)}: process.env.${k.replace(/[^A-Za-z0-9_]/g, "_")} ?? ${JSON.stringify(env[k])},`,
              )
              .join("\n") +
            `\n  }`
          : "";
      body =
        importStdio +
        `\n` +
        `const transport = new StdioClientTransport({\n` +
        `  command: ${JSON.stringify(spawn.command)},\n` +
        `  args: ${JSON.stringify(spawn.args ?? [])}` +
        envBlock +
        `,\n` +
        `});\n\n` +
        `const client = new Client(\n` +
        `  { name: "registry-test", version: "1.0.0" },\n` +
        `  { capabilities: {} },\n` +
        `);\n\n` +
        `await client.connect(transport);\n` +
        `const { tools } = await client.listTools();\n` +
        `console.log(tools);\n`;
    } else {
      return {
        applicable: false,
        language: "typescript",
        text: "",
        description: "",
        disabledReason:
          "This listing's upstream_ref doesn't carry a runnable transport.",
      };
    }

    return {
      applicable: true,
      language: "typescript",
      text: body,
      description: `Embed ${toolName} in a Node.js service. Uses streamable-http for HTTP servers and StdioClientTransport for stdio servers — the canonical transports in the latest MCP spec.`,
      installCommand: "npm install @modelcontextprotocol/sdk",
    };
  },
};

const TABS: TabDefinition[] = [
  CLAUDE_DESKTOP,
  CURSOR,
  CONTINUE_CLIENT,
  CLINE,
  INSPECTOR_TAB,
  CURL_TAB,
  PYTHON_SDK,
  TYPESCRIPT_SDK,
];

// ── Component ───────────────────────────────────────────────────

export function PerClientInstallSnippets({
  tool,
}: {
  tool: RegistryToolListing;
}) {
  const [activeTab, setActiveTab] = useState<SnippetTabId>("claude-desktop");
  const [copied, setCopied] = useState<SnippetTabId | null>(null);
  const [os, setOs] = useState<OsKey>(() => detectOS());

  const channel = (tool.upstream_ref?.channel ?? "").toLowerCase();
  const metadataTransport = useMemo(() => {
    const meta = tool.metadata as Record<string, unknown> | undefined;
    const t = meta?.transport;
    return typeof t === "string" && t.trim() ? t.trim() : null;
  }, [tool.metadata]);

  const spawn = useMemo(() => {
    if (!tool.upstream_ref) return null;
    return spawnEntryForUpstream(tool.upstream_ref, metadataTransport);
  }, [tool.upstream_ref, metadataTransport]);

  const env = useMemo(() => extractEnv(tool.metadata), [tool.metadata]);

  // No upstream ref → catalog listing without a runnable transport.
  if (!spawn) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "var(--app-muted)",
            }}
          >
            Install in your client
          </Typography>
          <Typography sx={{ mt: 1, fontSize: 13, color: "var(--app-muted)" }}>
            This listing doesn&apos;t carry a transport reference, so we
            can&apos;t generate per-client install snippets. See the
            recipe tabs below for transport-level instructions, or contact
            the publisher for the install path their client expects.
          </Typography>
        </CardContent>
      </Card>
    );
  }

  const activeDef = TABS.find((t) => t.id === activeTab) ?? CLAUDE_DESKTOP;
  const snippet = activeDef.build(tool.tool_name, spawn, env, channel);

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

  const isGuiTab = activeDef.group === "GUI";
  const requiresEnv = Object.keys(env).length > 0;

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
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--app-muted)",
              }}
            >
              Install in your client
            </Typography>
            <Typography sx={{ fontSize: 13, color: "var(--app-muted)" }}>
              Pick your target — GUI client, terminal, or SDK — and copy the
              snippet.
            </Typography>
          </Box>
          <Chip
            size="small"
            label={
              tool.upstream_ref?.channel
                ? `${tool.upstream_ref.channel} · ${tool.upstream_ref.identifier}`
                : (tool.upstream_ref?.identifier ?? "")
            }
            sx={{
              fontFamily:
                "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: 11,
              bgcolor: "var(--app-control-bg)",
              color: "var(--app-muted)",
              border: "1px solid var(--app-border)",
              maxWidth: { xs: 240, sm: 360 },
            }}
          />
        </Box>

        {requiresEnv ? (
          <Alert
            severity="info"
            sx={{
              mb: 1.5,
              fontSize: 12,
              "& .MuiAlert-message": { width: "100%" },
            }}
          >
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center" }}>
              <Box component="span" sx={{ fontWeight: 700, mr: 0.5 }}>
                Required env vars:
              </Box>
              {Object.keys(env).map((k) => (
                <Chip
                  key={k}
                  size="small"
                  label={k}
                  sx={{
                    fontFamily:
                      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                    fontSize: 11,
                    height: 20,
                    bgcolor: "var(--app-surface)",
                    border: "1px solid var(--app-border)",
                  }}
                />
              ))}
            </Box>
            <Box sx={{ mt: 0.5, color: "var(--app-muted)" }}>
              The snippets below pre-fill these as placeholders — replace with
              real values before launching the server, or it will fail at
              startup.
            </Box>
          </Alert>
        ) : null}

        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v as SnippetTabId)}
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
          {snippet.applicable ? (
            <>
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
            </>
          ) : (
            <Box
              sx={{
                p: 2,
                border: "1px dashed var(--app-border)",
                borderRadius: 2,
                bgcolor: "var(--app-control-bg)",
                color: "var(--app-muted)",
                fontSize: 12.5,
                lineHeight: 1.6,
              }}
            >
              <Box component="span" sx={{ fontWeight: 700, mr: 0.5 }}>
                Not applicable.
              </Box>
              {snippet.disabledReason}
            </Box>
          )}
        </Box>

        {snippet.applicable ? (
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

            {isGuiTab && snippet.configPath ? (
              <Box sx={{ display: "grid", gap: 0.75 }}>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    flexWrap: "wrap",
                  }}
                >
                  <Box
                    component="span"
                    sx={{
                      fontWeight: 700,
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                      fontSize: 11,
                      color: "var(--app-muted)",
                    }}
                  >
                    OS
                  </Box>
                  <ToggleButtonGroup
                    size="small"
                    exclusive
                    value={os}
                    onChange={(_, v: OsKey | null) => {
                      if (v) setOs(v);
                    }}
                    sx={{
                      "& .MuiToggleButton-root": {
                        textTransform: "none",
                        fontSize: 11,
                        fontWeight: 600,
                        py: 0.25,
                        px: 1,
                        color: "var(--app-muted)",
                        borderColor: "var(--app-border)",
                        "&.Mui-selected": {
                          color: "var(--app-fg)",
                          bgcolor: "var(--app-control-active-bg)",
                          borderColor: "var(--app-accent)",
                        },
                      },
                    }}
                  >
                    <ToggleButton value="mac">macOS</ToggleButton>
                    <ToggleButton value="windows">Windows</ToggleButton>
                    <ToggleButton value="linux">Linux</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
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
                    Config file
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
                      wordBreak: "break-all",
                    }}
                  >
                    {snippet.configPath[os]}
                  </Box>
                </Box>
              </Box>
            ) : null}
          </Box>
        ) : null}

        {channel === "http" ? (
          <Alert severity="info" sx={{ mt: 1.5, fontSize: 12 }}>
            HTTP MCP servers use the{" "}
            <Box
              component="code"
              sx={{
                fontFamily:
                  "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: 11.5,
              }}
            >
              {spawn.transport ?? "streamable-http"}
            </Box>{" "}
            transport. If the upstream requires authentication, check the
            publisher&apos;s documentation — clients support per-server
            bearer tokens (Cursor, Cline) and header injection (Continue)
            but don&apos;t auto-discover credentials.
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
