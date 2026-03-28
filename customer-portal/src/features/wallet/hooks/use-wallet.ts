"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Types
export interface Wallet {
  id: string;
  user_id: string;
  address: string;
  wallet_type: string;
  label: string;
  preferred_network: string;
  is_primary: boolean;
  is_verified: boolean;
  is_custodial: boolean;
  verified_at: string | null;
  created_at: string;
}

export interface TokenBalance {
  symbol: string;
  name: string;
  balance: number;
  value_usd: number;
}

export interface WalletBalance {
  address: string;
  native_balance: number;
  network: string;
  tokens: TokenBalance[];
}

export interface PortfolioToken {
  token_id: string;
  token_name: string;
  token_symbol: string;
  project_id: string;
  balance: number;
  value_usd: number;
  pending_dividends: number;
  last_dividend_at: string | null;
}

export interface BlockchainTransaction {
  id: string;
  tx_hash: string | null;
  tx_type: string;
  status: string;
  from_address: string | null;
  to_address: string | null;
  amount: number;
  token_symbol: string | null;
  network: string;
  gas_used: number | null;
  gas_price: number | null;
  error_message: string | null;
  created_at: string;
  confirmed_at: string | null;
}

export interface NetworkInfo {
  network: string;
  name: string;
  chain_id: number;
  currency_symbol: string;
  block_explorer: string;
  is_testnet: boolean;
  is_connected: boolean;
  current_block: number | null;
}

export interface CreateCustodialWalletInput {
  label?: string;
  preferred_network: string;
}

// Query keys
export const walletKeys = {
  all: ["wallet"] as const,
  wallets: () => [...walletKeys.all, "list"] as const,
  wallet: (id: string) => [...walletKeys.all, "detail", id] as const,
  balance: (id: string, network: string) => [...walletKeys.all, "balance", id, network] as const,
  portfolio: () => [...walletKeys.all, "portfolio"] as const,
  transactions: (filters?: Record<string, unknown>) => [...walletKeys.all, "transactions", filters] as const,
  networks: () => [...walletKeys.all, "networks"] as const,
};

// Hooks

// Lista de wallets del usuario
export function useWallets() {
  return useQuery({
    queryKey: walletKeys.wallets(),
    queryFn: () => apiClient.get<Wallet[]>("/blockchain/wallets"),
  });
}

// Balance de una wallet
export function useWalletBalance(walletId: string, network: string = "polygon") {
  return useQuery({
    queryKey: walletKeys.balance(walletId, network),
    queryFn: () =>
      apiClient.get<WalletBalance>(`/blockchain/wallets/${walletId}/balance`, {
        network,
      }),
    enabled: !!walletId,
  });
}

// Portfolio de tokens
export function usePortfolio() {
  return useQuery({
    queryKey: walletKeys.portfolio(),
    queryFn: () => apiClient.get<PortfolioToken[]>("/blockchain/portfolio"),
  });
}

// Transacciones blockchain
export function useBlockchainTransactions(options?: {
  limit?: number;
  offset?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: walletKeys.transactions(options),
    queryFn: () =>
      apiClient.get<BlockchainTransaction[]>("/blockchain/transactions", {
        limit: options?.limit || 50,
        offset: options?.offset || 0,
        ...(options?.status && { status_filter: options.status }),
      }),
  });
}

// Redes disponibles
export function useNetworks() {
  return useQuery({
    queryKey: walletKeys.networks(),
    queryFn: () => apiClient.get<NetworkInfo[]>("/blockchain/networks"),
    staleTime: 60 * 1000, // 1 minuto
  });
}

// Crear wallet custodial
export function useCreateCustodialWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateCustodialWalletInput) =>
      apiClient.post<Wallet>("/blockchain/wallets/custodial", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: walletKeys.wallets() });
    },
  });
}

// Eliminar wallet
export function useDeleteWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (walletId: string) =>
      apiClient.delete<void>(`/blockchain/wallets/${walletId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: walletKeys.wallets() });
    },
  });
}

// Helper para formatear dirección
export function formatAddress(address: string, chars: number = 6): string {
  if (!address || address.length < chars * 2) return address;
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

// Helper para obtener link del explorador
export function getExplorerLink(
  txHash: string,
  network: string = "polygon"
): string {
  const explorers: Record<string, string> = {
    polygon: "https://polygonscan.com/tx/",
    ethereum: "https://etherscan.io/tx/",
    arbitrum: "https://arbiscan.io/tx/",
    base: "https://basescan.org/tx/",
  };
  return `${explorers[network] || explorers.polygon}${txHash}`;
}

// Helper para obtener color de estado de transacción
export function getTransactionStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: "text-yellow-500",
    processing: "text-blue-500",
    confirmed: "text-green-500",
    failed: "text-red-500",
  };
  return colors[status] || "text-muted-foreground";
}
