import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  // Static export so the backend (Modal) can serve the dashboard from the same URL.
  output: "export",
};

export default nextConfig;
