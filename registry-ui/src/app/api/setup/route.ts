import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

export async function POST(request: NextRequest) {
  const backendBase = process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
  const body = await request.json();

  const backendResponse = await fetch(`${backendBase}/registry/setup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
    redirect: "manual",
  });

  const setCookie = backendResponse.headers.get("set-cookie");
  const payload = await backendResponse.json().catch(() => ({}));

  const response = NextResponse.json(payload, {
    status: backendResponse.status,
  });

  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }

  return response;
}
