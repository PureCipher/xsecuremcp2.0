import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function buildHeaders(method: string): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
  return {
    Accept: "application/json",
    ...(method === "PATCH" || method === "POST"
      ? { "Content-Type": "application/json" }
      : {}),
    ...(cookieHeader ? { cookie: cookieHeader } : {}),
  };
}

function backendUrl(clientId: string): string {
  const base = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  return `${base}/registry/clients/${encodeURIComponent(clientId)}`;
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await context.params;
  const headers = await buildHeaders("GET");
  const res = await fetch(backendUrl(clientId), {
    method: "GET",
    headers,
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return NextResponse.json(payload, { status: res.status });
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await context.params;
  const body = await request.json().catch(() => ({}));
  const headers = await buildHeaders("PATCH");
  const res = await fetch(backendUrl(clientId), {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return NextResponse.json(payload, { status: res.status });
}
