import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  basePath: '/webview',
  reactStrictMode: true,
  experimental: {
    staleTimes: {
      dynamic: 0,  // Disable dynamic route cache
      static: 0,   // Disable static route cache
    },
  },
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: '**',
      },
    ],
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/webview',
        permanent: false,
        basePath: false
      }
    ];
  },
};

export default nextConfig;
