import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Silence the multi-lockfile warning: pin Turbopack to the dashboard root.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
