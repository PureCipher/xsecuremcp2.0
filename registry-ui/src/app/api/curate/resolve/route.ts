import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

/**
 * Proxy for the registry's curator-onboarding URL-resolve step.
 *
 * The browser hits this Next.js route so the curator's session cookie
 * stays inside the registry-ui origin; we forward the cookie to the
 * Python registry. Pre-existing route shape — same pattern as
 * ``/api/openapi/ingest``.
 */
export async function POST(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const upstream = await fetch(`${backendBase}/registry/curate/resolve`, {
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
