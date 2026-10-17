import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  // demos are often run with `npm run dev`; keep the floating dev badge off the screen
  devIndicators: false,
  partialPrefetching: true,
};

export default nextConfig;
