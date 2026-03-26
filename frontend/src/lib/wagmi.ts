import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { polygon, polygonAmoy } from "wagmi/chains";

// Configuracion de WalletConnect
const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "fincore-demo";

// Configuracion principal de wagmi con RainbowKit
// OPTIMIZADO: Solo Polygon (mainnet y testnet) para reducir bundle ~40KB
export const config = getDefaultConfig({
  appName: "FinCore",
  projectId,
  chains: [polygon, polygonAmoy],
  ssr: true,
});

// Direcciones de USDC en cada red (solo Polygon para optimizar bundle)
export const USDC_ADDRESSES: Record<number, `0x${string}`> = {
  [polygon.id]: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", // USDC nativo Polygon
  [polygonAmoy.id]: "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582", // USDC testnet Amoy
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

// Mapeo de chain IDs a nombres de red del backend (solo Polygon)
export const CHAIN_TO_NETWORK: Record<number, string> = {
  [polygon.id]: "polygon",
  [polygonAmoy.id]: "polygon_amoy",
};

// Red por defecto (Polygon)
export const DEFAULT_CHAIN = polygon;

// Exploradores de bloques (solo Polygon)
export const BLOCK_EXPLORERS: Record<number, string> = {
  [polygon.id]: "https://polygonscan.com",
  [polygonAmoy.id]: "https://amoy.polygonscan.com",
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
