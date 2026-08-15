/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // The logo is served straight from /public unmodified; skip the optimizer
  // so it renders identically without the sharp pipeline.
  images: { unoptimized: true },
  async rewrites() {
    // Proxy /api to the backend in dev so the browser talks same-origin.
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
  async redirects() {
    // Chat is the landing screen. Handle "/" at the routing layer so it never
    // depends on a server-component redirect (robust across dev/prod/versions).
    return [{ source: "/", destination: "/chat", permanent: false }];
  },
};

export default nextConfig;
