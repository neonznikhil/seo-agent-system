/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Production optimizations
  compress: true,
  poweredByHeader: false,
  
  // Image optimization (uncomment if adding images later)
  // images: {
  //   remotePatterns: [
  //     { protocol: 'https', hostname: '**' },
  //   ],
  // },
  
  // Environment variables exposed to browser
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  
  // Redirects for clean URLs
  async redirects() {
    return [
      {
        source: '/dashboard',
        destination: '/',
        permanent: false,
      },
    ];
  },
};

module.exports = nextConfig;
