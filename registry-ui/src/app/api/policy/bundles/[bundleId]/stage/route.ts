import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ bundleId: string }> },
) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
  const { bundleId } = await context.params;

  const backendResponse = await fetch(
    `${backendBase}/registry/policy/bundles/${encodeURIComponent(bundleId)}/stage`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: JSON.stringify(body),
    },
  );

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}
