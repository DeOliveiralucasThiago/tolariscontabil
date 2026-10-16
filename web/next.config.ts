import type { NextConfig } from "next";

// Em desenvolvimento e no container, o Next encaminha /api/* para o FastAPI.
// Assim navegador e API ficam na mesma origem e o cookie de sessão (httpOnly) funciona.
const API_URL = process.env.TOLARIS_API_URL ?? "http://127.0.0.1:8000";

// Cabeçalhos de segurança do site. Sem CSP de scripts: o Next precisa de scripts embutidos; o resto trava
// o que não precisa: ser aberto dentro de outro site, plugins, formulários para fora e acesso a câmera, microfone e local.
const CABECALHOS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: CABECALHOS }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
