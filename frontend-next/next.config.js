/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  poweredByHeader: false,
  async redirects() {
    return [
      {
        source: "/workforce",
        destination: "/crew",
        permanent: true,
      },
      {
        source: "/wordpress",
        destination: "/connectors",
        permanent: true,
      },
      {
        source: "/settings",
        destination: "/connectors",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://seo-agent-system-production.up.railway.app:8080/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
