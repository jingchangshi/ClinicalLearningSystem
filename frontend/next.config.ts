import type { NextConfig } from "next";
import { execSync } from "node:child_process";

const apiBase = process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8100/api";
const backendOrigin = apiBase.endsWith("/api") ? apiBase.slice(0, -4) : apiBase;

/**
 * When the pilot is published over HTTPS, anything that arrives through a
 * plain-HTTP proxy is bounced to the secure host. The header condition means
 * this only fires for requests that really came in over HTTP (the tunnel sets
 * `x-forwarded-proto`); a direct local `http://127.0.0.1:8101` request during
 * development has no such header and keeps working.
 */
const httpsHost = process.env.CLINPATH_HTTPS_HOST;

/**
 * Stamp the build with the source revision at build time, so the running
 * frontend can always be compared with the checkout — even if someone builds
 * with a bare `npm run build` instead of the service script.
 */
function buildSha(): string {
  const provided = process.env.NEXT_PUBLIC_BUILD_SHA;
  if (provided) return provided;
  try {
    const sha = execSync("git rev-parse --short HEAD", { cwd: __dirname, encoding: "utf8" }).trim();
    const dirty = execSync("git status --porcelain", { cwd: __dirname, encoding: "utf8" }).trim();
    return `${sha}${dirty ? "-dirty" : ""}`;
  } catch {
    return "unknown";
  }
}

const nextConfig: NextConfig = {
  // Lets a disposable/test deployment build beside the production build instead
  // of overwriting the `.next` directory the running service serves.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  allowedDevOrigins: ["129.153.118.58", "clinpath.1031989.xyz"],
  env: {
    NEXT_PUBLIC_BUILD_SHA: buildSha(),
  },
  experimental: {
    // Rewrite-proxied requests are aborted after 30s by default
    // (next/dist/server/lib/router-utils/proxy-request.js). A real DeepSeek
    // Thinking-Mode case evaluation measured 15-25s, so the browser received a
    // 500 for a submit whose work the backend had already completed. The backend
    // bounds itself (LLM_TIMEOUT_SECONDS x (LLM_MAX_RETRIES + 1)); the proxy must
    // not be the layer that decides a model-backed request failed.
    proxyTimeout: 300_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
  async redirects() {
    if (!httpsHost) return [];
    return [
      {
        source: "/:path*",
        has: [{ type: "header", key: "x-forwarded-proto", value: "http" }],
        destination: `https://${httpsHost}/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
