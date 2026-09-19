import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // Static export so the backend (Modal) can serve the dashboard from the same URL.
  output: "export",
  // Emit /miniapp/index.html so the backend serves the Telegram Mini App at /miniapp/.
  trailingSlash: true,
};

export default nextConfig;
