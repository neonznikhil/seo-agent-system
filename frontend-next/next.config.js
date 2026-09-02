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
    const backendUrl =
      process.env.BACKEND_URL?.replace(/\/api\/?$/, "") ||
      (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.startsWith("/")
        ? process.env.NEXT_PUBLIC_API_URL.replace(/\/api\/?$/, "")
        : "") ||
      "https://rankforge-backend.onrender.com";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
