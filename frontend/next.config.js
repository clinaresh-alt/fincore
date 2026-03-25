/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy API calls to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
  // Webpack config para resolver modulos de wallet connectors
  webpack: (config, { isServer }) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      net: false,
      tls: false,
      crypto: false,
    };

    // Externals que no contienen @ (estos funcionan con push)
    config.externals.push("pino-pretty", "lokijs", "encoding");

    // Para modulos con @ en el nombre, usar resolve.alias con un modulo vacio
    config.resolve.alias = {
      ...config.resolve.alias,
      "@react-native-async-storage/async-storage": require.resolve(
        "./src/lib/empty-module.js"
      ),
    };

    return config;
  },
};

module.exports = nextConfig;
