const DEFAULT_BACKEND = "http://localhost:8000";

export function registryBackendBase(): string {
  const raw = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND;
  return raw.replace(/\/+$/, "");
}

export function defaultRegistryMcpUrl(): string {
  return `${registryBackendBase()}/mcp`;
}

export function allowedRegistryOrigin(): string {
  return new URL(registryBackendBase()).origin;
}

/** Prevent SSRF: only the configured registry origin may be contacted from the UI terminal. */
export function assertMcpUrlAllowed(mcpUrl: string, allowedOrigin: string): URL {
  let u: URL;
  try {
    u = new URL(mcpUrl);
  } catch {
    throw new Error("Invalid MCP URL.");
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    throw new Error("Only http(s) MCP URLs are supported (stdio / local paths are not available in this terminal).");
  }
  if (u.origin !== allowedOrigin) {
    throw new Error(
      `Origin ${u.origin} is not allowed. Use your registry MCP URL on ${allowedOrigin} (REGISTRY_BACKEND_URL).`,
    );
  }
  return u;
}
