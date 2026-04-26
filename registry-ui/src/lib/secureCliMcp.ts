import { Client } from "@modelcontextprotocol/sdk/client";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

import { assertMcpUrlAllowed, registryBackendBase } from "@/lib/secureCliOrigin";
import { shellSplit } from "@/lib/shellSplit";

export type CliExecResult = { ok: true; output: string } | { ok: false; error: string };

function looksLikeHttpMcpUrl(token: string): boolean {
  return token.startsWith("http://") || token.startsWith("https://");
}

function helpText(defaultMcp: string): string {
  return [
    "━━━ SecureMCP web CLI ━━━",
    "In-browser MCP client for this registry. Same mental model as `securemcp` / `fastmcp`,",
    "but only streamable HTTP to your configured registry origin.",
    "",
    "── Quick start (default MCP URL is already set) ──",
    `  list                          → list tools on ${defaultMcp}`,
    "  list --prompts                → include MCP prompts",
    "  list --resources --prompts    → tools + resources + prompts",
    "  call <tool>                   → call a tool (uses default MCP URL)",
    "  call <name> --prompt a=b     → render a prompt",
    "",
    "── Full forms (optional explicit URL) ──",
    "  securemcp list [<mcp-url>] [--prompts] [--resources] [--json]",
    "  securemcp call [<mcp-url>] <target> [--prompt] [key=value ...] [--input-json '{...}']",
    "  • If you skip <mcp-url>, this UI uses the default below.",
    "  • If the first arg after `call` is http(s), it is treated as the MCP URL.",
    "",
    "── Admin only (requires admin session) ──",
    "  admin status                 → session + registry health summary",
    "  admin health                 → registry health JSON",
    "  admin queue                  → moderation queue counts",
    "  admin policy                 → policy management snapshot",
    "  admin activity               → recent account activity for the admin",
    "",
    `Default MCP URL: ${defaultMcp}`,
    "",
    "── Help & aliases ──",
    "  help | ? | commands           This screen",
    "  securemcp help | fastmcp help | --help | -h",
    "  fastmcp …                    Same as securemcp …",
    "",
    "── Target rules for `call` ──",
    "  • name with ://              → read_resource (e.g. file://…, https://…)",
    "  • --prompt                   → prompts/get",
    "  • otherwise                  → tools/call",
    "",
    "── Examples ──",
    "  list --json",
    "  admin status",
    `  securemcp list ${defaultMcp} --prompts`,
    "  call registry_status",
    "  call my_prompt --prompt topic=SecureMCP",
    "",
    "── Security & session ──",
    "  • Only http(s) on this registry’s origin (SSRF-safe).",
    "  • Your login cookie is forwarded to MCP when the host matches.",
    "  • Admin commands are served by the registry REST API and require role=admin.",
    "",
    "── Not available here ──",
    "  stdio (`server.py`), `run`, `install`, OAuth browser flows → use local `securemcp` CLI.",
    "",
  ].join("\n");
}

function backendHeaders(cookieHeader: string | null): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (cookieHeader) headers.set("cookie", cookieHeader);
  return headers;
}

async function fetchRegistryJson(path: string, cookieHeader: string | null): Promise<unknown> {
  const response = await fetch(`${registryBackendBase()}${path}`, {
    headers: backendHeaders(cookieHeader),
    cache: "no-store",
  });
  const payload = (await response.json().catch(() => null)) as unknown;
  if (!response.ok) {
    const error =
      payload && typeof payload === "object" && "error" in payload
        ? String((payload as { error?: unknown }).error)
        : `Registry request failed with ${response.status}`;
    throw new Error(error);
  }
  return payload;
}

async function requireAdminSession(cookieHeader: string | null): Promise<Record<string, unknown>> {
  const payload = await fetchRegistryJson("/registry/session", cookieHeader);
  if (!payload || typeof payload !== "object") {
    throw new Error("Unable to read registry session.");
  }
  const session = (payload as { session?: unknown }).session;
  if (!session || typeof session !== "object") {
    throw new Error("Admin command requires sign-in.");
  }
  const role = (session as { role?: unknown }).role;
  if (role !== "admin") {
    throw new Error("Admin command requires role=admin.");
  }
  return session as Record<string, unknown>;
}

function formatJson(payload: unknown): string {
  return `${JSON.stringify(payload, null, 2)}\n`;
}

function formatStatus(session: Record<string, unknown>, health: unknown): string {
  const h = health && typeof health === "object" ? (health as Record<string, unknown>) : {};
  return [
    "Admin session",
    `  user: ${String(session.username ?? "unknown")}`,
    `  role: ${String(session.role ?? "unknown")}`,
    `  display: ${String(session.display_name ?? session.username ?? "unknown")}`,
    "",
    "Registry health",
    `  status: ${String(h.status ?? "unknown")}`,
    `  auth: ${String(h.auth_enabled ?? "unknown")}`,
    `  bootstrap_required: ${String(h.bootstrap_required ?? "unknown")}`,
    `  verified_tools: ${String(h.verified_tools ?? "unknown")}`,
    `  pending_review: ${String(h.pending_review ?? "unknown")}`,
    `  minimum_certification: ${String(h.minimum_certification ?? "unknown")}`,
    "",
  ].join("\n");
}

