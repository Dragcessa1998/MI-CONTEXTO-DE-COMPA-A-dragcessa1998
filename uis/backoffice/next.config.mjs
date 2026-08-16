import path from "node:path";
import { fileURLToPath } from "node:url";

const workspaceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

const securityHeaders = [
  { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https: wss: http://localhost:8000 ws://localhost:8000 http://127.0.0.1:8000 ws://127.0.0.1:8000; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { root: workspaceRoot },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
  async rewrites() {
    const platformApiInternalUrl =
      process.env.PLATFORM_API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    const talentApiInternalUrl =
      process.env.TALENT_API_INTERNAL_URL ?? "http://127.0.0.1:4000";

    return [
      {
        source: "/platform-api/:path*",
        destination: `${platformApiInternalUrl}/:path*`,
      },
      {
        source: "/talent-api/:path*",
        destination: `${talentApiInternalUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
