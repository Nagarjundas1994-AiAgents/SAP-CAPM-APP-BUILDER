/** @type {import('next').NextConfig} */
const nextConfig = {
  trailingSlash: true,
  skipTrailingSlashRedirect: true, // Prevents POST → GET redirect on API routes
  images: {
    unoptimized: true,
  },
  // Extend proxy timeout for long-running LLM calls (chat, generation)
  httpAgentOptions: {
    keepAlive: true,
  },
  // API calls go to the FastAPI backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
  // Allow long-running server actions (2 min for LLM chat calls)
  serverRuntimeConfig: {
    apiTimeout: 120000,
  },
};

module.exports = nextConfig;