function formatQueue(payload: unknown): string {
  const queue = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  const counts = queue.counts && typeof queue.counts === "object" ? (queue.counts as Record<string, unknown>) : {};
  return [
    "Moderation queue",
    `  pending_review: ${String(counts.pending_review ?? 0)}`,
    `  approved: ${String(counts.approved ?? 0)}`,
    `  rejected: ${String(counts.rejected ?? 0)}`,
    `  suspended: ${String(counts.suspended ?? 0)}`,
    "",
  ].join("\n");
}

function formatPolicy(payload: unknown): string {
  const policy = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  const status = policy.status && typeof policy.status === "object" ? (policy.status as Record<string, unknown>) : {};
  const versions = Array.isArray(policy.versions) ? policy.versions : [];
  const proposals = Array.isArray(policy.proposals) ? policy.proposals : [];
  return [
    "Policy snapshot",
    `  enabled: ${String(status.enabled ?? policy.enabled ?? "unknown")}`,
    `  mode: ${String(status.mode ?? policy.mode ?? "unknown")}`,
    `  versions: ${String(versions.length)}`,
    `  proposals: ${String(proposals.length)}`,
    "",
  ].join("\n");
}

async function runAdmin(subcommand: string | undefined, cookieHeader: string | null): Promise<string> {
  if (!subcommand || subcommand === "help") {
    return [
      "Admin commands",
      "  admin status     session + registry health summary",
      "  admin health     registry health JSON",
      "  admin queue      moderation queue counts",
      "  admin policy     policy management snapshot",
      "  admin activity   recent account activity for the admin",
      "",
    ].join("\n");
  }

  const session = await requireAdminSession(cookieHeader);
  if (subcommand === "status") {
    const health = await fetchRegistryJson("/registry/health", cookieHeader);
    return formatStatus(session, health);
  }
  if (subcommand === "health") {
    return formatJson(await fetchRegistryJson("/registry/health", cookieHeader));
  }
  if (subcommand === "queue") {
    return formatQueue(await fetchRegistryJson("/registry/review/submissions", cookieHeader));
  }
  if (subcommand === "policy") {
    return formatPolicy(await fetchRegistryJson("/registry/policy", cookieHeader));
  }
  if (subcommand === "activity") {
    return formatJson(await fetchRegistryJson("/registry/me/activity?limit=12", cookieHeader));
  }
  throw new Error(`Unsupported admin command "${subcommand}". Try \`admin help\`.`);
}

/** Parse tokens after `list`: either [url?, ...flags] or [...flags] only. */
function parseListTail(tail: string[], defaultMcpUrl: string): { url: string; flags: Set<string> } {
  if (tail.length === 0) {
    return { url: defaultMcpUrl, flags: new Set() };
  }
  const [first, ...rest] = tail;
  if (looksLikeHttpMcpUrl(first!)) {
    const flags = new Set<string>();
    for (const f of rest) {
      if (!f.startsWith("--")) {
        throw new Error(
          `After the MCP URL, only flags are allowed (got "${f}"). Try: list --prompts`,
        );
      }
      flags.add(f);
    }
    return { url: first!, flags };
  }
  const flags = new Set<string>();
  for (const f of tail) {
    if (!f.startsWith("--")) {
      throw new Error(
        `Expected a flag (e.g. --prompts) or start with http(s) URL. Got "${f}". ` +
          `Tip: run plain \`list\` to use ${defaultMcpUrl}`,
      );
    }
    flags.add(f);
  }
  return { url: defaultMcpUrl, flags };
}

/** Parse tokens after `call`: [<url>, ]target, ...args */
function parseCallTail(
  tail: string[],
  defaultMcpUrl: string,
): { url: string; target: string; argTokens: string[] } {
  if (tail.length === 0) {
    throw new Error(
      "Missing target. Examples: `call registry_status`  or  `call my_prompt --prompt x=y`",
    );
  }
  const [first, ...rest] = tail;
  if (looksLikeHttpMcpUrl(first!)) {
    if (rest.length === 0) {
      throw new Error(
        "After the MCP URL, add a tool name, resource URI, or prompt. Example: `call <url> registry_status`",
      );
    }
    const [target, ...argTokens] = rest;
    return { url: first!, target: target!, argTokens };
  }
  const [target, ...argTokens] = tail;
  return { url: defaultMcpUrl, target: target!, argTokens };
}

