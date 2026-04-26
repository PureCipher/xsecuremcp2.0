import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

/**
 * Proxy for the registry's curator-onboarding introspect step.
 *
 * The Python registry boots the upstream MCP server and runs
 * tools/list, resources/list, prompts/list against it, returning a
 * structured capability surface plus the registry's draft permission
 * suggestions. Can take up to ~15s upstream-side; the Next.js fetch
 * has no timeout so the wizard can render a spinner for the full
 * window.
 */
export async function POST(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const upstream = await fetch(`${backendBase}/registry/curate/introspect`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const payload = await upstream.json().catch(() => ({}));
  return NextResponse.json(payload, { status: upstream.status });
}
