import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      // The dashboard lives at "/" — anyone typing /dashboard (the intuitive
      // URL) should land there instead of a 404.
      { source: "/dashboard", destination: "/", permanent: false },
    ];
  },
};

export default nextConfig;
