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

// Proxy the API through this origin when a backend is configured, so the session cookie is
// first-party. Served cross-origin it is a third-party cookie: the browser takes the login
// response, declines to store the cookie, and the next request is anonymous -- login appears
// to succeed and the app immediately reports the session expired. SameSite=None does not
// help; modern tracking prevention blocks it anyway.
const backendOrigin = process.env.BACKEND_ORIGIN?.replace(/\/$/, "");

if (backendOrigin) {
  nextConfig.rewrites = async () => [
    { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
    { source: "/health", destination: `${backendOrigin}/health` },
  ];
}

export default nextConfig;
