import { create } from "zustand";
import { persist } from "zustand/middleware";

// Tipos de configuracion
export interface BlockchainConfig {
  // WalletConnect
  walletConnectProjectId: string;

  // Contratos desplegados
  investmentContract: string;
  kycContract: string;
  dividendsContract: string;
  tokenFactoryContract: string;

  // RPC URLs por red
  rpcUrls: {
    polygon: string;
    ethereum: string;
    arbitrum: string;
    base: string;
    polygonAmoy: string;
    sepolia: string;
  };

  // Block Explorer API Keys
  explorerApiKeys: {
    polygonscan: string;
    etherscan: string;
    arbiscan: string;
    basescan: string;
  };

  // Red por defecto
  defaultNetwork: "polygon" | "ethereum" | "arbitrum" | "base";

  // Modo (testnet/mainnet)
  isTestnet: boolean;
}

export interface SystemConfig {
  // General
  appName: string;
  appVersion: string;
  debugMode: boolean;

  // API
  apiUrl: string;
  apiTimeout: number;

  // Limites
  maxUploadSize: number; // MB
  sessionTimeout: number; // minutos

  // Compliance
  kycRequired: boolean;
  minInvestment: number;
  maxInvestment: number;
}

interface ConfigState {
  blockchain: BlockchainConfig;
  system: SystemConfig;
  isLoaded: boolean;
  lastUpdated: string | null;

  // Actions
  setBlockchainConfig: (config: Partial<BlockchainConfig>) => void;
  setSystemConfig: (config: Partial<SystemConfig>) => void;
  loadConfig: () => Promise<void>;
  saveConfig: () => Promise<void>;
  resetToDefaults: () => void;
}

// Valores por defecto
const defaultBlockchainConfig: BlockchainConfig = {
  walletConnectProjectId: "",

  investmentContract: "",
  kycContract: "",
  dividendsContract: "",
  tokenFactoryContract: "",

  rpcUrls: {
    polygon: "https://polygon-rpc.com",
    ethereum: "https://eth.llamarpc.com",
    arbitrum: "https://arb1.arbitrum.io/rpc",
    base: "https://mainnet.base.org",
    polygonAmoy: "https://rpc-amoy.polygon.technology",
    sepolia: "https://rpc.sepolia.org",
  },

  explorerApiKeys: {
    polygonscan: "",
    etherscan: "",
    arbiscan: "",
    basescan: "",
  },

  defaultNetwork: "polygon",
  isTestnet: false,
};

const defaultSystemConfig: SystemConfig = {
  appName: "FinCore",
  appVersion: "1.0.0",
  debugMode: false,

  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  apiTimeout: 30000,

  maxUploadSize: 10,
  sessionTimeout: 480,

  kycRequired: true,
  minInvestment: 1000,
  maxInvestment: 1000000,
};

export const useConfigStore = create<ConfigState>()(
  persist(
    (set, get) => ({
      blockchain: defaultBlockchainConfig,
      system: defaultSystemConfig,
      isLoaded: false,
      lastUpdated: null,

      setBlockchainConfig: (config) =>
        set((state) => ({
          blockchain: { ...state.blockchain, ...config },
          lastUpdated: new Date().toISOString(),
        })),

      setSystemConfig: (config) =>
        set((state) => ({
          system: { ...state.system, ...config },
          lastUpdated: new Date().toISOString(),
        })),

      loadConfig: async () => {
        try {
          const response = await fetch(
            `${get().system.apiUrl}/api/v1/config/system`,
            {
              headers: {
                Authorization: `Bearer ${localStorage.getItem("token")}`,
              },
            }
          );

          if (response.ok) {
            const data = await response.json();
            set({
              blockchain: { ...defaultBlockchainConfig, ...data.blockchain },
              system: { ...defaultSystemConfig, ...data.system },
              isLoaded: true,
              lastUpdated: data.updated_at,
            });
          }
        } catch (error) {
          console.error("Error loading config:", error);
          set({ isLoaded: true });
        }
      },

      saveConfig: async () => {
        try {
          const { blockchain, system } = get();
          const response = await fetch(
            `${system.apiUrl}/api/v1/config/system`,
            {
              method: "PUT",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${localStorage.getItem("token")}`,
              },
              body: JSON.stringify({ blockchain, system }),
            }
          );

          if (response.ok) {
            set({ lastUpdated: new Date().toISOString() });
          }
        } catch (error) {
          console.error("Error saving config:", error);
          throw error;
        }
      },

      resetToDefaults: () =>
        set({
          blockchain: defaultBlockchainConfig,
          system: defaultSystemConfig,
          lastUpdated: new Date().toISOString(),
        }),
    }),
    {
      name: "fincore-config",
      partialize: (state) => ({
        blockchain: state.blockchain,
        system: state.system,
        lastUpdated: state.lastUpdated,
      }),
    }
  )
);

// Hook para verificar si esta configurado para produccion
export function useProductionReady(): {
  isReady: boolean;
  missingItems: string[];
} {
  const { blockchain } = useConfigStore();

  const missingItems: string[] = [];

  if (!blockchain.walletConnectProjectId) {
    missingItems.push("WalletConnect Project ID");
  }
  if (!blockchain.investmentContract) {
    missingItems.push("Contrato de Inversion");
  }
  if (!blockchain.kycContract) {
    missingItems.push("Contrato de KYC");
  }
  if (!blockchain.dividendsContract) {
    missingItems.push("Contrato de Dividendos");
  }
  if (!blockchain.explorerApiKeys.polygonscan) {
    missingItems.push("API Key de Polygonscan");
  }

  return {
    isReady: missingItems.length === 0,
    missingItems,
  };
}
