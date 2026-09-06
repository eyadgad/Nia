import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Keep framework-generated AI instruction files out of the source tree.
  agentRules: false,
};

export default nextConfig;
