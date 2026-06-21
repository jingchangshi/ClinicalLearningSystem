import { NextResponse, type NextRequest } from "next/server";

const protectedPrefixes = ["/student", "/teacher"];

export function proxy(request: NextRequest) {
  const isProtected = protectedPrefixes.some((prefix) => request.nextUrl.pathname.startsWith(prefix));
  if (!isProtected) return NextResponse.next();
  const token = request.cookies.get("access_token")?.value;
  const role = token ? tokenRole(token) : null;
  if (request.nextUrl.pathname.startsWith("/student") && role === "student") return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/teacher") && (role === "teacher" || role === "admin")) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

function tokenRole(token: string): string | null {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(atob(normalized));
    return typeof decoded.role === "string" ? decoded.role : null;
  } catch {
    return null;
  }
}

export const config = {
  matcher: ["/student/:path*", "/teacher/:path*"],
};
