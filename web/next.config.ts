import type { NextConfig } from "next";

// Em desenvolvimento e no container, o Next encaminha /api/* para o FastAPI.
// Assim navegador e API ficam na mesma origem e o cookie de sessão (httpOnly) funciona.
const API_URL = process.env.TOLARIS_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