async function withMcpClient(
  mcpUrl: string,
  allowedOrigin: string,
  cookieHeader: string | null,
  fn: (client: Client) => Promise<string>,
): Promise<string> {
  assertMcpUrlAllowed(mcpUrl, allowedOrigin);
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl), {
    requestInit: {
      headers: {
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      },
    },
  });
  const client = new Client({ name: "purecipher-registry-ui-cli", version: "0.1.0" }, { capabilities: {} });
  await client.connect(transport);
  try {
    return await fn(client);
  } finally {
    await transport.terminateSession().catch(() => {});
    await client.close();
  }
}

async function collectAllTools(client: Client) {
  const tools: Awaited<ReturnType<Client["listTools"]>>["tools"] = [];
  let cursor: string | undefined;
  do {
    const page = await client.listTools(cursor ? { cursor } : {});
    tools.push(...page.tools);
    cursor = page.nextCursor;
  } while (cursor);
  return tools;
}

async function collectAllPrompts(client: Client) {
  const prompts: Awaited<ReturnType<Client["listPrompts"]>>["prompts"] = [];
  let cursor: string | undefined;
  do {
    const page = await client.listPrompts(cursor ? { cursor } : {});
    prompts.push(...page.prompts);
    cursor = page.nextCursor;
  } while (cursor);
  return prompts;
}

async function collectAllResources(client: Client) {
  const resources: Awaited<ReturnType<Client["listResources"]>>["resources"] = [];
  let cursor: string | undefined;
  do {
    const page = await client.listResources(cursor ? { cursor } : {});
    resources.push(...page.resources);
    cursor = page.nextCursor;
  } while (cursor);
  return resources;
}

function parseKeyValueArgs(tokens: string[]): {
  kv: Record<string, string>;
  inputJson?: string;
  isPrompt: boolean;
} {
  const kv: Record<string, string> = {};
  let inputJson: string | undefined;
  let isPrompt = false;
  const rest = [...tokens];
  while (rest.length) {
    const t = rest.shift()!;
    if (t === "--prompt") {
      isPrompt = true;
      continue;
    }
    if (t === "--input-json") {
      const next = rest.shift();
      if (next === undefined) throw new Error("--input-json requires a value");
      inputJson = next;
      continue;
    }
    if (t.startsWith("--")) {
      throw new Error(`Unsupported flag: ${t}`);
    }
    const eq = t.indexOf("=");
    if (eq === -1) {
      throw new Error(`Expected key=value, got: ${t}`);
    }
    const key = t.slice(0, eq);
    const val = t.slice(eq + 1);
    kv[key] = val;
  }
  return { kv, inputJson, isPrompt };
}

function mergePromptArguments(kv: Record<string, string>, inputJson?: string): Record<string, string> {
  const out: Record<string, string> = { ...kv };
  if (inputJson !== undefined) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(inputJson);
    } catch {
      throw new Error("Invalid JSON for --input-json");
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      throw new Error("--input-json must be a JSON object");
    }
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      out[k] = typeof v === "string" ? v : JSON.stringify(v);
    }
  }
  return out;
}

function parseToolArguments(kv: Record<string, string>, inputJson?: string): Record<string, unknown> {
  const merged = mergePromptArguments(kv, inputJson);
  const args: Record<string, unknown> = {};
  for (const [k, raw] of Object.entries(merged)) {
    try {
      args[k] = JSON.parse(raw) as unknown;
    } catch {
      args[k] = raw;
    }
  }
  return args;
}

async function runList(
  mcpUrl: string,
  allowedOrigin: string,
  cookieHeader: string | null,
  flags: Set<string>,
): Promise<string> {
  const wantPrompts = flags.has("--prompts");
  const wantResources = flags.has("--resources");
  const asJson = flags.has("--json");

  return withMcpClient(mcpUrl, allowedOrigin, cookieHeader, async (client) => {
    const tools = await collectAllTools(client);
    const lines: string[] = [];

    if (asJson) {
      const payload: Record<string, unknown> = {
        tools: tools.map((t) => ({
          name: t.name,
          description: t.description,
          inputSchema: t.inputSchema,
        })),
      };
      if (wantResources) {
        const resources = await collectAllResources(client);
        payload.resources = resources.map((r) => ({
          uri: r.uri,
          name: r.name,
          description: r.description,
          mimeType: r.mimeType,
        }));
      }
      if (wantPrompts) {
        const prompts = await collectAllPrompts(client);
        payload.prompts = prompts.map((p) => ({
          name: p.name,
          description: p.description,
          arguments: p.arguments,
        }));
      }
      return `${JSON.stringify(payload, null, 2)}\n`;
    }

    lines.push(`Tools (${tools.length})`, "");
    if (!tools.length) lines.push("  (none)", "");
    for (const t of tools) {
      lines.push(`  ${t.name}`);
      if (t.description) lines.push(`    ${t.description}`);
      lines.push("");
    }

    if (wantResources) {
      const resources = await collectAllResources(client);
      lines.push(`Resources (${resources.length})`, "");
      if (!resources.length) lines.push("  (none)", "");
      for (const r of resources) {
        lines.push(`  ${r.uri}`);
        const desc = [r.name, r.description].filter(Boolean).join(" — ");
        if (desc) lines.push(`    ${desc}`);
        lines.push("");
      }
    }

    if (wantPrompts) {
      const prompts = await collectAllPrompts(client);
      lines.push(`Prompts (${prompts.length})`, "");
      if (!prompts.length) lines.push("  (none)", "");
      for (const p of prompts) {
        const argNames = (p.arguments ?? []).map((a) => a.name);
        const sig = argNames.length ? `(${argNames.join(", ")})` : "";
        lines.push(`  ${p.name}${sig}`);
        if (p.description) lines.push(`    ${p.description}`);
        lines.push("");
      }
    }

    return lines.join("\n");
  });
}

