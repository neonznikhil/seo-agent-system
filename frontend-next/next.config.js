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
    // Accept either env name. Route handlers prefer BACKEND_URL while the public
    // client uses NEXT_PUBLIC_API_URL; using only the latter silently disabled
    // the rewrite whenever a deployment set just BACKEND_URL.
    const backendBase = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    if (!backendBase) {
      return [];
    }
    const backendWithApi = backendBase.endsWith("/api") ? backendBase : `${backendBase}/api`;
    return [
      {
        source: "/api/:path*",
        destination: `${backendWithApi}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
