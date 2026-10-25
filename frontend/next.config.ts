import type { NextConfig } from "next";
import { resolve } from "node:path";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // FastAPI collection routes end in '/'; preserve them through the API proxy.
  skipTrailingSlashRedirect: true,
  turbopack: {
    root: resolve(__dirname),
  },
  async rewrites() {
    return [
      // A catch-all rewrite drops an empty trailing segment. Pin collection
      // roots to their canonical URL so FastAPI does not redirect off-origin.
      ...["tenants", "exams"].flatMap((collection) =>
        ["", "/"].map((suffix) => ({
          source: `/backend/api/v1/${collection}${suffix}`,
          destination: `${backendUrl.replace(/\/$/, "")}/api/v1/${collection}/`,
        })),
      ),
      {
        source: "/backend/:path*",
        destination: `${backendUrl.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
};

export default nextConfig;
