import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

async function cookieHeaderValue() {
  const cookieStore = await cookies();
  return cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
}

export async function GET(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const cookieHeader = await cookieHeaderValue();

  const url = new URL(request.url);
  const jurisdiction = url.searchParams.get("jurisdiction");
  const category = url.searchParams.get("category");

  const params = new URLSearchParams();
  if (jurisdiction) params.set("jurisdiction", jurisdiction);
  if (category) params.set("category", category);
  const qs = params.toString();

  const backendResponse = await fetch(
    `${backendBase}/registry/policy/plugins${qs ? `?${qs}` : ""}`,
    {
      headers: {
        Accept: "application/json",
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
      cache: "no-store",
    },
  );

  const payload = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(payload, { status: backendResponse.status });
}
