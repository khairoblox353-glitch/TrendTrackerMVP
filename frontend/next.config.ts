import type { NextConfig } from "next";

/**
 * The dashboard is a server-rendered client of the FastAPI backend, so it needs no
 * image domains, no rewrites and no edge runtime. Keeping this file minimal is
 * deliberate: the frontend holds no business rules, only presentation (spec 19.9-19.10).
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Produces a self-contained server bundle so the runtime image does not need to
  // carry the whole node_modules tree.
  output: "standalone",
};

export default nextConfig;
