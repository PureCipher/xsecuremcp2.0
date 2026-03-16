import { cookies } from "next/headers";

const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendBase() {
  return process.env.REGISTRY_BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

async function backendFetch(path: string, init?: RequestInit) {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("purecipher_registry_token");

  const headers: HeadersInit = {
    Accept: "application/json",
    ...(init?.headers ?? {}),
  };

  if (sessionCookie) {
    headers.cookie = `${sessionCookie.name}=${sessionCookie.value}`;
  }

  const response = await fetch(`${backendBase()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  return response;
}

export async function getRegistrySession(): Promise<any | null> {
  const response = await backendFetch("/registry/session");
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function listVerifiedTools(): Promise<any | null> {
  const response = await backendFetch("/registry/tools");
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function getToolDetail(toolName: string): Promise<any | null> {
  const response = await backendFetch(`/registry/tools/${encodeURIComponent(toolName)}`);
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function getInstallRecipes(toolName: string): Promise<any | null> {
  const response = await backendFetch(`/registry/install/${encodeURIComponent(toolName)}`);
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function listPublishers(): Promise<any | null> {
  const response = await backendFetch("/registry/publishers");
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function getPublisherProfile(publisherId: string): Promise<any | null> {
  const response = await backendFetch(`/registry/publishers/${encodeURIComponent(publisherId)}`);
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function getReviewQueue(): Promise<any | null> {
  const response = await backendFetch("/registry/review/submissions");
  if (!response.ok) {
    return response.json().catch(() => null);
  }
  return response.json().catch(() => null);
}

export async function requirePublisherRole(): Promise<{ allowed: boolean; role: string | null }> {
  const session = await getRegistrySession();
  const role = session?.session?.role ?? null;
  const allowed = role === "publisher" || role === "reviewer" || role === "admin";
  return { allowed, role };
}

export async function getRegistryHealth(): Promise<any | null> {
  const response = await backendFetch("/registry/health");
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

export async function verifyTool(toolName: string): Promise<any | null> {
  const response = await backendFetch("/registry/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ tool_name: toolName }),
  });
  if (!response.ok) {
    return null;
  }
  return response.json().catch(() => null);
}

