import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function buildBackendHeaders(method: "GET" | "POST"): Promise<HeadersInit> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  return {
    Accept: "application/json",
    ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
    ...(cookieHeader ? { cookie: cookieHeader } : {}),
  };
}

export async function GET() {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const headers = await buildBackendHeaders("GET");

  const backendResponse = await fetch(`${backendBase}/registry/clients`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}

export async function POST(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));
  const headers = await buildBackendHeaders("POST");

  const backendResponse = await fetch(`${backendBase}/registry/clients`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}
