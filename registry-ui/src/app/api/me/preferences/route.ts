import type { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function proxyPreferences(method: "GET" | "PUT" | "DELETE", body?: unknown) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");

  const backendResponse = await fetch(`${backendBase}/registry/me/preferences`, {
    method,
    headers: {
      Accept: "application/json",
      ...(method === "PUT" ? { "Content-Type": "application/json" } : {}),
      ...(cookieHeader ? { cookie: cookieHeader } : {}),
    },
    ...(method === "PUT" ? { body: JSON.stringify(body ?? {}) } : {}),
    cache: "no-store",
  });

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}

export async function GET() {
  return proxyPreferences("GET");
}

export async function PUT(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  return proxyPreferences("PUT", body);
}

export async function DELETE() {
  return proxyPreferences("DELETE");
}
