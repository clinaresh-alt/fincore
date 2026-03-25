import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import {
  polygon,
  polygonAmoy,
  mainnet,
  sepolia,
  arbitrum,
  base,
} from "wagmi/chains";

// Configuracion de WalletConnect
const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "fincore-demo";

// Configuracion principal de wagmi con RainbowKit
export const config = getDefaultConfig({
  appName: "FinCore",
  projectId,
  chains: [
    polygon,
    polygonAmoy,
    mainnet,
    sepolia,
    arbitrum,
    base,
  ],
  ssr: true,
});

// Direcciones de USDC en cada red
export const USDC_ADDRESSES: Record<number, `0x${string}`> = {
  [polygon.id]: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", // USDC nativo Polygon
  [polygonAmoy.id]: "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582", // USDC testnet Amoy
  [mainnet.id]: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", // USDC Ethereum
  [sepolia.id]: "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238", // USDC testnet Sepolia
  [arbitrum.id]: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", // USDC nativo Arbitrum
  [base.id]: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", // USDC Base
};

// ABI de USDC (ERC20 basico)
export const USDC_ABI = [
  {
    name: "balanceOf",
    type: "function",
    stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    name: "approve",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "spender", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    name: "transfer",
    type: "function",
    stateMutability: "nonpayable",
    inputs: [
      { name: "to", type: "address" },
      { name: "amount", type: "uint256" },
    ],
    outputs: [{ name: "", type: "bool" }],
  },
  {
    name: "allowance",
    type: "function",
    stateMutability: "view",
    inputs: [
      { name: "owner", type: "address" },
      { name: "spender", type: "address" },
    ],
    outputs: [{ name: "", type: "uint256" }],
  },
  {
    name: "decimals",
    type: "function",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "uint8" }],
  },
  {
    name: "symbol",
    type: "function",
    stateMutability: "view",
    inputs: [],
    outputs: [{ name: "", type: "string" }],
  },
] as const;

// Mapeo de chain IDs a nombres de red del backend
export const CHAIN_TO_NETWORK: Record<number, string> = {
  [polygon.id]: "polygon",
  [polygonAmoy.id]: "polygon_amoy",
  [mainnet.id]: "ethereum",
  [sepolia.id]: "ethereum_sepolia",
  [arbitrum.id]: "arbitrum",
  [base.id]: "base",
};

// Red por defecto (Polygon)
export const DEFAULT_CHAIN = polygon;

// Exploradores de bloques
export const BLOCK_EXPLORERS: Record<number, string> = {
  [polygon.id]: "https://polygonscan.com",
  [polygonAmoy.id]: "https://amoy.polygonscan.com",
  [mainnet.id]: "https://etherscan.io",
  [sepolia.id]: "https://sepolia.etherscan.io",
  [arbitrum.id]: "https://arbiscan.io",
  [base.id]: "https://basescan.org",
};

// Utilidad para obtener URL del explorador
export function getExplorerUrl(chainId: number, type: "tx" | "address", hash: string): string {
  const baseUrl = BLOCK_EXPLORERS[chainId] || BLOCK_EXPLORERS[polygon.id];
  return `${baseUrl}/${type}/${hash}`;
}

// Utilidad para formatear direcciones
export function formatAddress(address: string): string {
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
