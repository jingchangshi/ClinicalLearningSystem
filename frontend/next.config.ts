import type { NextConfig } from "next";
import { execSync } from "node:child_process";

const apiBase = process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8100/api";
const backendOrigin = apiBase.endsWith("/api") ? apiBase.slice(0, -4) : apiBase;

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
  allowedDevOrigins: ["129.153.118.58"],
  env: {
    NEXT_PUBLIC_BUILD_SHA: buildSha(),
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
