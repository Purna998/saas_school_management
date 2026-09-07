import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Simple, stable configuration
  reactStrictMode: true,

  // Webpack configuration (using --webpack flag for stability)
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
    }
    return config;
  },
};

export default nextConfig;
