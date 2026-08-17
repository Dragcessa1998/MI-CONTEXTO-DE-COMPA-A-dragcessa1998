/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const platformApiInternalUrl =
      process.env.PLATFORM_API_INTERNAL_URL ?? "http://127.0.0.1:8000";

    return [
      {
        source: "/platform-api/:path*",
        destination: `${platformApiInternalUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
