import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output is what infra/docker-compose builds against: the Dockerfile copies
  // .next/standalone and runs it directly. Vercel builds its own output and chokes on this
  // one -- it looks for trace files standalone mode does not leave behind -- so the setting
  // stands down there. VERCEL=1 is set by their builder, not by us.
  output: process.env.VERCEL ? undefined : "standalone",
  // Keep framework-generated AI instruction files out of the source tree.
  agentRules: false,
};

export default nextConfig;
