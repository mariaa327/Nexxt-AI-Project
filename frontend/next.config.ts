import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle for the Docker image (see frontend/Dockerfile).
  output: "standalone",
  // The backend is a separate FastAPI service; the browser talks to it directly
  // through NEXT_PUBLIC_API_URL, so no rewrites are needed here.
  poweredByHeader: false,
};

export default nextConfig;
