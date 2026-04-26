import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function buildHeaders(): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(cookieHeader ? { cookie: cookieHeader } : {}),
  };
}

function url(clientId: string): string {
  const base = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  return `${base}/registry/clients/${encodeURIComponent(clientId)}/tokens`;
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await context.params;
  const headers = await buildHeaders();
  const res = await fetch(url(clientId), {
    method: "GET",
    headers,
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return NextResponse.json(payload, { status: res.status });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await context.params;
  const body = await request.json().catch(() => ({}));
  const headers = await buildHeaders();
  const res = await fetch(url(clientId), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await res.json().catch(() => ({}));
  return NextResponse.json(payload, { status: res.status });
}
