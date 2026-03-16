import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ listingId: string; action: string }> },
) {
  const { listingId, action } = await context.params;
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json().catch(() => ({}));

  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();
  const cookieHeader = allCookies.map((c) => `${c.name}=${c.value}`).join("; ");

  const backendResponse = await fetch(
    `${backendBase}/registry/review/${encodeURIComponent(listingId)}/${encodeURIComponent(action)}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      body: JSON.stringify(body),
      redirect: "manual",
    },
  );

  const payload = await backendResponse.json().catch(() => ({}));

  return NextResponse.json(payload, { status: backendResponse.status });
}

