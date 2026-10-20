import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  // job ids live in /counsel/<id> URLs; don't hand them to other sites via Referer
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  // the photo flow uses <input capture>, which needs no camera permission
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

// One-container deploy (Dockerfile): the browser talks only to this Next server, which proxies /api to the FastAPI
// backend on the same machine. Same origin, so the HttpOnly session cookie stays first-party and CORS is not needed.
// Read at build time; local dev leaves it unset and calls the backend directly (NEXT_PUBLIC_API_URL).
const internalApi = process.env.AIN_INTERNAL_API;

const nextConfig: NextConfig = {
  cacheComponents: true,
  // demos are often run with `npm run dev`; keep the floating dev badge off the screen
  devIndicators: false,
  partialPrefetching: true,
  // gzip would buffer the proxied server-sent events of a running analysis; the host compresses static files anyway
  compress: !internalApi,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return internalApi ? { beforeFiles: [{ source: "/api/:path*", destination: `${internalApi}/api/:path*` }], afterFiles: [], fallback: [] } : [];
  },
};

export default nextConfig;
