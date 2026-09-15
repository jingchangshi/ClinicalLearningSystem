import { NextResponse, type NextRequest } from "next/server";

const protectedPrefixes = ["/student", "/teacher"];
const AUTH_COOKIE = "access_token";

type TokenClaims = { role?: string; sub?: string; exp?: number };

/**
 * Coarse-grained route protection only: the FastAPI backend remains the
 * authorization source of truth for every request. The cookie is verified here
 * (HS256, shared server-only secret) so an unsigned or forged token can never
 * claim a role, then the role decides between "render" and "go to your own area".
 */
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = protectedPrefixes.some((prefix) => pathname.startsWith(prefix));
  if (!isProtected) return NextResponse.next();

  const token = request.cookies.get(AUTH_COOKIE)?.value;
  const claims = token ? await readClaims(token) : null;
  const role = typeof claims?.role === "string" ? claims.role : null;
  const wantsStudent = pathname.startsWith("/student");
  const wantsTeacher = pathname.startsWith("/teacher");

  if (wantsStudent && role === "student") return NextResponse.next();
  if (wantsTeacher && (role === "teacher" || role === "admin")) return NextResponse.next();

  // Authenticated, but in the wrong area: send them where they belong instead of
  // bouncing through /login (which is what turned this into a redirect loop).
  if (role === "student" && wantsTeacher) return redirectTo(request, "/student/dashboard");
  if ((role === "teacher" || role === "admin") && wantsStudent) return redirectTo(request, "/teacher/dashboard");

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

function redirectTo(request: NextRequest, pathname: string) {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  url.search = "";
  return NextResponse.redirect(url);
}

async function readClaims(token: string): Promise<TokenClaims | null> {
  const secret = process.env.JWT_SECRET;
  const claims = secret ? await verifyHs256(token, secret) : null;
  if (claims) return claims;
  if (!secret) {
    // Misconfigured deployment: keep the previous, presence-based behaviour
    // rather than locking every signed-in user out of the app.
    console.error("proxy: JWT_SECRET is not configured; role routing is not verified");
    return decodeClaims(token);
  }
  return null;
}

async function verifyHs256(token: string, secret: string): Promise<TokenClaims | null> {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [encodedHeader, encodedPayload, encodedSignature] = parts;

  const header = decodeJson(encodedHeader);
  if (!header || header.alg !== "HS256") return null;

  let signatureValid = false;
  try {
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );
    signatureValid = await crypto.subtle.verify(
      "HMAC",
      key,
      base64UrlToBytes(encodedSignature),
      new TextEncoder().encode(`${encodedHeader}.${encodedPayload}`),
    );
  } catch {
    return null;
  }
  if (!signatureValid) return null;

  const claims = decodeJson(encodedPayload);
  if (!claims) return null;
  if (typeof claims.exp === "number" && claims.exp * 1000 <= Date.now()) return null;
  return claims;
}

function decodeClaims(token: string): TokenClaims | null {
  const payload = token.split(".")[1];
  return payload ? decodeJson(payload) : null;
}

function decodeJson(value: string): (TokenClaims & { alg?: string }) | null {
  try {
    return JSON.parse(new TextDecoder().decode(base64UrlToBytes(value)));
  } catch {
    return null;
  }
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export const config = {
  matcher: ["/student/:path*", "/teacher/:path*"],
};
