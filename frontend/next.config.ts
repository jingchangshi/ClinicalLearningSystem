import type { NextConfig } from "next";

const apiBase = process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8100";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["129.153.118.58"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
