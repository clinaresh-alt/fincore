/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // OPTIMIZACIONES DE RENDIMIENTO
  experimental: {
    // Optimizar imports de paquetes pesados
    optimizePackageImports: [
      "lucide-react",
      "recharts",
      "framer-motion",
      "date-fns",
      "@radix-ui/react-icons",
    ],
  },

  // Comprimir respuestas
  compress: true,

  // Reducir tamaño de source maps en produccion
  productionBrowserSourceMaps: false,

  // Proxy API calls to backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },

  // Headers de cache para assets estaticos
  async headers() {
    return [
      {
        source: '/:all*(svg|jpg|png|woff|woff2)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
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

    // Optimizar chunks para mejor caching
    if (!isServer) {
      config.optimization = {
        ...config.optimization,
        splitChunks: {
          ...config.optimization.splitChunks,
          cacheGroups: {
            ...config.optimization.splitChunks?.cacheGroups,
            // Separar wagmi/viem en su propio chunk
            web3: {
              test: /[\\/]node_modules[\\/](wagmi|viem|@rainbow-me)[\\/]/,
              name: 'web3-vendors',
              chunks: 'all',
              priority: 20,
            },
            // Separar recharts
            charts: {
              test: /[\\/]node_modules[\\/](recharts|d3-.*)[\\/]/,
              name: 'charts-vendors',
              chunks: 'all',
              priority: 15,
            },
          },
        },
      };
    }

    return config;
  },
};

module.exports = nextConfig;
