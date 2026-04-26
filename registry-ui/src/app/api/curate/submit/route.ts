import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

/**
 * Proxy for the registry's curator-onboarding submit step.
 *
 * The registry re-runs introspection at submit time so the manifest
 * always reflects what the registry currently observes — not whatever
 * the wizard captured earlier. The curator's selected_permissions
 * list is reconciled against the fresh introspection; scopes that
 * aren't in the suggestion list are silently dropped (confirm-or-
 * remove-only contract).
 */
export async function POST(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));

  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const upstream = await fetch(`${backendBase}/registry/curate/submit`, {
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
