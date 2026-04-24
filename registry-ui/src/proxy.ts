import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PUBLIC_ONLY = process.env.PUBLIC_REGISTRY_ONLY === "true";

function isAllowedPath(pathname: string): boolean {
  if (!PUBLIC_ONLY) return true;

  // Always allow Next internals + static assets.
  if (pathname.startsWith("/_next")) return true;
  if (pathname === "/favicon.ico") return true;
  if (pathname.startsWith("/assets")) return true;

  // Public registry app.
  if (pathname === "/public" || pathname.startsWith("/public/")) return true;

  // Let root show a clean redirect page (or be handled by routing).
  if (pathname === "/") return true;

  // Everything else is console/API and should not be served from the public container.
  return false;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isAllowedPath(pathname)) {
    return NextResponse.next();
  }

  // Default: send users back to the public landing page.
  const url = request.nextUrl.clone();
  url.pathname = "/public/tools";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/:path*"],
};