async function runCall(
  mcpUrl: string,
  target: string,
  allowedOrigin: string,
  cookieHeader: string | null,
  argTokens: string[],
): Promise<string> {
  const { kv, inputJson, isPrompt } = parseKeyValueArgs(argTokens);

  return withMcpClient(mcpUrl, allowedOrigin, cookieHeader, async (client) => {
    if (target.includes("://")) {
      const res = await client.readResource({ uri: target });
      return `${JSON.stringify(res, null, 2)}\n`;
    }

    if (isPrompt) {
      const args = mergePromptArguments(kv, inputJson);
      const pr = await client.getPrompt({ name: target, arguments: args });
      return `${JSON.stringify(pr, null, 2)}\n`;
    }

    const toolArgs = parseToolArguments(kv, inputJson);
    const tr = await client.callTool({ name: target, arguments: toolArgs });
    return `${JSON.stringify(tr, null, 2)}\n`;
  });
}

export async function executeSecureCliLine(
  line: string,
  options: {
    allowedOrigin: string;
    defaultMcpUrl: string;
    cookieHeader: string | null;
  },
): Promise<CliExecResult> {
  const trimmed = line.trim();
  if (!trimmed) return { ok: true, output: "" };

  const lower = trimmed.toLowerCase();
  if (lower === "help" || lower === "?" || lower === "h" || lower === "commands") {
    return { ok: true, output: helpText(options.defaultMcpUrl) };
  }

  const tokens = shellSplit(trimmed);
  const effective =
    tokens[0] === "list" || tokens[0] === "call" ? (["securemcp", ...tokens] as string[]) : tokens;

  const cmd = effective[0];
  if (cmd === "admin") {
    try {
      const out = await runAdmin(effective[1]?.toLowerCase(), options.cookieHeader);
      return { ok: true, output: out };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, error: msg };
    }
  }

  if (cmd !== "securemcp" && cmd !== "fastmcp") {
    return {
      ok: false,
      error: [
        "Unknown input. This terminal understands:",
        "  list [--prompts] [--resources] [--json]     (shortcut — default MCP URL)",
        "  call <tool|uri> [--prompt] [k=v …]          (shortcut)",
        "  admin status | health | queue | policy      (admin-only registry commands)",
        "  securemcp list | call …                     (same as above, optional explicit URL)",
        "  help | commands                              full reference",
      ].join("\n"),
    };
  }

  const sub = effective[1];
  const subLower = sub?.toLowerCase();
  if (subLower === "help" || subLower === "--help" || sub === "-h") {
    if (effective.length > 2) {
      return { ok: false, error: "Usage: securemcp help (no extra arguments)" };
    }
    return { ok: true, output: helpText(options.defaultMcpUrl) };
  }

  if (sub === undefined) {
    return {
      ok: false,
      error: [
        "Missing subcommand. Quick options:",
        "  list                    → tools on the default registry MCP endpoint",
        "  call <tool_name>        → invoke a tool",
        "  admin status            → admin-only registry status",
        "  securemcp help         → full command reference",
      ].join("\n"),
    };
  }

  if (sub === "list") {
    try {
      const { url, flags } = parseListTail(effective.slice(2), options.defaultMcpUrl);
      const out = await runList(url, options.allowedOrigin, options.cookieHeader, flags);
      return { ok: true, output: out };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, error: msg };
    }
  }

  if (sub === "call") {
    try {
      const { url, target, argTokens } = parseCallTail(effective.slice(2), options.defaultMcpUrl);
      const out = await runCall(url, target, options.allowedOrigin, options.cookieHeader, argTokens);
      return { ok: true, output: out };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, error: msg };
    }
  }

  return {
    ok: false,
    error: `Unsupported subcommand "${sub}". Try \`help\` or \`list\`.`,
  };
}
